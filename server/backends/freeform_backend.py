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

# ── Exceptions ───────────────────────────────────────────────────────


class FreeformPathError(ValueError):
    """Raised when FreeformBackend receives an invalid root path.

    Most commonly: a relative path passed to a remote MCP server.
    The MCP process resolves the relative path against its own CWD
    (the VPS), not the client's repo, which causes data to be written
    in the wrong filesystem.
    """


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

    def __init__(
        self,
        root: str | None = None,
        *,
        allow_relative: bool = False,
        items_content: str | None = None,
    ) -> None:
        """Initialize FreeformBackend in disk mode or memory mode.

        Disk mode (default): operations read/write ``items.json`` and the
        progress Markdown layer under ``root`` on the local filesystem.

        Memory mode (``items_content`` given): the backend operates entirely
        on an in-memory list parsed from ``items_content`` and never touches a
        filesystem. This is the content-passing contract (v6.0.1, UC-660): a
        remote MCP server (``SPECBOX_ENGINE_MCP_URL`` set) cannot reach the
        client's filesystem, so the client reads ``items.json`` locally, passes
        the string in, and writes back ``get_items_content()`` afterwards. The
        progress / readable-layer regeneration is the client's responsibility
        in this mode (the server has no disk to write).

        Args:
            root: Path to the FreeForm data directory. Required in disk mode;
                ignored (and may be omitted) in memory mode. MUST be absolute
                in disk mode unless ``allow_relative`` is True.
            allow_relative: Escape hatch for tests and tools that operate on a
                known-local CWD. Production disk-mode callers resolve to
                absolute before calling, so this stays False.
            items_content: When provided, activates memory mode. The string is
                the raw contents of ``items.json`` (a JSON array). An empty or
                whitespace-only string is treated as an empty board.

        Raises:
            FreeformPathError: In disk mode, if ``root`` is relative and
                ``allow_relative`` is False. Guards against the silent-failure
                mode where a remote MCP resolves a relative path against its
                own CWD instead of the client's repo.
            ValueError: In disk mode, if ``root`` is None; in memory mode, if
                ``items_content`` is not a valid JSON array.
        """
        self._items_cache: list[dict[str, Any]] | None = None
        self._memory_mode = items_content is not None

        if self._memory_mode:
            # Memory mode: no filesystem. `root` is irrelevant.
            self.root = None
            self._mem_comments: dict[str, list[dict[str, Any]]] = {}
            stripped = (items_content or "").strip()
            if not stripped:
                self._mem_items: list[dict[str, Any]] = []
            else:
                parsed = json.loads(stripped)
                if not isinstance(parsed, list):
                    # UC-709: a nested FreeForm index.json ({"user_stories": [...]})
                    # is a dict, not the flat items.json array. Name the dialect
                    # and the fix instead of the cryptic "got dict".
                    if isinstance(parsed, dict) and isinstance(
                        parsed.get("user_stories"), list
                    ):
                        raise ValueError(
                            "items_content is a nested FreeForm index.json "
                            '({"user_stories": [...]}), not the flat items.json '
                            "array this backend consumes. Convert it first with "
                            "server.migration.freeform_normalize."
                            "normalize_source_content (it maps US/UC/AC to flat "
                            "items with labels + parent_id). Note: AC texts live "
                            "in the markdown bodies, not in index.json — pass "
                            "ac_texts for faithful AC, else counts are preserved "
                            "with placeholder AC text."
                        )
                    raise ValueError(
                        "items_content must be a JSON array (the contents of "
                        f"items.json), got {type(parsed).__name__}"
                    )
                self._mem_items = parsed
            return

        if root is None:
            raise ValueError(
                "FreeformBackend requires either root (disk mode) or "
                "items_content (memory mode)."
            )
        path = Path(root)
        if not path.is_absolute() and not allow_relative:
            raise FreeformPathError(
                f"FreeformBackend requires an absolute root path, got {root!r}. "
                "Relative paths are unsafe with a remote MCP server because "
                "they resolve against the server's CWD, not the client's repo. "
                "Pass an absolute path (e.g. /Users/me/myproject/doc/tracking) "
                "or use the /app-init skill which auto-detects it."
            )
        self.root = path

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
        """Load all items. Memory mode: from the in-memory buffer. Disk mode: from disk."""
        if self._memory_mode:
            return self._mem_items
        path = self._items_path()
        if path.exists():
            return json.loads(path.read_text())
        return []

    def _save_items(self, items: list[dict[str, Any]]) -> None:
        """Persist all items. Memory mode: to the in-memory buffer. Disk mode: to disk."""
        if self._memory_mode:
            self._mem_items = items
            self._items_cache = None
            return
        self._items_path().parent.mkdir(parents=True, exist_ok=True)
        self._items_path().write_text(json.dumps(items, indent=2, ensure_ascii=False) + "\n")
        self._items_cache = None

    def get_items_content(self) -> str:
        """Return the current items.json as a string (content-passing contract).

        Only meaningful in memory mode: the caller (a remote-MCP client bridge)
        reads this after a mutation and writes it back to its local items.json.
        In disk mode it still returns a faithful serialization of the current
        items, matching the on-disk format byte-for-byte.
        """
        return json.dumps(self._load_items(), indent=2, ensure_ascii=False) + "\n"

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
        """Regenerate all Markdown progress files from current items.

        No-op in memory mode: there is no server-side filesystem to write, and
        the client owns the readable layer (progress/, us/, uc/). The client
        regenerates it after writing back the mutated items.json.
        """
        if self._memory_mode:
            return
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
        # Memory mode (content-passing): no config.json on disk; the board name
        # is not carried in items.json. Fall back to the conventional default.
        if self._memory_mode:
            return "FreeForm Project"
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

    async def update_acceptance_criterion(
        self,
        board_id: str,
        uc_item_id: str,
        ac_id: str,
        *,
        text: str | None = None,
        done: bool | None = None,
    ) -> ChecklistItemDTO:
        items = self._load_items()
        for item in items:
            if item.get("parent_id") != uc_item_id:
                continue
            if "AC" not in item.get("labels", []):
                continue
            parsed_id, _ = parse_item_id(item.get("name", ""), "AC")
            if parsed_id != ac_id:
                continue
            if text is not None:
                item["name"] = f"[{ac_id}] {text}"
            if done is not None:
                item["state"] = "done" if done else "backlog"
            if text is not None or done is not None:
                item["updated_at"] = _now_iso()
                self._save_items(items)
                self._regenerate_progress()

            _, clean_name = parse_item_id(item["name"], "AC")
            return ChecklistItemDTO(
                id=ac_id,
                text=clean_name or item["name"],
                done=item.get("state") == "done",
                backend_id=item["id"],
            )

        raise ValueError(f"AC '{ac_id}' not found as child of '{uc_item_id}'")

    async def delete_acceptance_criterion(
        self,
        board_id: str,
        uc_item_id: str,
        ac_id: str,
    ) -> None:
        items = self._load_items()
        for idx, item in enumerate(items):
            if item.get("parent_id") != uc_item_id:
                continue
            if "AC" not in item.get("labels", []):
                continue
            parsed_id, _ = parse_item_id(item.get("name", ""), "AC")
            if parsed_id == ac_id:
                items.pop(idx)
                self._save_items(items)
                self._regenerate_progress()
                return
        raise ValueError(f"AC '{ac_id}' not found as child of '{uc_item_id}'")

    # ── SpecBackend: Archival ────────────────────────────────────

    async def archive_item(
        self, board_id: str, item_id: str, *, reason: str,
    ) -> dict[str, Any]:
        items = self._load_items()
        target = None
        target_idx = -1
        for idx, item in enumerate(items):
            if item["id"] == item_id:
                target = item
                target_idx = idx
                break

        if target is None:
            raise ValueError(f"Item '{item_id}' not found in items.json")

        target["archived_at"] = _now_iso()
        target["archive_reason"] = reason

        # Move to archive.json (disk mode only — memory mode has no FS; the
        # archived item is simply dropped from the in-memory items and the
        # client persists archival on its side if it tracks archive.json).
        if not self._memory_mode:
            archive_path = self.root / "archive.json"
            archive: list[dict[str, Any]] = []
            if archive_path.exists():
                try:
                    archive = json.loads(archive_path.read_text())
                except (json.JSONDecodeError, OSError):
                    archive = []
            archive.append(target)
            archive_path.write_text(json.dumps(archive, indent=2, ensure_ascii=False))

        # Remove from items.json
        items.pop(target_idx)
        self._save_items(items)
        self._regenerate_progress()

        return {"archive_location": "archive.json", "archived_at": target["archived_at"]}

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

        if self._memory_mode:
            # No FS in memory mode — buffer comments so callers don't crash.
            # The client persists comments on its side if it tracks them.
            self._mem_comments.setdefault(item_id, []).append(comment)
        else:
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
        if self._memory_mode:
            return [
                CommentDTO(
                    id=c.get("id", ""),
                    text=c.get("text", ""),
                    created_at=c.get("created_at", ""),
                    author=c.get("author", ""),
                )
                for c in self._mem_comments.get(item_id, [])
            ]

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
        if self._memory_mode:
            # No FS in memory mode — return a synthetic DTO without persisting.
            # Attachments aren't part of the items.json content-passing contract.
            return AttachmentDTO(
                id=_new_id("att"),
                name=filename,
                url="",
                size=len(content),
                created_at=_now_iso(),
                mime_type=mime_type,
            )

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
        if self._memory_mode:
            return []
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
        # Memory mode (content-passing): labels are not carried in items.json,
        # so there are none to load — and `self.root` is None. Return empty.
        if self._memory_mode:
            return []
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
