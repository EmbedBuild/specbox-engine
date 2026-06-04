"""Audit log for destructive operations on the Native Backend (UC-503).

US-NATIVE-SECURITY closes the mutation window with a 30s cached gate, but a
30-second window of exposure remains by design. For irreversible operations
(``delete_acceptance_criterion``, ``archive_item``), we want a per-operation
trail so a SuperAdmin / panel operator can investigate and, if needed,
restore from a Supabase backup.

Scope is intentionally narrow:

* Only **successful** destructive operations are recorded — a DELETE that
  affected 0 rows is not destruction.
* Only **destructive** operations are recorded — creates, updates, marks,
  comments and attachments are reversible or trivially auditable from the
  current row state.
* Records only stable identifiers — ``developer_id``, ``project_id``,
  ``operation`` name, ``target_id``. No diff / before-after payload. Recovery
  is done from backups; the audit is the index, not the snapshot.

Frontier 2 inalterado: this module receives an already-built asyncpg
connection. It never reads a DSN, never logs the developer's token, and the
``developer_id`` it stores is the opaque identifier from ``developers`` —
never a token, never an email.
"""

from __future__ import annotations

import json
from typing import Any

import asyncpg
import structlog

logger = structlog.get_logger(__name__)


#: Canonical operation names persisted in ``audit_log.operation``. Kept as a
#: tuple of literals so callers can ``from server.coordination.audit import
#: OP_DELETE_AC`` without typo risk.
OP_DELETE_AC: str = "delete_acceptance_criterion"
OP_ARCHIVE_ITEM: str = "archive_item"
#: Non-destructive but audited: the engine provisioned a native tenant +
#: creator membership during a from-scratch migration (UC-820, decision D2).
#: ``target_id`` carries the project_id; ``developer_id`` the provisioned admin.
OP_PROVISION_PROJECT: str = "provision_project"

#: UC lifecycle events (US-05 / UC-506). Non-destructive but audited so the
#: Control Panel activity feed can show *coordination* — who reserved, released
#: or completed which UC — instead of only administrative/destructive events.
#: ``target_id`` carries the uc_id; ``developer_id`` the actor. Scope decision
#: (2026-06-04): UC lifecycle only, current schema, no migration. US/AC lifecycle
#: and a ``target_type``/``metadata`` column are intentionally deferred.
OP_RESERVE_UC: str = "reserve_uc"
OP_RELEASE_UC: str = "release_uc"
OP_COMPLETE_UC: str = "complete_uc"
#: Reserved for when a merge call-site exists (AC-02). No producer emits it yet;
#: defined so the contract is stable and the panel can map the verb in advance.
OP_MERGE: str = "merge"

#: Progress mutations (US-05 / UC-513). The realtime broadcast trigger fires on
#: INSERT to audit_log, so a UC's detail view only refreshes live when an audit
#: row appears. Marking an AC / editing US·UC·AC previously wrote NO audit row,
#: so the most frequent action while working a UC ("mark this AC done") did not
#: refresh the tree in real time. Emitting these here closes that gap via the
#: existing trigger + useProjectRealtime (no migration, no front change needed
#: for the refresh). The activity feed maps them to human verbs (UC-505).
#: ``target_id`` carries the ac_id / uc_id / us_id; ``developer_id`` the actor.
OP_MARK_AC: str = "mark_ac"
OP_UNMARK_AC: str = "unmark_ac"
OP_UPDATE_AC: str = "update_ac"
OP_UPDATE_UC: str = "update_uc"
OP_UPDATE_US: str = "update_us"

#: Creation events (US-05 / UC-706). Same gap as the progress mutations above,
#: but for *creation*: ``create_item`` (US/UC) and ``create_acceptance_criteria``
#: (AC) and ``import_spec`` wrote NO audit row, so seeding a US/UC/AC did not
#: refresh the Cloud panel live (had to reload). Emitting these closes that gap
#: via the existing ``audit_log_broadcast_change`` trigger. Granularity decision
#: (2026-06-04, UC-706): individual creates emit ONE event each (fine-grained
#: refresh); a bulk ``import_spec`` emits ONE aggregate ``OP_IMPORT_SPEC`` with
#: counts in ``metadata`` (NOT one per item) so a large seed doesn't flood the
#: feed with hundreds of rows. ``target_id`` carries the us_id/uc_id/ac_id (or
#: the project_id for import); ``developer_id`` the actor.
OP_CREATE_US: str = "create_us"
OP_CREATE_UC: str = "create_uc"
OP_CREATE_AC: str = "create_ac"
OP_IMPORT_SPEC: str = "import_spec"


async def record_destructive(
    conn: asyncpg.Connection,
    *,
    developer_id: str | None,
    project_id: str,
    operation: str,
    target_id: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Append one row to ``audit_log`` for a successful destructive operation.

    Callers must invoke this AFTER the SQL of the destructive operation has
    succeeded (e.g. the DELETE returned ``DELETE 1``, the UPDATE affected the
    expected row). Calling it before the SQL would record phantom events;
    calling it on a failed SQL would record events that did not happen.

    Args:
        conn: An open asyncpg connection. The audit insert reuses the
            caller's connection so it can participate in the same logical
            unit of work if the caller is in a transaction, but this module
            does NOT open its own transaction — the caller decides.
        developer_id: The id of the developer who performed the operation,
            as returned by the cached gate (UC-502). May be ``None`` only in
            the very narrow case where the caller wants to record an
            operation whose actor cannot be resolved — production callers in
            UC-503 always have a Developer object from
            ``_require_membership_cached`` and pass ``dev.developer_id``.
        project_id: The Native project_id (tenant root) the target belongs
            to. NEVER a DSN.
        operation: One of :data:`OP_DELETE_AC` / :data:`OP_ARCHIVE_ITEM`.
            Other strings are accepted (extensibility for future destructive
            ops) but production callers should reuse the canonical names.
        target_id: The id of the affected item (AC id, US/UC id, etc.).
        metadata: Optional JSON payload describing the operation (e.g. the
            provisioning case ``{"case": "created"}`` — UC-606). When ``None``
            the row keeps the table default ``{}`` and behaviour is unchanged.
    """
    await conn.execute(
        """
        INSERT INTO audit_log (developer_id, project_id, operation, target_id, metadata)
        VALUES ($1, $2, $3, $4, COALESCE($5::jsonb, '{}'::jsonb))
        """,
        developer_id,
        project_id,
        operation,
        target_id,
        json.dumps(metadata) if metadata is not None else None,
    )
    # Opaque ids only — never a token, never the diff. The audit row itself is
    # what enables forensics; this log line is just so the MCP operator sees
    # the trail in real time without querying the table.
    logger.info(
        "audit_destructive_recorded",
        developer_id=developer_id,
        project_id=project_id,
        operation=operation,
        target_id=target_id,
    )
