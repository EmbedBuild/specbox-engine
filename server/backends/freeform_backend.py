"""FreeForm backend implementation of SpecBackend.

Filesystem-backed project management — no external API required.
All data stored as JSON files under a configurable root directory,
with auto-generated Markdown progress files for human readability.

Use cases:
- Solo developers without Trello/Plane
- Projects where external PM is overkill
- Offline-first workflows
- Quick prototyping with full traceability

File structure:
    {root}/
    ├── config.json              ← BoardConfig snapshot
    ├── items.json               ← All items (fast list_items)
    ├── labels.json              ← Label definitions
    ├── comments/
    │   └── {item_id}.jsonl      ← Append-only comments
    ├── attachments/
    │   └── {item_id}/
    │       └── {filename}       ← PDF evidence, screenshots
    └── progress/                ← Auto-generated Markdown (human-readable)
        ├── README.md            ← Board overview with tables
        ├── US-XX.md             ← Per-US progress
        └── UC-XXX.md            ← Per-UC detail with ACs
"""

from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
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

logger = structlog.get_logger(__name__)

# ── Constants ────────────────────────────────────────────────────────

FREEFORM_STATES: dict[str, str] = {
    "user_stories": "user_stories",
    "backlog": "backlog",
    "in_progress": "in_progress",
    "review": "review",
    "done": "done",
}

_DEFAULT_LABELS: dict[str, str] = {
    "US": "#3B82F6",
    "UC": "#22C55E",
    "AC": "#A855F7",
    "Infra": "#EAB308",
    "Bloqueado": "#EF4444",
}

_STATE_DISPLAY: dict[str, str] = {
    "user_stories": "User Stories",
    "backlog": "Backlog",
    "in_progress": "In Progress",
    "review": "Review",
    "done": "Done",
}


# ── Helpers ──────────────────────────────────────────────────────────


def _new_id(prefix: str = "ff") -> str:
    """Generate a short unique ID."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _detect_item_type(name: str) -> str:
    """Detect US/UC/AC from name prefix."""
    import re

    if re.match(r"\[?US-\d+", name):
        return "US"
    if re.match(r"\[?UC-\d+", name):
        return "UC"
    if re.match(r"\[?AC-\d+", name):
        return "AC"
    return ""


# ── FreeformBackend ──────────────────────────────────────────────────


class FreeformBackend(SpecBackend):
    """SpecBackend implementation using local filesystem (JSON + Markdown).

    All operations are synchronous file I/O wrapped in async for compatibility.
    Thread-safe for single-writer scenarios (typical Claude Code usage).
    """

    def __init__(self, root: str) -> None:
        self.root = Path(root)
        self._items_cache: list[dict[str, Any]] | None = None

    # ── File I/O primitives ──────────────────────────────────────

    def _items_path(self) -> Path:
        return self.root / "items.json"

    def _config_path(self) -> Path:
        return self.root / "config.json"

    def _labels_path(self) -> Path:
        return self.root / "labels.json"

    def _comments_path(self, item_id: str) -> Path:
        return self.root / "comments" / f"{item_id}.jsonl"

    def _attachments_dir(self, item_id: str) -> Path:
        return self.root / "attachments" / item_id

    def _progress_dir(self) -> Path:
        return self.root / "progress"

    def _load_items(self) -> list[dict[str, Any]]:
        """Load all items from disk."""
        path = self._items_path()
        if path.exists():
            return json.loads(path.read_text())
        return []

    def _save_items(self, items: list[dict[str, Any]]) -> None:
        """Save all items to disk and invalidate cache."""
        self._items_path().parent.mkdir(parents=True, exist_ok=True)
        self._items_path().write_text(json.dumps(items, indent=2, ensure_ascii=False) + "\n")
        self._items_cache = None

    def _load_labels(self) -> dict[str, dict[str, str]]:
        """Load labels. Returns {name: {id, name, color}}."""
        path = self._labels_path()
        if path.exists():
            return json.loads(path.read_text())
        return {}

    def _save_labels(self, labels: dict[str, dict[str, str]]) -> None:
        self._labels_path().parent.mkdir(parents=True, exist_ok=True)
        self._labels_path().write_text(json.dumps(labels, indent=2) + "\n")

    def _load_config(self) -> dict[str, Any]:
        path = self._config_path()
        if path.exists():
            return json.loads(path.read_text())
        return {}

    def _save_config(self, config: dict[str, Any]) -> None:
        self._config_path().parent.mkdir(parents=True, exist_ok=True)
        self._config_path().write_text(json.dumps(config, indent=2) + "\n")

    def _dict_to_dto(self, d: dict[str, Any]) -> ItemDTO:
        """Convert stored dict to ItemDTO."""
        return ItemDTO(
            id=d.get("id", ""),
            name=d.get("name", ""),
            description=d.get("description", ""),
            state=d.get("state", "backlog"),
            state_id=d.get("state", "backlog"),
            parent_id=d.get("parent_id"),
            labels=d.get("labels", []),
            label_ids=d.get("labels", []),
            priority=d.get("priority", "none"),
            url="",
            meta=d.get("meta", {}),
            raw=d,
        )

    def _dto_to_dict(self, item: ItemDTO) -> dict[str, Any]:
        """Convert ItemDTO to storable dict."""
        return {
            "id": item.id,
            "name": item.name,
            "description": item.description,
            "state": item.state,
            "parent_id": item.parent_id,
            "labels": item.labels,
            "priority": item.priority,
            "meta": item.meta,
            "created_at": _now_iso(),
        }

    # ── Progress Markdown generation ─────────────────────────────

    def _regenerate_progress(self) -> None:
        """Regenerate all Markdown progress files from current items."""
        items = self._load_items()
        progress_dir = self._progress_dir()
        progress_dir.mkdir(parents=True, exist_ok=True)

        us_items = [i for i in items if "US" in i.get("labels", [])]
        uc_items = [i for i in items if "UC" in i.get("labels", [])]
        ac_items = [i for i in items if "AC" in i.get("labels", [])]

        # --- README.md: Board overview ---
        lines = [
            "# Progreso del Proyecto",
            "",
            f"> Actualizado: {_now_iso()}",
            "",
            "## User Stories",
            "",
            "| US | Nombre | Estado | UCs Done | UCs Total | % |",
            "|-----|--------|--------|----------|-----------|---|",
        ]

        for us in us_items:
            us_id = us.get("meta", {}).get("us_id", us["id"])
            us_name = us["name"]
            us_state = _STATE_DISPLAY.get(us.get("state", ""), us.get("state", ""))
            # Count child UCs
            child_ucs = [uc for uc in uc_items if uc.get("parent_id") == us["id"]]
            done_ucs = [uc for uc in child_ucs if uc.get("state") == "done"]
            total = len(child_ucs) or 1
            pct = int(len(done_ucs) / total * 100)
            lines.append(
                f"| {us_id} | {us_name} | {us_state} | {len(done_ucs)} | {len(child_ucs)} | {pct}% |"
            )

        lines += ["", "## Use Cases", "", "| UC | US | Estado | ACs Pass | ACs Total | % |",
                   "|-----|-----|--------|----------|-----------|---|"]

        for uc in uc_items:
            uc_id = uc.get("meta", {}).get("uc_id", uc["id"])
            uc_us_id = uc.get("meta", {}).get("us_id", "—")
            uc_state = _STATE_DISPLAY.get(uc.get("state", ""), uc.get("state", ""))
            child_acs = [ac for ac in ac_items if ac.get("parent_id") == uc["id"]]
            done_acs = [ac for ac in child_acs if ac.get("state") == "done"]
            total = len(child_acs) or 1
            pct = int(len(done_acs) / total * 100)
            lines.append(
                f"| {uc_id} | {uc_us_id} | {uc_state} | {len(done_acs)} | {len(child_acs)} | {pct}% |"
            )

        (progress_dir / "README.md").write_text("\n".join(lines) + "\n")

        # --- Per-UC detail files ---
        for uc in uc_items:
            uc_id = uc.get("meta", {}).get("uc_id", uc["id"])
            uc_name = uc["name"]
            uc_state = _STATE_DISPLAY.get(uc.get("state", ""), uc.get("state", ""))
            child_acs = [ac for ac in ac_items if ac.get("parent_id") == uc["id"]]

            uc_lines = [
                f"# {uc_name}",
                "",
                f"- **Estado**: {uc_state}",
                f"- **US padre**: {uc.get('meta', {}).get('us_id', '—')}",
                f"- **Horas estimadas**: {uc.get('meta', {}).get('horas', '—')}",
                f"- **Actor**: {uc.get('meta', {}).get('actor', '—')}",
                "",
                "## Acceptance Criteria",
                "",
                "| AC | Descripción | Estado |",
                "|----|-------------|--------|",
            ]

            for ac in child_acs:
                ac_id_parsed = ac.get("meta", {}).get("ac_id", ac["id"])
                ac_done = "PASS" if ac.get("state") == "done" else "PENDING"
                ac_text = ac["name"]
                uc_lines.append(f"| {ac_id_parsed} | {ac_text} | {ac_done} |")

            # Comments
            comments_path = self._comments_path(uc["id"])
            if comments_path.exists():
                uc_lines += ["", "## Comentarios", ""]
                for line in comments_path.read_text().strip().split("\n"):
                    if line.strip():
                        c = json.loads(line)
                        uc_lines.append(f"- **{c.get('created_at', '')}**: {c.get('text', '')}")

            safe_name = uc_id.replace("/", "-")
            (progress_dir / f"{safe_name}.md").write_text("\n".join(uc_lines) + "\n")

        logger.info("freeform_progress_regenerated", us_count=len(us_items), uc_count=len(uc_items))

    # ── SpecBackend: Auth ────────────────────────────────────────

    async def validate_auth(self) -> BackendUser:
        return BackendUser(
            id="local",
            username="freeform",
            display_name="FreeForm (Local Filesystem)",
        )

    # ── SpecBackend: Board / Project Setup ───────────────────────

    async def setup_board(self, name: str) -> BoardConfig:
        board_id = f"ff-{uuid.uuid4().hex[:12]}"

        # Create directory structure
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "comments").mkdir(exist_ok=True)
        (self.root / "attachments").mkdir(exist_ok=True)
        (self.root / "progress").mkdir(exist_ok=True)

        # Create labels
        labels = {}
        for label_name, color in _DEFAULT_LABELS.items():
            lid = _new_id("lbl")
            labels[label_name] = {"id": lid, "name": label_name, "color": color}
        self._save_labels(labels)

        # Create empty items
        self._save_items([])

        # Save config
        config = {
            "board_id": board_id,
            "board_name": name,
            "board_url": f"file://{self.root}",
            "states": dict(FREEFORM_STATES),
            "labels": {k: v["id"] for k, v in labels.items()},
            "custom_fields": {},
            "created_at": _now_iso(),
        }
        self._save_config(config)

        # Generate initial progress
        self._regenerate_progress()

        return BoardConfig(
            board_id=board_id,
            board_url=f"file://{self.root}",
            states=dict(FREEFORM_STATES),
            labels={k: v["id"] for k, v in labels.items()},
            custom_fields={},
        )

    async def get_board_name(self, board_id: str) -> str:
        config = self._load_config()
        return config.get("board_name", "FreeForm Project")

    # ── SpecBackend: Items (CRUD) ────────────────────────────────

    async def list_items(self, board_id: str) -> list[ItemDTO]:
        items = self._load_items()
        return [self._dict_to_dto(i) for i in items]

    async def get_item(self, board_id: str, item_id: str) -> ItemDTO:
        items = self._load_items()
        for i in items:
            if i["id"] == item_id:
                return self._dict_to_dto(i)
        raise ValueError(f"Item {item_id} not found")

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
        labels = labels or []
        meta = meta or {}

        # Auto-detect type label
        item_type = _detect_item_type(name)
        if item_type and item_type not in labels:
            labels.insert(0, item_type)

        # Auto-extract ID from name
        if item_type:
            parsed_id, _ = parse_item_id(name, item_type)
            if parsed_id:
                meta[f"{item_type.lower()}_id"] = parsed_id
                meta["tipo"] = item_type

        item_id = _new_id("item")
        item = ItemDTO(
            id=item_id,
            name=name,
            description=description,
            state=state,
            state_id=state,
            parent_id=parent_id,
            labels=labels,
            label_ids=labels,
            priority=priority,
            external_source=external_source,
            external_id=external_id,
            meta=meta,
        )

        items = self._load_items()
        d = self._dto_to_dict(item)
        d["external_source"] = external_source
        d["external_id"] = external_id
        items.append(d)
        self._save_items(items)

        self._regenerate_progress()
        logger.info("freeform_item_created", item_id=item_id, name=name, type=item_type)
        return item

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
        items = self._load_items()
        for i in items:
            if i["id"] == item_id:
                if name is not None:
                    i["name"] = name
                if description is not None:
                    i["description"] = description
                if state is not None:
                    i["state"] = state
                if labels is not None:
                    i["labels"] = labels
                if parent_id is not None:
                    i["parent_id"] = parent_id
                if priority is not None:
                    i["priority"] = priority
                if external_source is not None:
                    i["external_source"] = external_source
                if external_id is not None:
                    i["external_id"] = external_id
                if meta is not None:
                    existing_meta = i.get("meta", {})
                    existing_meta.update(meta)
                    i["meta"] = existing_meta
                i["updated_at"] = _now_iso()
                self._save_items(items)
                self._regenerate_progress()
                return self._dict_to_dto(i)

        raise ValueError(f"Item {item_id} not found")

    async def find_item_by_field(
        self, board_id: str, field_name: str, value: str
    ) -> ItemDTO | None:
        items = self._load_items()
        for item in items:
            if field_name in ("us_id", "uc_id", "ac_id"):
                prefix = field_name[:2].upper()
                parsed_id, _ = parse_item_id(item.get("name", ""), prefix)
                if parsed_id == value:
                    return self._dict_to_dto(item)
            elif field_name == "tipo":
                if value in item.get("labels", []):
                    return self._dict_to_dto(item)
            elif field_name in item.get("meta", {}) and item["meta"][field_name] == value:
                return self._dict_to_dto(item)
        return None

    async def get_item_children(
        self, board_id: str, parent_id: str
    ) -> list[ItemDTO]:
        items = self._load_items()
        return [self._dict_to_dto(i) for i in items if i.get("parent_id") == parent_id]

    # ── SpecBackend: Acceptance Criteria ─────────────────────────

    async def get_acceptance_criteria(
        self, board_id: str, uc_item_id: str
    ) -> list[ChecklistItemDTO]:
        children = await self.get_item_children(board_id, uc_item_id)
        result: list[ChecklistItemDTO] = []
        for ac in children:
            if "AC" not in ac.labels:
                continue
            ac_id, clean_name = parse_item_id(ac.name, "AC")
            result.append(
                ChecklistItemDTO(
                    id=ac_id or ac.id,
                    text=clean_name or ac.name,
                    done=ac.state == "done",
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
        items = self._load_items()
        for item in items:
            if item.get("parent_id") != uc_item_id:
                continue
            if "AC" not in item.get("labels", []):
                continue
            parsed_id, clean_name = parse_item_id(item.get("name", ""), "AC")
            if parsed_id == ac_id:
                item["state"] = "done" if passed else "backlog"
                item["updated_at"] = _now_iso()
                self._save_items(items)
                self._regenerate_progress()
                return ChecklistItemDTO(
                    id=ac_id,
                    text=clean_name or item["name"],
                    done=passed,
                    backend_id=item["id"],
                )

        raise ValueError(f"AC '{ac_id}' not found as child of '{uc_item_id}'")

    async def create_acceptance_criteria(
        self,
        board_id: str,
        uc_item_id: str,
        criteria: list[tuple[str, str]],
    ) -> list[ChecklistItemDTO]:
        result: list[ChecklistItemDTO] = []
        items = self._load_items()

        for ac_id, text in criteria:
            item_id = _new_id("ac")
            name = f"[{ac_id}] {text}"
            d = {
                "id": item_id,
                "name": name,
                "description": "",
                "state": "backlog",
                "parent_id": uc_item_id,
                "labels": ["AC"],
                "priority": "none",
                "meta": {"ac_id": ac_id, "tipo": "AC"},
                "created_at": _now_iso(),
            }
            items.append(d)
            result.append(
                ChecklistItemDTO(id=ac_id, text=text, done=False, backend_id=item_id)
            )

        self._save_items(items)
        self._regenerate_progress()
        return result

    # ── SpecBackend: Comments ────────────────────────────────────

    async def add_comment(
        self, board_id: str, item_id: str, text: str
    ) -> CommentDTO:
        comment_id = _new_id("cmt")
        comment = {
            "id": comment_id,
            "text": text,
            "created_at": _now_iso(),
            "author": "freeform",
        }

        path = self._comments_path(item_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as f:
            f.write(json.dumps(comment, ensure_ascii=False) + "\n")

        return CommentDTO(
            id=comment_id,
            text=text,
            created_at=comment["created_at"],
            author="freeform",
        )

    async def get_comments(
        self, board_id: str, item_id: str
    ) -> list[CommentDTO]:
        path = self._comments_path(item_id)
        if not path.exists():
            return []

        result: list[CommentDTO] = []
        for line in path.read_text().strip().split("\n"):
            if line.strip():
                c = json.loads(line)
                result.append(
                    CommentDTO(
                        id=c.get("id", ""),
                        text=c.get("text", ""),
                        created_at=c.get("created_at", ""),
                        author=c.get("author", ""),
                    )
                )
        return result

    # ── SpecBackend: Attachments / Evidence ──────────────────────

    async def add_attachment(
        self,
        board_id: str,
        item_id: str,
        filename: str,
        content: bytes,
        mime_type: str = "application/pdf",
    ) -> AttachmentDTO:
        att_dir = self._attachments_dir(item_id)
        att_dir.mkdir(parents=True, exist_ok=True)

        file_path = att_dir / filename
        file_path.write_bytes(content)

        return AttachmentDTO(
            id=_new_id("att"),
            name=filename,
            url=f"file://{file_path}",
            size=len(content),
            created_at=_now_iso(),
            mime_type=mime_type,
        )

    async def get_attachments(
        self, board_id: str, item_id: str
    ) -> list[AttachmentDTO]:
        att_dir = self._attachments_dir(item_id)
        if not att_dir.exists():
            return []

        result: list[AttachmentDTO] = []
        for f in sorted(att_dir.iterdir()):
            if f.is_file():
                result.append(
                    AttachmentDTO(
                        id=_new_id("att"),
                        name=f.name,
                        url=f"file://{f}",
                        size=f.stat().st_size,
                        created_at="",
                    )
                )
        return result

    # ── SpecBackend: Modules ─────────────────────────────────────

    async def create_module(
        self, board_id: str, name: str, description: str = ""
    ) -> ModuleDTO:
        """Modules in FreeForm are stored as metadata — no separate entity needed."""
        module_id = _new_id("mod")
        return ModuleDTO(id=module_id, name=name, status="planned")

    async def add_items_to_module(
        self, board_id: str, module_id: str, item_ids: list[str]
    ) -> None:
        """No-op for FreeForm — hierarchy is via parent_id, not modules."""
        pass

    # ── SpecBackend: Labels ──────────────────────────────────────

    async def create_label(
        self, board_id: str, name: str, color: str
    ) -> dict[str, str]:
        labels = self._load_labels()
        lid = _new_id("lbl")
        labels[name] = {"id": lid, "name": name, "color": color}
        self._save_labels(labels)
        return {"name": name, "id": lid, "color": color}

    async def get_labels(self, board_id: str) -> list[dict[str, str]]:
        labels = self._load_labels()
        return list(labels.values())

    # ── SpecBackend: States ──────────────────────────────────────

    async def get_state_id(self, board_id: str, state: str) -> str:
        return FREEFORM_STATES.get(state, "backlog")

    async def get_states(self, board_id: str) -> dict[str, str]:
        return dict(FREEFORM_STATES)

    # ── SpecBackend: Cleanup ─────────────────────────────────────

    async def close(self) -> None:
        """No-op — filesystem doesn't need cleanup."""
        pass
