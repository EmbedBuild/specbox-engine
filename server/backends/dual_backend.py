"""DualBackendWrapper — best-effort Native mirror over a primary backend.

US-DUAL-BACKEND (board UC-1101): a project reports to TWO backends at once.
The *primary* (trello / plane / freeform) is the source of truth: every write
goes there first, synchronously, and its result (or exception) propagates to
the caller untouched. The *mirror* (always native) is written AFTER the
primary, wrapped so that ANY mirror failure is logged as structured drift and
swallowed — the primary flow is never blocked, slowed by retries, nor rolled
back because the mirror is down. That guarantee is the reason this class
exists: the primary may feed client-facing tooling tied to payment milestones.

Reads delegate ONLY to the primary; the mirror is never consulted.

item_id translation: backend ids are not portable (a Trello card id means
nothing to Native). Mirror writes addressed at an existing item resolve the
equivalent mirror item by its *logical* id (``UC-XXX`` / ``US-XX``) via
``find_item_by_field`` against the mirror's own board id. A missing mirror
item is logged (``mirror_item_missing``) and the write is skipped —
best-effort, recoverable later by an ``enable_mirror`` re-backfill.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

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

logger = structlog.get_logger("dual_backend")


class DualBackendWrapper(SpecBackend):
    """Compose a primary backend with a best-effort native mirror.

    Args:
        primary: Source-of-truth backend (trello / plane / freeform).
        mirror: Replica backend (native). Written best-effort, never read.
        mirror_board_id: The mirror's own board id (the native project_id).
            Primary board ids arrive per-call and are NOT valid on the mirror.
    """

    def __init__(
        self, primary: SpecBackend, mirror: SpecBackend, mirror_board_id: str
    ) -> None:
        self.primary = primary
        self.mirror = mirror
        self.mirror_board_id = mirror_board_id
        # primary item/module id -> mirror id (None = known-missing).
        # Session-scoped; a stale entry only costs one skipped mirror write.
        self._mirror_ids: dict[str, str | None] = {}

    # ── Mirror guard (the critical guarantee) ─────────────────────

    async def _guarded_mirror(
        self, method: str, thunk: Callable[[], Awaitable[Any]]
    ) -> None:
        """Run a mirror write; log and swallow ANY failure (drift log)."""
        try:
            await thunk()
        except Exception as exc:  # noqa: BLE001 - best-effort by contract
            logger.warning(
                "mirror_write_failed",
                method=method,
                mirror_board=self.mirror_board_id,
                error=str(exc),
            )

    @staticmethod
    def _logical_id(item: ItemDTO) -> tuple[str, str]:
        """Extract (field_name, logical_id) from a primary item, or ("", "")."""
        for label, field_name, prefix in (
            ("UC", "uc_id", "UC"),
            ("US", "us_id", "US"),
        ):
            if label in item.labels or item.meta.get("tipo") == label:
                logical = item.meta.get(field_name) or parse_item_id(item.name, prefix)[0]
                if logical:
                    return field_name, logical
        # No labels to go by — try the name with both prefixes.
        for field_name, prefix in (("uc_id", "UC"), ("us_id", "US")):
            logical = parse_item_id(item.name, prefix)[0]
            if logical:
                return field_name, logical
        return "", ""

    async def _resolve_mirror_id(
        self, board_id: str, primary_item_id: str
    ) -> str | None:
        """Map a primary item id to the equivalent mirror item id (or None)."""
        if primary_item_id in self._mirror_ids:
            return self._mirror_ids[primary_item_id]
        item = await self.primary.get_item(board_id, primary_item_id)
        field_name, logical = self._logical_id(item)
        mirror_id: str | None = None
        if logical:
            found = await self.mirror.find_item_by_field(
                self.mirror_board_id, field_name, logical
            )
            mirror_id = found.id if found else None
        self._mirror_ids[primary_item_id] = mirror_id
        if mirror_id is None:
            logger.warning(
                "mirror_item_missing",
                primary_item_id=primary_item_id,
                logical_id=logical or "<unresolvable>",
                mirror_board=self.mirror_board_id,
            )
        return mirror_id

    # ── Auth / setup (primary only) ───────────────────────────────

    async def validate_auth(self) -> BackendUser:
        return await self.primary.validate_auth()

    async def setup_board(self, name: str) -> BoardConfig:
        # Mirror provisioning is enable_mirror's job, not the wrapper's.
        return await self.primary.setup_board(name)

    async def get_board_name(self, board_id: str) -> str:
        return await self.primary.get_board_name(board_id)

    # ── Reads (primary only — the mirror is never consulted) ─────

    async def list_items(self, board_id: str) -> list[ItemDTO]:
        return await self.primary.list_items(board_id)

    async def get_item(self, board_id: str, item_id: str) -> ItemDTO:
        return await self.primary.get_item(board_id, item_id)

    async def find_item_by_field(
        self, board_id: str, field_name: str, value: str
    ) -> ItemDTO | None:
        return await self.primary.find_item_by_field(board_id, field_name, value)

    async def get_item_children(
        self, board_id: str, parent_id: str
    ) -> list[ItemDTO]:
        return await self.primary.get_item_children(board_id, parent_id)

    async def get_acceptance_criteria(
        self, board_id: str, uc_item_id: str
    ) -> list[ChecklistItemDTO]:
        return await self.primary.get_acceptance_criteria(board_id, uc_item_id)

    async def get_comments(self, board_id: str, item_id: str) -> list[CommentDTO]:
        return await self.primary.get_comments(board_id, item_id)

    async def get_attachments(
        self, board_id: str, item_id: str
    ) -> list[AttachmentDTO]:
        return await self.primary.get_attachments(board_id, item_id)

    async def get_labels(self, board_id: str) -> list[dict[str, str]]:
        return await self.primary.get_labels(board_id)

    async def get_state_id(self, board_id: str, state: str) -> str:
        return await self.primary.get_state_id(board_id, state)

    async def get_states(self, board_id: str) -> dict[str, str]:
        return await self.primary.get_states(board_id)

    # ── Writes (primary first, then best-effort mirror) ──────────

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
        result = await self.primary.create_item(
            board_id,
            name,
            description=description,
            state=state,
            labels=labels,
            parent_id=parent_id,
            priority=priority,
            external_source=external_source,
            external_id=external_id,
            meta=meta,
        )

        async def _mirror() -> None:
            mirror_parent: str | None = None
            if parent_id is not None:
                mirror_parent = await self._resolve_mirror_id(board_id, parent_id)
                if mirror_parent is None:
                    # Creating under an unresolvable parent would corrupt the
                    # mirror hierarchy — skip; re-backfill recovers it.
                    return
            created = await self.mirror.create_item(
                self.mirror_board_id,
                name,
                description=description,
                state=state,
                labels=labels,
                parent_id=mirror_parent,
                priority=priority,
                external_source=external_source,
                external_id=external_id,
                meta=meta,
            )
            self._mirror_ids[result.id] = created.id

        await self._guarded_mirror("create_item", _mirror)
        return result

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
        result = await self.primary.update_item(
            board_id,
            item_id,
            name=name,
            description=description,
            state=state,
            labels=labels,
            parent_id=parent_id,
            priority=priority,
            external_source=external_source,
            external_id=external_id,
            meta=meta,
        )

        async def _mirror() -> None:
            mirror_id = await self._resolve_mirror_id(board_id, item_id)
            if mirror_id is None:
                return
            mirror_parent: str | None = None
            if parent_id is not None:
                mirror_parent = await self._resolve_mirror_id(board_id, parent_id)
                if mirror_parent is None:
                    return
            await self.mirror.update_item(
                self.mirror_board_id,
                mirror_id,
                name=name,
                description=description,
                state=state,
                labels=labels,
                parent_id=mirror_parent,
                priority=priority,
                external_source=external_source,
                external_id=external_id,
                meta=meta,
            )

        await self._guarded_mirror("update_item", _mirror)
        return result

    async def mark_acceptance_criterion(
        self, board_id: str, uc_item_id: str, ac_id: str, passed: bool
    ) -> ChecklistItemDTO:
        result = await self.primary.mark_acceptance_criterion(
            board_id, uc_item_id, ac_id, passed
        )

        async def _mirror() -> None:
            mirror_id = await self._resolve_mirror_id(board_id, uc_item_id)
            if mirror_id is None:
                return
            await self.mirror.mark_acceptance_criterion(
                self.mirror_board_id, mirror_id, ac_id, passed
            )

        await self._guarded_mirror("mark_acceptance_criterion", _mirror)
        return result

    async def create_acceptance_criteria(
        self,
        board_id: str,
        uc_item_id: str,
        criteria: list[tuple[str, str]],
    ) -> list[ChecklistItemDTO]:
        result = await self.primary.create_acceptance_criteria(
            board_id, uc_item_id, criteria
        )

        async def _mirror() -> None:
            mirror_id = await self._resolve_mirror_id(board_id, uc_item_id)
            if mirror_id is None:
                return
            await self.mirror.create_acceptance_criteria(
                self.mirror_board_id, mirror_id, criteria
            )

        await self._guarded_mirror("create_acceptance_criteria", _mirror)
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
        result = await self.primary.update_acceptance_criterion(
            board_id, uc_item_id, ac_id, text=text, done=done
        )

        async def _mirror() -> None:
            mirror_id = await self._resolve_mirror_id(board_id, uc_item_id)
            if mirror_id is None:
                return
            await self.mirror.update_acceptance_criterion(
                self.mirror_board_id, mirror_id, ac_id, text=text, done=done
            )

        await self._guarded_mirror("update_acceptance_criterion", _mirror)
        return result

    async def delete_acceptance_criterion(
        self, board_id: str, uc_item_id: str, ac_id: str
    ) -> None:
        result = await self.primary.delete_acceptance_criterion(
            board_id, uc_item_id, ac_id
        )

        async def _mirror() -> None:
            mirror_id = await self._resolve_mirror_id(board_id, uc_item_id)
            if mirror_id is None:
                return
            await self.mirror.delete_acceptance_criterion(
                self.mirror_board_id, mirror_id, ac_id
            )

        await self._guarded_mirror("delete_acceptance_criterion", _mirror)
        return result

    async def archive_item(
        self, board_id: str, item_id: str, *, reason: str
    ) -> dict[str, Any]:
        result = await self.primary.archive_item(board_id, item_id, reason=reason)

        async def _mirror() -> None:
            mirror_id = await self._resolve_mirror_id(board_id, item_id)
            if mirror_id is None:
                return
            await self.mirror.archive_item(
                self.mirror_board_id, mirror_id, reason=reason
            )

        await self._guarded_mirror("archive_item", _mirror)
        return result

    async def add_comment(
        self, board_id: str, item_id: str, text: str
    ) -> CommentDTO:
        result = await self.primary.add_comment(board_id, item_id, text)

        async def _mirror() -> None:
            mirror_id = await self._resolve_mirror_id(board_id, item_id)
            if mirror_id is None:
                return
            await self.mirror.add_comment(self.mirror_board_id, mirror_id, text)

        await self._guarded_mirror("add_comment", _mirror)
        return result

    async def add_attachment(
        self,
        board_id: str,
        item_id: str,
        filename: str,
        content: bytes,
        mime_type: str = "application/pdf",
    ) -> AttachmentDTO:
        result = await self.primary.add_attachment(
            board_id, item_id, filename, content, mime_type
        )

        async def _mirror() -> None:
            mirror_id = await self._resolve_mirror_id(board_id, item_id)
            if mirror_id is None:
                return
            await self.mirror.add_attachment(
                self.mirror_board_id, mirror_id, filename, content, mime_type
            )

        await self._guarded_mirror("add_attachment", _mirror)
        return result

    async def create_module(
        self, board_id: str, name: str, description: str = ""
    ) -> ModuleDTO:
        result = await self.primary.create_module(board_id, name, description)

        async def _mirror() -> None:
            created = await self.mirror.create_module(
                self.mirror_board_id, name, description
            )
            self._mirror_ids[result.id] = created.id

        await self._guarded_mirror("create_module", _mirror)
        return result

    async def add_items_to_module(
        self, board_id: str, module_id: str, item_ids: list[str]
    ) -> None:
        result = await self.primary.add_items_to_module(board_id, module_id, item_ids)

        async def _mirror() -> None:
            mirror_module = self._mirror_ids.get(module_id)
            if mirror_module is None:
                logger.warning(
                    "mirror_item_missing",
                    primary_item_id=module_id,
                    logical_id="<module>",
                    mirror_board=self.mirror_board_id,
                )
                return
            mirror_items: list[str] = []
            for item_id in item_ids:
                resolved = await self._resolve_mirror_id(board_id, item_id)
                if resolved is not None:
                    mirror_items.append(resolved)
            if mirror_items:
                await self.mirror.add_items_to_module(
                    self.mirror_board_id, mirror_module, mirror_items
                )

        await self._guarded_mirror("add_items_to_module", _mirror)
        return result

    async def create_label(
        self, board_id: str, name: str, color: str
    ) -> dict[str, str]:
        result = await self.primary.create_label(board_id, name, color)

        async def _mirror() -> None:
            await self.mirror.create_label(self.mirror_board_id, name, color)

        await self._guarded_mirror("create_label", _mirror)
        return result

    # ── Cleanup ──────────────────────────────────────────────────

    async def close(self) -> None:
        # Mirror first, guarded: its failure must never block the primary's
        # cleanup (AC-05). Primary close propagates normally.
        try:
            await self.mirror.close()
        except Exception as exc:  # noqa: BLE001 - best-effort by contract
            logger.warning(
                "mirror_close_failed",
                mirror_board=self.mirror_board_id,
                error=str(exc),
            )
        await self.primary.close()
