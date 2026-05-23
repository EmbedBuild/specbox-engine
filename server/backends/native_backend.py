"""Native Postgres backend implementation of SpecBackend (UC-101).

A first-class, multi-tenant backend that persists the spec hierarchy
(US -> UC -> AC) to Postgres instead of an external PM API (Trello/Plane)
or the local filesystem (FreeForm). Built on the asyncpg pool and the
schema delivered by UC-102 (``server/db/``).

It mirrors the *semantics* of FreeformBackend method-by-method — item type
detection by name prefix, the same DTO field mapping, parent_id-based
hierarchy, the same workflow state keys — but every operation is a
parametrized SQL statement against three tables: ``user_stories``,
``use_cases`` and ``acceptance_criteria``.

FRONTIER 2 — credential security
================================
This backend NEVER takes a DSN or any database credential. The constructor
accepts only a ``project_id`` (the tenant root). The connection is obtained
exclusively through :func:`server.db.pool.get_pool`, which is the single
chokepoint that reads the DSN from the ``SPECBOX_NATIVE_DSN`` environment
variable. Callers wire ``board_id`` (the SpecBackend API key) to
``projects.project_id``; a NativeBackend instance is scoped to one project.

TENANT ISOLATION [AC-05]
========================
Every read and write filters by ``project_id``. The ``board_id`` argument of
the SpecBackend API maps directly to ``projects.project_id``. There is no
query in this module that touches a row of another tenant — the project_id
predicate is present in every WHERE clause, including UPDATE and DELETE.

OPTIMISTIC CONCURRENCY [AC-03] — how ``expected_version`` is passed
===================================================================
The SpecBackend ABC signatures for ``update_item`` /
``update_acceptance_criterion`` have no version parameter, and they are
frozen (other backends must not break). Adding a required parameter is not
allowed. We therefore pass the caller's expected version **through the
existing ``meta`` dict** under the reserved key ``"expected_version"``:

    await backend.update_item(board_id, item_id, name="...",
                              meta={"expected_version": 2})

This keeps the ABC contract byte-for-byte identical (other backends simply
ignore the extra meta key — FreeForm merges it harmlessly into stored meta,
which is why we strip it before persisting here). When the key is present:

- The UPDATE carries ``... AND version = $expected``.
- Every successful UPDATE sets ``version = version + 1``.
- If 0 rows are affected but the row exists (with a different version), a
  :class:`StaleVersionError` is raised and the row is left UNCHANGED.

When the key is absent, the UPDATE is a plain last-writer-wins that still
increments ``version`` (so readers can detect concurrent edits next time).

JSONB
=====
``labels`` and ``meta`` are JSONB. asyncpg returns JSONB as ``str`` unless a
codec is configured; rather than mutating the shared pool, this module
serializes with :func:`json.dumps` on write (passing the encoded string and
casting with ``$n::jsonb`` in SQL) and decodes with :func:`json.loads` on
read. One approach, applied consistently.

Out of scope (later cycles): wiring into ``auth_gateway.py`` / ``server.py``
(UC-103). This module is only required to be importable and correct.
"""

from __future__ import annotations

import json
import re
from typing import Any

import asyncpg
import structlog

from ..db.pool import get_pool
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


class StaleVersionError(Exception):
    """Raised when an optimistic-concurrency UPDATE is rejected.

    The caller supplied ``meta["expected_version"]`` but the row's current
    ``version`` differs (a concurrent writer won the race). The row is NOT
    mutated. Carries STALE_VERSION semantics so dispatch (UC-103) can map it
    to a stable error code for clients.
    """

    code = "STALE_VERSION"

    def __init__(
        self,
        item_id: str,
        expected_version: int,
        actual_version: int,
    ) -> None:
        self.item_id = item_id
        self.expected_version = expected_version
        self.actual_version = actual_version
        super().__init__(
            f"Stale version for item {item_id!r}: expected {expected_version}, "
            f"found {actual_version}. The row was not modified."
        )


# ── Constants (mirror FreeformBackend / spec_backend semantics) ──────

NATIVE_STATES: dict[str, str] = {
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

#: Reserved meta key used to pass the optimistic-concurrency expected version
#: without changing the frozen ABC signatures. Stripped before persisting.
_EXPECTED_VERSION_KEY = "expected_version"


# ── Helpers ──────────────────────────────────────────────────────────


def _detect_item_type(name: str) -> str:
    """Detect US/UC/AC from name prefix (mirrors FreeformBackend)."""
    if re.match(r"\[?US-\d+", name):
        return "US"
    if re.match(r"\[?UC-\d+", name):
        return "UC"
    if re.match(r"\[?AC-\d+", name):
        return "AC"
    return ""


def _jsonb(value: Any) -> str:
    """Serialize a Python value for a ``$n::jsonb`` parameter."""
    return json.dumps(value, ensure_ascii=False)


def _from_jsonb(value: Any) -> Any:
    """Decode a JSONB column. asyncpg returns ``str`` by default."""
    if value is None:
        return None
    if isinstance(value, (str, bytes, bytearray)):
        return json.loads(value)
    # Already decoded (a json codec was configured upstream) — pass through.
    return value


def _split_expected_version(
    meta: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, int | None]:
    """Extract the reserved ``expected_version`` from a meta dict.

    Returns ``(clean_meta, expected_version)``. ``clean_meta`` has the
    reserved key removed so it never gets persisted. If meta is None or has
    no expected version, returns ``(meta, None)``.
    """
    if not meta or _EXPECTED_VERSION_KEY not in meta:
        return meta, None
    clean = {k: v for k, v in meta.items() if k != _EXPECTED_VERSION_KEY}
    raw = meta[_EXPECTED_VERSION_KEY]
    expected = int(raw) if raw is not None else None
    # If the only key was expected_version, treat meta as "no field changes".
    return (clean if clean else None), expected


# ── NativeBackend ────────────────────────────────────────────────────


class NativeBackend(SpecBackend):
    """SpecBackend implementation backed by Postgres (asyncpg + UC-102 schema).

    Scoped to a single project (tenant). ``board_id`` in the API maps to
    ``projects.project_id``; the constructor's ``project_id`` is the default
    used when a method's ``board_id`` is not the canonical one — but every
    method honours the ``board_id`` it is given so the instance can serve any
    project it is asked about while still filtering by tenant.
    """

    def __init__(self, project_id: str, dev_token: str) -> None:
        """Initialize the backend scoped to a project + a developer session.

        Args:
            project_id: The tenant root id (``projects.project_id``). NEVER a
                DSN or credential — the connection comes from
                :func:`server.db.pool.get_pool`.
            dev_token: The developer's MCP token (clear form). Used by UC-502
                to re-validate identity + membership on every mutation via the
                cached gate. Cannot be empty: an empty token is the same as
                no token, and the gate would always raise UNAUTHENTICATED — we
                fail fast at construction instead [UC-505 AC-01].

        Raises:
            ValueError: If ``project_id`` or ``dev_token`` is empty / falsy.
        """
        if not project_id:
            raise ValueError("project_id is required for NativeBackend")
        if not dev_token:
            raise ValueError("dev_token is required for NativeBackend")
        self.project_id = project_id
        self._dev_token = dev_token

    # ── Pool access ──────────────────────────────────────────────

    async def _pool(self) -> asyncpg.Pool:
        return await get_pool()

    # ── Row -> DTO mapping ───────────────────────────────────────

    def _us_row_to_dto(self, row: asyncpg.Record) -> ItemDTO:
        labels = _from_jsonb(row["labels"]) or []
        meta = _from_jsonb(row["meta"]) or {}
        meta = {**meta, "tipo": "US", "version": row["version"]}
        return ItemDTO(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            state=row["state"],
            state_id=row["state"],
            parent_id=None,
            labels=labels,
            label_ids=labels,
            priority=row["priority"],
            url="",
            external_source=row["external_source"],
            external_id=row["external_id"],
            meta=meta,
            raw=dict(row),
        )

    def _uc_row_to_dto(self, row: asyncpg.Record) -> ItemDTO:
        labels = _from_jsonb(row["labels"]) or []
        meta = _from_jsonb(row["meta"]) or {}
        extra: dict[str, Any] = {"tipo": "UC", "version": row["version"]}
        if row["us_id"]:
            extra["us_id"] = row["us_id"]
        meta = {**meta, **extra}
        return ItemDTO(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            state=row["state"],
            state_id=row["state"],
            parent_id=row["us_id"],
            labels=labels,
            label_ids=labels,
            priority=row["priority"],
            url="",
            external_source=row["external_source"],
            external_id=row["external_id"],
            meta=meta,
            raw=dict(row),
        )

    def _ac_row_to_item_dto(self, row: asyncpg.Record) -> ItemDTO:
        """Map an acceptance_criteria row to an ItemDTO (for list_items / children)."""
        meta = _from_jsonb(row["meta"]) or {}
        meta = {
            **meta,
            "tipo": "AC",
            "ac_id": row["ac_id"],
            "version": row["version"],
        }
        return ItemDTO(
            id=row["id"],
            name=f"[{row['ac_id']}] {row['text']}",
            description="",
            state="done" if row["done"] else "backlog",
            state_id="done" if row["done"] else "backlog",
            parent_id=row["uc_id"],
            labels=["AC"],
            label_ids=["AC"],
            priority="none",
            url="",
            meta=meta,
            raw=dict(row),
        )

    # ── SpecBackend: Auth ────────────────────────────────────────

    async def validate_auth(self) -> BackendUser:
        # Connectivity check doubles as auth validation: if the pool opens, the
        # env DSN is valid. No per-user identity in the native backend.
        pool = await self._pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return BackendUser(
            id="native",
            username="native",
            display_name="Native (Postgres)",
        )

    # ── SpecBackend: Board / Project Setup ───────────────────────

    async def setup_board(self, name: str) -> BoardConfig:
        """Create (or upsert) the project row. board_id == project_id."""
        board_id = self.project_id
        board_url = f"native://{board_id}"
        pool = await self._pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO projects (project_id, name, backend_type, board_url, meta)
                VALUES ($1, $2, 'native', $3, '{}'::jsonb)
                ON CONFLICT (project_id) DO UPDATE
                    SET name = EXCLUDED.name,
                        board_url = EXCLUDED.board_url,
                        updated_at = now()
                """,
                board_id,
                name,
                board_url,
            )
        return BoardConfig(
            board_id=board_id,
            board_url=board_url,
            states=dict(NATIVE_STATES),
            labels=dict(_DEFAULT_LABELS),
            custom_fields={},
        )

    async def get_board_name(self, board_id: str) -> str:
        pool = await self._pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT name FROM projects WHERE project_id = $1",
                board_id,
            )
        return row["name"] if row else "Native Project"

    # ── SpecBackend: Items (CRUD) ────────────────────────────────

    async def list_items(self, board_id: str) -> list[ItemDTO]:
        pool = await self._pool()
        async with pool.acquire() as conn:
            us_rows = await conn.fetch(
                "SELECT * FROM user_stories WHERE project_id = $1 ORDER BY id",
                board_id,
            )
            uc_rows = await conn.fetch(
                "SELECT * FROM use_cases WHERE project_id = $1 ORDER BY id",
                board_id,
            )
            ac_rows = await conn.fetch(
                "SELECT * FROM acceptance_criteria WHERE project_id = $1 ORDER BY id",
                board_id,
            )
        items: list[ItemDTO] = []
        items.extend(self._us_row_to_dto(r) for r in us_rows)
        items.extend(self._uc_row_to_dto(r) for r in uc_rows)
        items.extend(self._ac_row_to_item_dto(r) for r in ac_rows)
        return items

    async def get_item(self, board_id: str, item_id: str) -> ItemDTO:
        pool = await self._pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM user_stories WHERE project_id = $1 AND id = $2",
                board_id,
                item_id,
            )
            if row:
                return self._us_row_to_dto(row)
            row = await conn.fetchrow(
                "SELECT * FROM use_cases WHERE project_id = $1 AND id = $2",
                board_id,
                item_id,
            )
            if row:
                return self._uc_row_to_dto(row)
            row = await conn.fetchrow(
                "SELECT * FROM acceptance_criteria WHERE project_id = $1 AND id = $2",
                board_id,
                item_id,
            )
            if row:
                return self._ac_row_to_item_dto(row)
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
        labels = list(labels or [])
        meta = dict(meta or {})

        item_type = _detect_item_type(name)
        if item_type and item_type not in labels:
            labels.insert(0, item_type)

        parsed_id, _ = parse_item_id(name, item_type) if item_type else ("", name)
        if item_type and parsed_id:
            meta[f"{item_type.lower()}_id"] = parsed_id
            meta["tipo"] = item_type

        # The DB id follows the spec id (US-xx / UC-xxx). For ACs created via
        # create_item the id is namespaced under the parent UC.
        if item_type == "US":
            item_id = parsed_id or name
            return await self._insert_us(
                conn_board=board_id,
                item_id=item_id,
                name=name,
                description=description,
                state=state or "user_stories",
                labels=labels,
                priority=priority,
                external_source=external_source,
                external_id=external_id,
                meta=meta,
            )
        if item_type == "UC":
            item_id = parsed_id or name
            return await self._insert_uc(
                board_id=board_id,
                item_id=item_id,
                us_id=parent_id,
                name=name,
                description=description,
                state=state,
                labels=labels,
                priority=priority,
                external_source=external_source,
                external_id=external_id,
                meta=meta,
            )
        if item_type == "AC":
            if not parent_id:
                raise ValueError("Creating an AC via create_item requires parent_id (the UC id)")
            ac_short = parsed_id or name
            db_id = f"{parent_id}::{ac_short}"
            _, text = parse_item_id(name, "AC")
            return await self._insert_ac(
                board_id=board_id,
                db_id=db_id,
                uc_id=parent_id,
                ac_id=ac_short,
                text=text or name,
                done=state == "done",
                meta=meta,
            )
        raise ValueError(
            f"Cannot determine item type from name {name!r}. Native items must be named with a US-/UC-/AC- prefix."
        )

    async def _insert_us(
        self,
        *,
        conn_board: str,
        item_id: str,
        name: str,
        description: str,
        state: str,
        labels: list[str],
        priority: str,
        external_source: str,
        external_id: str,
        meta: dict[str, Any],
    ) -> ItemDTO:
        pool = await self._pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO user_stories
                    (id, project_id, name, description, state, labels, priority,
                     external_source, external_id, meta)
                VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9, $10::jsonb)
                RETURNING *
                """,
                item_id,
                conn_board,
                name,
                description,
                state,
                _jsonb(labels),
                priority,
                external_source,
                external_id,
                _jsonb(meta),
            )
        logger.info("native_item_created", item_id=item_id, type="US")
        return self._us_row_to_dto(row)

    async def _insert_uc(
        self,
        *,
        board_id: str,
        item_id: str,
        us_id: str | None,
        name: str,
        description: str,
        state: str,
        labels: list[str],
        priority: str,
        external_source: str,
        external_id: str,
        meta: dict[str, Any],
    ) -> ItemDTO:
        pool = await self._pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO use_cases
                    (id, project_id, us_id, name, description, state, labels,
                     priority, external_source, external_id, meta)
                VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8, $9, $10, $11::jsonb)
                RETURNING *
                """,
                item_id,
                board_id,
                us_id,
                name,
                description,
                state,
                _jsonb(labels),
                priority,
                external_source,
                external_id,
                _jsonb(meta),
            )
        logger.info("native_item_created", item_id=item_id, type="UC")
        return self._uc_row_to_dto(row)

    async def _insert_ac(
        self,
        *,
        board_id: str,
        db_id: str,
        uc_id: str,
        ac_id: str,
        text: str,
        done: bool,
        meta: dict[str, Any],
    ) -> ItemDTO:
        pool = await self._pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO acceptance_criteria
                    (id, project_id, uc_id, ac_id, text, done, meta)
                VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
                RETURNING *
                """,
                db_id,
                board_id,
                uc_id,
                ac_id,
                text,
                done,
                _jsonb(meta),
            )
        logger.info("native_item_created", item_id=db_id, type="AC")
        return self._ac_row_to_item_dto(row)

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
        """Update a US or UC. Increments ``version`` on success.

        Optimistic concurrency: pass ``meta={"expected_version": N}`` to make
        the UPDATE guarded by ``version = N``. On a version mismatch (row
        exists, different version) a :class:`StaleVersionError` is raised and
        the row is unchanged. See the module docstring.
        """
        clean_meta, expected = _split_expected_version(meta)

        # Determine which table holds the item.
        pool = await self._pool()
        async with pool.acquire() as conn:
            table = await self._locate_us_or_uc(conn, board_id, item_id)
            if table is None:
                raise ValueError(f"Item {item_id} not found")

            set_clauses: list[str] = []
            params: list[Any] = []

            def add(expr_template: str, value: Any) -> None:
                """Append a param and a SET fragment.

                ``expr_template`` uses ``{p}`` as the placeholder for the
                positional parameter (e.g. ``"name = {p}"`` or
                ``"meta = meta || {p}::jsonb"``).
                """
                params.append(value)
                set_clauses.append(expr_template.format(p=f"${len(params)}"))

            if name is not None:
                add("name = {p}", name)
            if description is not None:
                add("description = {p}", description)
            if state is not None:
                add("state = {p}", state)
            if labels is not None:
                add("labels = {p}::jsonb", _jsonb(labels))
            if priority is not None:
                add("priority = {p}", priority)
            if external_source is not None:
                add("external_source = {p}", external_source)
            if external_id is not None:
                add("external_id = {p}", external_id)
            if table == "use_cases" and parent_id is not None:
                add("us_id = {p}", parent_id)
            if clean_meta is not None:
                # MERGE into existing meta (mirror FreeForm's update semantics).
                add("meta = meta || {p}::jsonb", _jsonb(clean_meta))

            # Always bump version + updated_at on a successful UPDATE.
            set_clauses.append("version = version + 1")
            set_clauses.append("updated_at = now()")

            params.append(board_id)
            board_param = f"${len(params)}"
            params.append(item_id)
            id_param = f"${len(params)}"

            where = f"project_id = {board_param} AND id = {id_param}"
            if expected is not None:
                params.append(expected)
                where += f" AND version = ${len(params)}"

            sql = f"UPDATE {table} SET {', '.join(set_clauses)} WHERE {where} RETURNING *"

            row = await conn.fetchrow(sql, *params)
            if row is None:
                await self._raise_if_stale(conn, table, board_id, item_id, expected)
                # No expected version but still no row → row vanished mid-update.
                raise ValueError(f"Item {item_id} not found")

        return self._us_row_to_dto(row) if table == "user_stories" else self._uc_row_to_dto(row)

    async def _locate_us_or_uc(self, conn: asyncpg.Connection, board_id: str, item_id: str) -> str | None:
        """Return the table name holding the item, or None."""
        exists_us = await conn.fetchval(
            "SELECT 1 FROM user_stories WHERE project_id = $1 AND id = $2",
            board_id,
            item_id,
        )
        if exists_us:
            return "user_stories"
        exists_uc = await conn.fetchval(
            "SELECT 1 FROM use_cases WHERE project_id = $1 AND id = $2",
            board_id,
            item_id,
        )
        if exists_uc:
            return "use_cases"
        return None

    async def _raise_if_stale(
        self,
        conn: asyncpg.Connection,
        table: str,
        board_id: str,
        item_id: str,
        expected: int | None,
    ) -> None:
        """Raise StaleVersionError if the row exists with a different version."""
        if expected is None:
            return
        # Table name is from a fixed allow-list (set internally), never user input.
        actual = await conn.fetchval(
            f"SELECT version FROM {table} WHERE project_id = $1 AND id = $2",
            board_id,
            item_id,
        )
        if actual is not None:
            raise StaleVersionError(item_id, expected, actual)

    async def find_item_by_field(self, board_id: str, field_name: str, value: str) -> ItemDTO | None:
        # us_id / uc_id / ac_id resolve directly to the primary key (id) of the
        # respective table. Other fields fall back to a meta scan over list_items.
        if field_name == "us_id":
            pool = await self._pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM user_stories WHERE project_id = $1 AND id = $2",
                    board_id,
                    value,
                )
            return self._us_row_to_dto(row) if row else None
        if field_name == "uc_id":
            pool = await self._pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM use_cases WHERE project_id = $1 AND id = $2",
                    board_id,
                    value,
                )
            return self._uc_row_to_dto(row) if row else None
        if field_name == "ac_id":
            pool = await self._pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM acceptance_criteria WHERE project_id = $1 AND ac_id = $2 LIMIT 1",
                    board_id,
                    value,
                )
            return self._ac_row_to_item_dto(row) if row else None

        # Generic fallback: scan items for a matching meta field or label.
        items = await self.list_items(board_id)
        for item in items:
            if field_name == "tipo":
                if value in item.labels:
                    return item
            elif item.meta.get(field_name) == value:
                return item
        return None

    async def get_item_children(self, board_id: str, parent_id: str) -> list[ItemDTO]:
        pool = await self._pool()
        async with pool.acquire() as conn:
            # Children of a US are UCs; children of a UC are ACs.
            uc_rows = await conn.fetch(
                "SELECT * FROM use_cases WHERE project_id = $1 AND us_id = $2 ORDER BY id",
                board_id,
                parent_id,
            )
            ac_rows = await conn.fetch(
                "SELECT * FROM acceptance_criteria WHERE project_id = $1 AND uc_id = $2 ORDER BY id",
                board_id,
                parent_id,
            )
        children: list[ItemDTO] = []
        children.extend(self._uc_row_to_dto(r) for r in uc_rows)
        children.extend(self._ac_row_to_item_dto(r) for r in ac_rows)
        return children

    # ── SpecBackend: Acceptance Criteria ─────────────────────────

    async def get_acceptance_criteria(self, board_id: str, uc_item_id: str) -> list[ChecklistItemDTO]:
        pool = await self._pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM acceptance_criteria WHERE project_id = $1 AND uc_id = $2 ORDER BY id",
                board_id,
                uc_item_id,
            )
        return [
            ChecklistItemDTO(
                id=r["ac_id"],
                text=r["text"],
                done=r["done"],
                backend_id=r["id"],
            )
            for r in rows
        ]

    async def mark_acceptance_criterion(
        self,
        board_id: str,
        uc_item_id: str,
        ac_id: str,
        passed: bool,
    ) -> ChecklistItemDTO:
        pool = await self._pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE acceptance_criteria
                SET done = $4, version = version + 1, updated_at = now()
                WHERE project_id = $1 AND uc_id = $2 AND ac_id = $3
                RETURNING *
                """,
                board_id,
                uc_item_id,
                ac_id,
                passed,
            )
        if row is None:
            raise ValueError(f"AC '{ac_id}' not found as child of '{uc_item_id}'")
        return ChecklistItemDTO(
            id=ac_id,
            text=row["text"],
            done=row["done"],
            backend_id=row["id"],
        )

    async def create_acceptance_criteria(
        self,
        board_id: str,
        uc_item_id: str,
        criteria: list[tuple[str, str]],
    ) -> list[ChecklistItemDTO]:
        result: list[ChecklistItemDTO] = []
        pool = await self._pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                for ac_id, text in criteria:
                    db_id = f"{uc_item_id}::{ac_id}"
                    row = await conn.fetchrow(
                        """
                        INSERT INTO acceptance_criteria
                            (id, project_id, uc_id, ac_id, text, done, meta)
                        VALUES ($1, $2, $3, $4, $5, false, $6::jsonb)
                        RETURNING *
                        """,
                        db_id,
                        board_id,
                        uc_item_id,
                        ac_id,
                        text,
                        _jsonb({"ac_id": ac_id, "tipo": "AC"}),
                    )
                    result.append(
                        ChecklistItemDTO(
                            id=ac_id,
                            text=text,
                            done=False,
                            backend_id=row["id"],
                        )
                    )
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
        """Update an AC's text and/or done state. Increments ``version``.

        Optimistic concurrency: the ABC signature has no meta param here, so an
        expected version is passed positionally is impossible. Callers that
        need the stale check route through ``update_item`` semantics is N/A for
        ACs; instead an optional behaviour is offered: when neither field is
        provided we no-op-return the current row. The version is still bumped on
        any real change so concurrent edits remain detectable on the next read.
        """
        if text is None and done is None:
            # Nothing to change — return current state without bumping version.
            pool = await self._pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM acceptance_criteria WHERE project_id = $1 AND uc_id = $2 AND ac_id = $3",
                    board_id,
                    uc_item_id,
                    ac_id,
                )
            if row is None:
                raise ValueError(f"AC '{ac_id}' not found as child of '{uc_item_id}'")
            return ChecklistItemDTO(id=ac_id, text=row["text"], done=row["done"], backend_id=row["id"])

        set_clauses: list[str] = []
        params: list[Any] = []
        if text is not None:
            params.append(text)
            set_clauses.append(f"text = ${len(params)}")
        if done is not None:
            params.append(done)
            set_clauses.append(f"done = ${len(params)}")
        set_clauses.append("version = version + 1")
        set_clauses.append("updated_at = now()")

        params.append(board_id)
        board_param = f"${len(params)}"
        params.append(uc_item_id)
        uc_param = f"${len(params)}"
        params.append(ac_id)
        ac_param = f"${len(params)}"

        sql = (
            f"UPDATE acceptance_criteria SET {', '.join(set_clauses)} "
            f"WHERE project_id = {board_param} AND uc_id = {uc_param} "
            f"AND ac_id = {ac_param} RETURNING *"
        )
        pool = await self._pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(sql, *params)
        if row is None:
            raise ValueError(f"AC '{ac_id}' not found as child of '{uc_item_id}'")
        return ChecklistItemDTO(id=ac_id, text=row["text"], done=row["done"], backend_id=row["id"])

    async def delete_acceptance_criterion(
        self,
        board_id: str,
        uc_item_id: str,
        ac_id: str,
    ) -> None:
        pool = await self._pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM acceptance_criteria WHERE project_id = $1 AND uc_id = $2 AND ac_id = $3",
                board_id,
                uc_item_id,
                ac_id,
            )
        # asyncpg returns e.g. 'DELETE 1'
        if result.split()[-1] == "0":
            raise ValueError(f"AC '{ac_id}' not found as child of '{uc_item_id}'")

    # ── SpecBackend: Archival ────────────────────────────────────

    async def archive_item(
        self,
        board_id: str,
        item_id: str,
        *,
        reason: str,
    ) -> dict[str, Any]:
        """Archive by stamping meta and moving state to a terminal 'archived'.

        Native has no separate archive table in UC-102 scope; we record the
        archival in the item's meta and set state to 'archived' so it falls out
        of active queries while remaining recoverable.
        """
        from datetime import datetime, timezone

        archived_at = datetime.now(timezone.utc).isoformat()
        pool = await self._pool()
        async with pool.acquire() as conn:
            table = await self._locate_us_or_uc(conn, board_id, item_id)
            if table is None:
                # Maybe an AC.
                ac = await conn.fetchval(
                    "SELECT 1 FROM acceptance_criteria WHERE project_id = $1 AND id = $2",
                    board_id,
                    item_id,
                )
                if ac:
                    await conn.execute(
                        """
                        UPDATE acceptance_criteria
                        SET meta = meta || $3::jsonb, version = version + 1, updated_at = now()
                        WHERE project_id = $1 AND id = $2
                        """,
                        board_id,
                        item_id,
                        _jsonb({"archived_at": archived_at, "archive_reason": reason}),
                    )
                    return {"archive_location": "meta", "archived_at": archived_at}
                raise ValueError(f"Item '{item_id}' not found")

            await conn.execute(
                f"""
                UPDATE {table}
                SET state = 'archived',
                    meta = meta || $3::jsonb,
                    version = version + 1,
                    updated_at = now()
                WHERE project_id = $1 AND id = $2
                """,
                board_id,
                item_id,
                _jsonb({"archived_at": archived_at, "archive_reason": reason}),
            )
        return {"archive_location": "state=archived", "archived_at": archived_at}

    # ── SpecBackend: Comments ────────────────────────────────────
    #
    # UC-102 schema has no comments table. Comments are stored in the item's
    # meta under a "comments" list — append-only, mirroring FreeForm's jsonl.

    async def add_comment(self, board_id: str, item_id: str, text: str) -> CommentDTO:
        from datetime import datetime, timezone

        created_at = datetime.now(timezone.utc).isoformat()
        comment = {"text": text, "created_at": created_at, "author": "native"}
        pool = await self._pool()
        async with pool.acquire() as conn:
            table = await self._locate_table_any(conn, board_id, item_id)
            if table is None:
                raise ValueError(f"Item '{item_id}' not found")
            await conn.execute(
                f"""
                UPDATE {table}
                SET meta = jsonb_set(
                        meta,
                        '{{comments}}',
                        COALESCE(meta->'comments', '[]'::jsonb) || $3::jsonb
                    ),
                    updated_at = now()
                WHERE project_id = $1 AND id = $2
                """,
                board_id,
                item_id,
                _jsonb([comment]),
            )
        return CommentDTO(id="", text=text, created_at=created_at, author="native")

    async def get_comments(self, board_id: str, item_id: str) -> list[CommentDTO]:
        pool = await self._pool()
        async with pool.acquire() as conn:
            table = await self._locate_table_any(conn, board_id, item_id)
            if table is None:
                return []
            raw = await conn.fetchval(
                f"SELECT meta->'comments' FROM {table} WHERE project_id = $1 AND id = $2",
                board_id,
                item_id,
            )
        comments = _from_jsonb(raw) or []
        return [
            CommentDTO(
                id="",
                text=c.get("text", ""),
                created_at=c.get("created_at", ""),
                author=c.get("author", ""),
            )
            for c in comments
        ]

    async def _locate_table_any(self, conn: asyncpg.Connection, board_id: str, item_id: str) -> str | None:
        """Locate the table holding an item across all three tables."""
        table = await self._locate_us_or_uc(conn, board_id, item_id)
        if table is not None:
            return table
        ac = await conn.fetchval(
            "SELECT 1 FROM acceptance_criteria WHERE project_id = $1 AND id = $2",
            board_id,
            item_id,
        )
        return "acceptance_criteria" if ac else None

    # ── SpecBackend: Attachments / Evidence ──────────────────────
    #
    # UC-102 has no blob storage. Native stores attachment *references* (URL +
    # metadata) in the item meta under "attachments"; raw bytes are not held in
    # Postgres. add_attachment records the reference; content is expected to be
    # persisted out-of-band by the caller (UC-103 wiring decides where).

    async def add_attachment(
        self,
        board_id: str,
        item_id: str,
        filename: str,
        content: bytes,
        mime_type: str = "application/pdf",
    ) -> AttachmentDTO:
        from datetime import datetime, timezone

        created_at = datetime.now(timezone.utc).isoformat()
        url = f"native://{board_id}/{item_id}/{filename}"
        att: dict[str, Any] = {
            "name": filename,
            "url": url,
            "size": len(content),
            "created_at": created_at,
            "mime_type": mime_type,
        }
        pool = await self._pool()
        async with pool.acquire() as conn:
            table = await self._locate_table_any(conn, board_id, item_id)
            if table is None:
                raise ValueError(f"Item '{item_id}' not found")
            await conn.execute(
                f"""
                UPDATE {table}
                SET meta = jsonb_set(
                        meta,
                        '{{attachments}}',
                        COALESCE(meta->'attachments', '[]'::jsonb) || $3::jsonb
                    ),
                    updated_at = now()
                WHERE project_id = $1 AND id = $2
                """,
                board_id,
                item_id,
                _jsonb([att]),
            )
        return AttachmentDTO(
            id="",
            name=filename,
            url=url,
            size=len(content),
            created_at=created_at,
            mime_type=mime_type,
        )

    async def get_attachments(self, board_id: str, item_id: str) -> list[AttachmentDTO]:
        pool = await self._pool()
        async with pool.acquire() as conn:
            table = await self._locate_table_any(conn, board_id, item_id)
            if table is None:
                return []
            raw = await conn.fetchval(
                f"SELECT meta->'attachments' FROM {table} WHERE project_id = $1 AND id = $2",
                board_id,
                item_id,
            )
        atts = _from_jsonb(raw) or []
        return [
            AttachmentDTO(
                id="",
                name=a.get("name", ""),
                url=a.get("url", ""),
                size=a.get("size", 0),
                created_at=a.get("created_at", ""),
                mime_type=a.get("mime_type", ""),
            )
            for a in atts
        ]

    # ── SpecBackend: Modules ─────────────────────────────────────

    async def create_module(self, board_id: str, name: str, description: str = "") -> ModuleDTO:
        """Modules are implicit in Native (hierarchy via us_id). Returns a stub."""
        return ModuleDTO(id=f"mod-{name}", name=name, status="planned")

    async def add_items_to_module(self, board_id: str, module_id: str, item_ids: list[str]) -> None:
        """No-op — Native hierarchy is via us_id FK, not modules."""
        return None

    # ── SpecBackend: Labels ──────────────────────────────────────
    #
    # Labels are not a separate entity in UC-102; they live inline in each
    # item's labels JSONB. We expose the project's known label palette via the
    # project's meta["labels"], seeded with the defaults.

    async def create_label(self, board_id: str, name: str, color: str) -> dict[str, str]:
        pool = await self._pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE projects
                SET meta = jsonb_set(
                        meta,
                        '{labels}',
                        COALESCE(meta->'labels', '{}'::jsonb) || $2::jsonb
                    ),
                    updated_at = now()
                WHERE project_id = $1
                """,
                board_id,
                _jsonb({name: color}),
            )
        return {"name": name, "id": name, "color": color}

    async def get_labels(self, board_id: str) -> list[dict[str, str]]:
        pool = await self._pool()
        async with pool.acquire() as conn:
            raw = await conn.fetchval(
                "SELECT meta->'labels' FROM projects WHERE project_id = $1",
                board_id,
            )
        stored = _from_jsonb(raw) or {}
        merged = {**_DEFAULT_LABELS, **stored}
        return [{"name": k, "id": k, "color": v} for k, v in merged.items()]

    # ── SpecBackend: States ──────────────────────────────────────

    async def get_state_id(self, board_id: str, state: str) -> str:
        return NATIVE_STATES.get(state, "backlog")

    async def get_states(self, board_id: str) -> dict[str, str]:
        return dict(NATIVE_STATES)

    # ── SpecBackend: Cleanup ─────────────────────────────────────

    async def close(self) -> None:
        """No-op — the shared asyncpg pool is owned by server.db.pool, not by
        this instance. Closing it here would break other backends sharing it.
        """
        return None
