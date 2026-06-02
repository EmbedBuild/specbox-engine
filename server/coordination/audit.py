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


async def record_destructive(
    conn: asyncpg.Connection,
    *,
    developer_id: str | None,
    project_id: str,
    operation: str,
    target_id: str,
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
    """
    await conn.execute(
        """
        INSERT INTO audit_log (developer_id, project_id, operation, target_id)
        VALUES ($1, $2, $3, $4)
        """,
        developer_id,
        project_id,
        operation,
        target_id,
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
