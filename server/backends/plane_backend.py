"""Plane backend implementation of SpecBackend.

Maps the abstract SpecBackend interface to Plane REST API v1 using PlaneClient.
Works with both Plane Cloud and Plane CE (self-hosted) — only the base_url differs.
Uses labels and name conventions to encode metadata (tipo, us_id, uc_id, etc.)
since Plane does not expose custom properties via its REST API.
"""

from __future__ import annotations

import html
import re
from typing import Any

import structlog

from ..spec_backend import (
    AttachmentDTO,
    BackendUser,
    BoardConfig,
    ChecklistItemDTO,
    CommentDTO,
    ItemDTO,
    ModuleDTO,
    SpecBackend,
    parse_item_id,
)
from .plane_client import PlaneClient

logger = structlog.get_logger(__name__)

# ── Constants ────────────────────────────────────────────────────────

PLANE_STATE_NAMES: dict[str, str] = {
    "user_stories": "User Stories",
    "backlog": "Backlog",
    "in_progress": "In Progress",
    "review": "Review",
    "done": "Done",
}

# Reverse: display name -> workflow key
_STATE_NAME_TO_KEY: dict[str, str] = {
    v.lower(): k for k, v in PLANE_STATE_NAMES.items()
}

# Default labels to create on board setup
_DEFAULT_LABELS: dict[str, str] = {
    "US": "#3B82F6",
    "UC": "#22C55E",
    "AC": "#A855F7",
    "Infra": "#EAB308",
    "Bloqueado": "#EF4444",
}

# State groups in Plane CE
_STATE_GROUPS: dict[str, str] = {
    "user_stories": "backlog",
    "backlog": "backlog",
    "in_progress": "started",
    "review": "started",
    "done": "completed",
}

# Completed state groups (for AC done detection)
_COMPLETED_GROUPS = {"completed"}

# Regex for extracting metadata from description_html
_META_RE = re.compile(
    r"<p>\s*<strong>(\w+)</strong>\s*:\s*(.*?)\s*</p>",
    re.IGNORECASE,
)


# ── Helpers ──────────────────────────────────────────────────────────


def _extract_meta_from_html(description_html: str) -> dict[str, str]:
    """Extract structured metadata from description HTML.

    Looks for patterns like: <p><strong>Horas</strong>: 8</p>
    """
    meta: dict[str, str] = {}
    for match in _META_RE.finditer(description_html or ""):
        key = match.group(1).lower()
        value = match.group(2).strip()
        # Strip HTML tags and decode entities
        value = re.sub(r"<[^>]+>", "", value).strip()
        value = html.unescape(value)
        meta[key] = value
    return meta


def _build_description_html(
    description: str,
    meta: dict[str, Any] | None = None,
) -> str:
    """Build Plane description_html with metadata sections appended."""
    parts: list[str] = []

    if description:
        # If description already looks like HTML, use as-is
        if description.strip().startswith("<"):
            parts.append(description)
        else:
            # Wrap plain text in paragraphs
            for line in description.split("\n"):
                escaped = html.escape(line) if line.strip() else ""
                if escaped:
                    parts.append(f"<p>{escaped}</p>")
                else:
                    parts.append("<p></p>")

    if meta:
        meta_fields = ["horas", "pantallas", "actor"]
        for field_name in meta_fields:
            value = meta.get(field_name)
            if value:
                escaped_val = html.escape(str(value))
                parts.append(
                    f"<p><strong>{field_name.capitalize()}</strong>: {escaped_val}</p>"
                )

    return "\n".join(parts)


def _strip_html(text: str) -> str:
    """Strip HTML tags for plain text output."""
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _detect_item_type(name: str) -> str:
    """Detect item type prefix from name: US, UC, or AC."""
    if re.match(r"\[?US-\d+", name):
        return "US"
    if re.match(r"\[?UC-\d+", name):
        return "UC"
    if re.match(r"\[?AC-\d+", name):
        return "AC"
    return ""


# ── PlaneBackend ─────────────────────────────────────────────────────


class PlaneBackend(SpecBackend):
    """SpecBackend implementation for Plane (Cloud and CE).

    Metadata encoding (no custom properties):
    - tipo (US/UC/AC): Label "US", "UC", or "AC"
    - us_id / uc_id / ac_id: Parsed from name prefix [US-XX] / [UC-XXX] / [AC-XX]
    - horas, pantallas, actor: Stored in description_html as <p><strong>Key</strong>: Value</p>
    - Actor label: "Actor:Profesional", "Actor:Empresa", etc.
    - Hierarchy: parent field on work items (UC -> US, AC -> UC)
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        workspace_slug: str,
    ) -> None:
        self.client = PlaneClient(
            base_url=base_url,
            api_key=api_key,
            workspace_slug=workspace_slug,
        )
        # Caches: board_id -> {key: id}
        self._state_cache: dict[str, dict[str, str]] = {}
        self._label_cache: dict[str, dict[str, str]] = {}
        # State group cache: board_id -> {state_id: group}
        self._state_group_cache: dict[str, dict[str, str]] = {}

    # ── Cache management ─────────────────────────────────────────

    async def _ensure_state_cache(self, board_id: str) -> dict[str, str]:
        """Ensure state cache is populated. Returns {state_key: state_id}."""
        if board_id not in self._state_cache:
            states = await self.client.list_states(board_id)
            mapping: dict[str, str] = {}
            group_mapping: dict[str, str] = {}
            for s in states:
                name_lower = s.get("name", "").lower()
                state_id = s.get("id", "")
                group = s.get("group", "")
                group_mapping[state_id] = group
                # Map by exact name match
                if name_lower in _STATE_NAME_TO_KEY:
                    mapping[_STATE_NAME_TO_KEY[name_lower]] = state_id
                # Also map by Plane default state names
                elif name_lower == "todo":
                    mapping.setdefault("backlog", state_id)
                elif name_lower == "in progress":
                    mapping.setdefault("in_progress", state_id)
                elif name_lower == "done":
                    mapping.setdefault("done", state_id)
            self._state_cache[board_id] = mapping
            self._state_group_cache[board_id] = group_mapping
        return self._state_cache[board_id]

    async def _ensure_label_cache(self, board_id: str) -> dict[str, str]:
        """Ensure label cache is populated. Returns {label_name: label_id}."""
        if board_id not in self._label_cache:
            labels = await self.client.list_labels(board_id)
            self._label_cache[board_id] = {
                lbl.get("name", ""): lbl.get("id", "") for lbl in labels
            }
        return self._label_cache[board_id]

    def _invalidate_caches(self, board_id: str) -> None:
        """Invalidate caches for a board (after setup or label creation)."""
        self._state_cache.pop(board_id, None)
        self._label_cache.pop(board_id, None)
        self._state_group_cache.pop(board_id, None)

    async def _resolve_label_ids(
        self, board_id: str, label_names: list[str]
    ) -> list[str]:
        """Resolve label names to IDs."""
        cache = await self._ensure_label_cache(board_id)
        ids: list[str] = []
        for name in label_names:
            lid = cache.get(name)
            if lid:
                ids.append(lid)
            else:
                logger.warning("plane_label_not_found", label=name, board_id=board_id)
        return ids

    async def _resolve_state_id(self, board_id: str, state_key: str) -> str:
        """Resolve a workflow state key to its Plane UUID."""
        cache = await self._ensure_state_cache(board_id)
        state_id = cache.get(state_key, "")
        if not state_id:
            logger.warning(
                "plane_state_not_found",
                state=state_key,
                board_id=board_id,
                available=list(cache.keys()),
            )
        return state_id

    def _state_id_to_key(self, board_id: str, state_id: str) -> str:
        """Reverse-lookup: state UUID -> workflow key."""
        cache = self._state_cache.get(board_id, {})
        for key, sid in cache.items():
            if sid == state_id:
                return key
        return "backlog"

    def _is_state_completed(self, board_id: str, state_id: str) -> bool:
        """Check if a state belongs to a completed group."""
        group = self._state_group_cache.get(board_id, {}).get(state_id, "")
        return group in _COMPLETED_GROUPS

    # ── SpecBackend: Auth ────────────────────────────────────────

    async def validate_auth(self) -> BackendUser:
        user = await self.client.get_me()
        return BackendUser(
            id=user.get("id", ""),
            username=user.get("username", user.get("email", "")),
            display_name=user.get("display_name", user.get("first_name", "")),
        )

    # ── SpecBackend: Board / Project Setup ───────────────────────

    async def setup_board(self, name: str) -> BoardConfig:
        # Create project
        identifier = re.sub(r"[^A-Z0-9]", "", name.upper()[:5]) or "PROJ"
        project = await self.client.create_project(
            name=name,
            identifier=identifier,
            network=2,  # 2 = public to workspace
        )
        project_id = project["id"]

        # Create custom states (Plane CE creates defaults; we add ours)
        existing_states = await self.client.list_states(project_id)
        existing_names = {s["name"].lower() for s in existing_states}

        states_mapping: dict[str, str] = {}

        # Map existing defaults first
        for s in existing_states:
            name_lower = s["name"].lower()
            if name_lower in _STATE_NAME_TO_KEY:
                states_mapping[_STATE_NAME_TO_KEY[name_lower]] = s["id"]
            elif name_lower == "todo":
                states_mapping["backlog"] = s["id"]
            elif name_lower == "in progress":
                states_mapping["in_progress"] = s["id"]
            elif name_lower == "done":
                states_mapping["done"] = s["id"]

        # Create missing states
        for state_key, state_name in PLANE_STATE_NAMES.items():
            if state_key not in states_mapping and state_name.lower() not in existing_names:
                group = _STATE_GROUPS.get(state_key, "backlog")
                new_state = await self.client.create_state(
                    project_id,
                    name=state_name,
                    color="#6B7280",
                    group=group,
                )
                states_mapping[state_key] = new_state["id"]

        # Create labels
        labels_mapping: dict[str, str] = {}
        existing_labels = await self.client.list_labels(project_id)
        existing_label_names = {lbl["name"].lower() for lbl in existing_labels}

        for label_name, color in _DEFAULT_LABELS.items():
            if label_name.lower() in existing_label_names:
                # Find existing
                for lbl in existing_labels:
                    if lbl["name"].lower() == label_name.lower():
                        labels_mapping[label_name] = lbl["id"]
                        break
            else:
                new_label = await self.client.create_label(
                    project_id, name=label_name, color=color
                )
                labels_mapping[label_name] = new_label["id"]

        # Invalidate and repopulate caches for the new project
        self._invalidate_caches(project_id)
        await self._ensure_state_cache(project_id)
        await self._ensure_label_cache(project_id)

        project_url = (
            f"{self.client.base_url}/{self.client.workspace_slug}"
            f"/projects/{project_id}/issues/"
        )

        return BoardConfig(
            board_id=project_id,
            board_url=project_url,
            states=states_mapping,
            labels=labels_mapping,
            custom_fields={},  # Plane CE: no custom properties
        )

    async def get_board_name(self, board_id: str) -> str:
        project = await self.client.get_project(board_id)
        return project.get("name", "")

    # ── SpecBackend: Items (CRUD) ────────────────────────────────

    async def list_items(self, board_id: str) -> list[ItemDTO]:
        # Ensure caches are warm
        await self._ensure_state_cache(board_id)
        await self._ensure_label_cache(board_id)

        raw_items = await self.client.list_work_items(board_id)
        label_cache = self._label_cache.get(board_id, {})
        # Reverse label cache: id -> name
        label_id_to_name = {v: k for k, v in label_cache.items()}

        result: list[ItemDTO] = []
        for item in raw_items:
            result.append(
                self._raw_to_dto(item, board_id, label_id_to_name)
            )
        return result

    async def get_item(self, board_id: str, item_id: str) -> ItemDTO:
        await self._ensure_state_cache(board_id)
        await self._ensure_label_cache(board_id)

        raw = await self.client.get_work_item(board_id, item_id, expand="labels,state")
        label_cache = self._label_cache.get(board_id, {})
        label_id_to_name = {v: k for k, v in label_cache.items()}
        return self._raw_to_dto(raw, board_id, label_id_to_name)

    async def create_item(
        self,
        board_id: str,
        name: str,
        description: str = "",
        state: str = "backlog",
        labels: list[str] | None = None,
        parent_id: str | None = None,
        priority: str = "none",
        external_source: str = "",
        external_id: str = "",
        meta: dict[str, Any] | None = None,
    ) -> ItemDTO:
        meta = meta or {}
        labels = labels or []

        # Auto-add type label if detectable from name
        item_type = _detect_item_type(name)
        if item_type and item_type not in labels:
            labels.insert(0, item_type)

        # Auto-add actor label
        actor = meta.get("actor")
        if actor:
            actor_label = f"Actor:{actor}"
            if actor_label not in labels:
                labels.append(actor_label)
                # Ensure actor label exists
                label_cache = await self._ensure_label_cache(board_id)
                if actor_label not in label_cache:
                    new_lbl = await self.client.create_label(
                        board_id, name=actor_label, color="#94A3B8"
                    )
                    label_cache[actor_label] = new_lbl["id"]

        # Resolve IDs
        state_id = await self._resolve_state_id(board_id, state)
        label_ids = await self._resolve_label_ids(board_id, labels)

        # Build description with metadata
        description_html = _build_description_html(description, meta)

        # Map priority string to Plane priority value
        priority_map = {
            "none": "none",
            "low": "low",
            "medium": "medium",
            "high": "high",
            "urgent": "urgent",
        }
        plane_priority = priority_map.get(priority, "none")

        data: dict[str, Any] = {
            "name": name,
            "description_html": description_html,
            "priority": plane_priority,
            "labels": label_ids,
        }
        if state_id:
            data["state"] = state_id
        if parent_id:
            data["parent"] = parent_id

        raw = await self.client.create_work_item(board_id, **data)

        # Re-fetch with expand to get full DTO
        return await self.get_item(board_id, raw["id"])

    async def update_item(
        self,
        board_id: str,
        item_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        state: str | None = None,
        labels: list[str] | None = None,
        parent_id: str | None = None,
        priority: str | None = None,
        external_source: str | None = None,
        external_id: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> ItemDTO:
        data: dict[str, Any] = {}

        if name is not None:
            data["name"] = name
        if description is not None:
            data["description_html"] = _build_description_html(description, meta)
        elif meta is not None:
            # Update meta in existing description
            existing = await self.client.get_work_item(board_id, item_id)
            existing_html = existing.get("description_html", "")
            # Remove old meta lines
            cleaned = _META_RE.sub("", existing_html).strip()
            data["description_html"] = _build_description_html(cleaned, meta)
        if state is not None:
            state_id = await self._resolve_state_id(board_id, state)
            if state_id:
                data["state"] = state_id
        if labels is not None:
            label_ids = await self._resolve_label_ids(board_id, labels)
            data["labels"] = label_ids
        if parent_id is not None:
            data["parent"] = parent_id
        if priority is not None:
            priority_map = {
                "none": "none",
                "low": "low",
                "medium": "medium",
                "high": "high",
                "urgent": "urgent",
            }
            data["priority"] = priority_map.get(priority, priority)

        if data:
            await self.client.update_work_item(board_id, item_id, **data)

        return await self.get_item(board_id, item_id)

    async def find_item_by_field(
        self, board_id: str, field_name: str, value: str
    ) -> ItemDTO | None:
        items = await self.list_items(board_id)

        for item in items:
            if field_name in ("us_id", "uc_id", "ac_id"):
                prefix = field_name[:2].upper()
                parsed_id, _ = parse_item_id(item.name, prefix)
                if parsed_id == value:
                    return item
            elif field_name == "tipo":
                if value in item.labels:
                    return item
            elif field_name == "actor":
                actor_label = f"Actor:{value}"
                if actor_label in item.labels:
                    return item
            elif field_name in item.meta and item.meta[field_name] == value:
                return item

        return None

    async def get_item_children(
        self, board_id: str, parent_id: str
    ) -> list[ItemDTO]:
        items = await self.list_items(board_id)
        return [i for i in items if i.parent_id == parent_id]

    # ── SpecBackend: Acceptance Criteria ─────────────────────────

    async def get_acceptance_criteria(
        self, board_id: str, uc_item_id: str
    ) -> list[ChecklistItemDTO]:
        children = await self.get_item_children(board_id, uc_item_id)
        ac_items = [c for c in children if "AC" in c.labels]

        result: list[ChecklistItemDTO] = []
        for ac in ac_items:
            ac_id, clean_name = parse_item_id(ac.name, "AC")
            done = self._is_state_completed(board_id, ac.state_id)
            result.append(
                ChecklistItemDTO(
                    id=ac_id or ac.id,
                    text=clean_name or ac.name,
                    done=done,
                    backend_id=ac.id,
                )
            )
        return result

    async def mark_acceptance_criterion(
        self,
        board_id: str,
        uc_item_id: str,
        ac_id: str,
        passed: bool,
    ) -> ChecklistItemDTO:
        # Find the AC child matching ac_id
        children = await self.get_item_children(board_id, uc_item_id)
        ac_item: ItemDTO | None = None
        for child in children:
            if "AC" not in child.labels:
                continue
            parsed_id, _ = parse_item_id(child.name, "AC")
            if parsed_id == ac_id:
                ac_item = child
                break

        if not ac_item:
            raise ValueError(
                f"AC '{ac_id}' not found as child of UC item '{uc_item_id}'"
            )

        # Move to Done or Backlog
        target_state = "done" if passed else "backlog"
        state_id = await self._resolve_state_id(board_id, target_state)
        if state_id:
            await self.client.update_work_item(
                board_id, ac_item.id, state=state_id
            )

        _, clean_name = parse_item_id(ac_item.name, "AC")
        return ChecklistItemDTO(
            id=ac_id,
            text=clean_name or ac_item.name,
            done=passed,
            backend_id=ac_item.id,
        )

    async def create_acceptance_criteria(
        self,
        board_id: str,
        uc_item_id: str,
        criteria: list[tuple[str, str]],
    ) -> list[ChecklistItemDTO]:
        result: list[ChecklistItemDTO] = []
        ac_label_ids = await self._resolve_label_ids(board_id, ["AC"])
        if not ac_label_ids:
            # Ensure AC label exists before creating ACs
            new_label = await self.client.create_label(
                board_id, name="AC", color="#A855F7"
            )
            ac_label_ids = [new_label["id"]]
            # Update cache
            if board_id in self._label_cache:
                self._label_cache[board_id]["AC"] = new_label["id"]

        backlog_state_id = await self._resolve_state_id(board_id, "backlog")

        for ac_id, text in criteria:
            name = f"[{ac_id}] {text}"
            data: dict[str, Any] = {
                "name": name,
                "labels": ac_label_ids,
                "parent": uc_item_id,
            }
            if backlog_state_id:
                data["state"] = backlog_state_id

            raw = await self.client.create_work_item(board_id, **data)
            result.append(
                ChecklistItemDTO(
                    id=ac_id,
                    text=text,
                    done=False,
                    backend_id=raw["id"],
                )
            )

        return result

    # ── SpecBackend: Comments ────────────────────────────────────

    async def add_comment(
        self, board_id: str, item_id: str, text: str
    ) -> CommentDTO:
        # Wrap in HTML if not already
        if not text.strip().startswith("<"):
            comment_html = f"<p>{html.escape(text)}</p>"
        else:
            comment_html = text

        raw = await self.client.create_comment(board_id, item_id, comment_html)
        return CommentDTO(
            id=raw.get("id", ""),
            text=_strip_html(raw.get("comment_html", text)),
            created_at=raw.get("created_at", ""),
            author=raw.get("actor_detail", {}).get("display_name", ""),
        )

    async def get_comments(
        self, board_id: str, item_id: str
    ) -> list[CommentDTO]:
        raw_comments = await self.client.list_comments(board_id, item_id)
        return [
            CommentDTO(
                id=c.get("id", ""),
                text=_strip_html(c.get("comment_html", "")),
                created_at=c.get("created_at", ""),
                author=c.get("actor_detail", {}).get("display_name", ""),
            )
            for c in raw_comments
        ]

    # ── SpecBackend: Attachments / Evidence ──────────────────────

    async def add_attachment(
        self,
        board_id: str,
        item_id: str,
        filename: str,
        content: bytes,
        mime_type: str = "application/pdf",
    ) -> AttachmentDTO:
        """Store attachment as a comment (Plane CE MVP).

        Plane CE file attachments require S3 presigned URLs which are complex
        to set up. For MVP, we store evidence as a comment with filename reference
        and create a link if the content can be summarized.
        """
        logger.warning(
            "plane_attachment_as_comment",
            filename=filename,
            mime_type=mime_type,
            size=len(content),
            reason="Plane CE file attachments require S3 presigned URLs. "
            "Storing as comment for MVP.",
        )

        comment_html = (
            f"<p><strong>Attachment</strong>: {html.escape(filename)}</p>"
            f"<p><em>Type</em>: {html.escape(mime_type)} | "
            f"<em>Size</em>: {len(content)} bytes</p>"
            f"<p><em>Note</em>: File stored as comment in Plane CE. "
            f"For full file support, configure S3 storage.</p>"
        )

        raw = await self.client.create_comment(board_id, item_id, comment_html)
        comment_id = raw.get("id", "")

        return AttachmentDTO(
            id=f"comment:{comment_id}",
            name=filename,
            url="",
            size=len(content),
            created_at=raw.get("created_at", ""),
            mime_type=mime_type,
        )

    async def get_attachments(
        self, board_id: str, item_id: str
    ) -> list[AttachmentDTO]:
        """Get attachments as links from Plane."""
        raw_links = await self.client.list_links(board_id, item_id)
        return [
            AttachmentDTO(
                id=link.get("id", ""),
                name=link.get("title", link.get("url", "")),
                url=link.get("url", ""),
                created_at=link.get("created_at", ""),
            )
            for link in raw_links
        ]

    # ── SpecBackend: Modules ─────────────────────────────────────

    async def create_module(
        self, board_id: str, name: str, description: str = ""
    ) -> ModuleDTO:
        raw = await self.client.create_module(
            board_id,
            name=name,
            description=description,
            status="planned",
        )
        return ModuleDTO(
            id=raw.get("id", ""),
            name=raw.get("name", name),
            status=raw.get("status", "planned"),
        )

    async def add_items_to_module(
        self, board_id: str, module_id: str, item_ids: list[str]
    ) -> None:
        await self.client.add_items_to_module(board_id, module_id, item_ids)

    # ── SpecBackend: Labels ──────────────────────────────────────

    async def create_label(
        self, board_id: str, name: str, color: str
    ) -> dict[str, str]:
        raw = await self.client.create_label(board_id, name=name, color=color)
        label_id = raw.get("id", "")

        # Update cache
        if board_id in self._label_cache:
            self._label_cache[board_id][name] = label_id

        return {"name": name, "id": label_id, "color": color}

    async def get_labels(self, board_id: str) -> list[dict[str, str]]:
        raw_labels = await self.client.list_labels(board_id)
        return [
            {
                "name": lbl.get("name", ""),
                "id": lbl.get("id", ""),
                "color": lbl.get("color", ""),
            }
            for lbl in raw_labels
        ]

    # ── SpecBackend: States ──────────────────────────────────────

    async def get_state_id(self, board_id: str, state: str) -> str:
        return await self._resolve_state_id(board_id, state)

    async def get_states(self, board_id: str) -> dict[str, str]:
        return await self._ensure_state_cache(board_id)

    # ── SpecBackend: Cleanup ─────────────────────────────────────

    async def close(self) -> None:
        await self.client.close()

    # ── Internal: DTO building ───────────────────────────────────

    def _raw_to_dto(
        self,
        item: dict[str, Any],
        board_id: str,
        label_id_to_name: dict[str, str],
    ) -> ItemDTO:
        """Convert raw Plane API response to ItemDTO."""
        item_id = item.get("id", "")
        name = item.get("name", "")
        description_html = item.get("description_html", "")

        # Resolve state
        state_id = item.get("state", "")
        # If expanded, state is a dict
        if isinstance(state_id, dict):
            state_id = state_id.get("id", "")
        state_key = self._state_id_to_key(board_id, state_id)

        # Resolve labels
        raw_labels = item.get("labels", [])
        label_names: list[str] = []
        label_ids: list[str] = []
        for lbl in raw_labels:
            if isinstance(lbl, dict):
                # Expanded
                label_names.append(lbl.get("name", ""))
                label_ids.append(lbl.get("id", ""))
            elif isinstance(lbl, str):
                # Just ID
                label_ids.append(lbl)
                label_names.append(label_id_to_name.get(lbl, lbl))

        # Extract meta from description and labels
        meta = _extract_meta_from_html(description_html)

        # Parse structured ID from name
        item_type = _detect_item_type(name)
        if item_type:
            prefix = item_type
            parsed_id, _ = parse_item_id(name, prefix)
            if parsed_id:
                meta_key = f"{prefix.lower()}_id"
                meta[meta_key] = parsed_id
                meta["tipo"] = item_type

        # Extract actor from labels
        for lbl_name in label_names:
            if lbl_name.startswith("Actor:"):
                meta["actor"] = lbl_name[6:]
                break

        # Parent
        parent_id = item.get("parent", None)
        if isinstance(parent_id, dict):
            parent_id = parent_id.get("id")

        # Priority
        priority = item.get("priority", "none") or "none"

        # URL
        project_id_val = item.get("project", board_id)
        if isinstance(project_id_val, dict):
            project_id_val = project_id_val.get("id", board_id)
        url = (
            f"{self.client.base_url}/{self.client.workspace_slug}"
            f"/projects/{project_id_val}/issues/{item_id}"
        )

        return ItemDTO(
            id=item_id,
            name=name,
            description=_strip_html(description_html),
            state=state_key,
            state_id=state_id,
            parent_id=parent_id,
            labels=label_names,
            label_ids=label_ids,
            priority=priority,
            url=url,
            meta=meta,
            raw=item,
        )
