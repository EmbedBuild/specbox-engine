"""Session GUCs for the UC lifecycle triggers (US-12 / UC-1202).

The 0012 migration installs triggers on ``use_cases`` that capture every
state transition into ``uc_state_transitions``. The row itself carries the
WHAT and WHEN; the WHO and the cause live only in the application, so the
engine hands them to the triggers through two per-transaction GUCs:

* ``app.developer_id``  — the authenticated developer performing the mutation.
* ``app.change_source`` — ``'interactive'`` (default) | ``'import'`` |
  ``'backfill_estimate'``. Non-interactive sources must not count as
  implementation time: the BEFORE trigger skips ``started_at``/``completed_at``
  for them.

``set_config(..., is_local := true)`` is SET LOCAL: the value dies with the
transaction, so a pooled connection can never leak one caller's context into
the next. That is also why this helper MUST be called inside an open
transaction — outside one, the setting would apply only to the implicit
single-statement transaction of the ``SELECT set_config`` itself and the
triggers would read nothing.

Degradation is honest by design: a writer that does not call this helper
produces transitions with ``developer_id = NULL`` and ``source =
'interactive'`` — never an error (the triggers read with
``current_setting(..., true)``).
"""

from __future__ import annotations

import asyncpg

__all__ = ["set_lifecycle_context"]


async def set_lifecycle_context(
    conn: asyncpg.Connection,
    *,
    developer_id: str | None = None,
    source: str | None = None,
) -> None:
    """Set the per-transaction GUCs read by the 0012 lifecycle triggers.

    Args:
        conn: Connection with an OPEN transaction (see module docstring).
        developer_id: Authenticated developer id, or None to leave unset.
        source: Change source ('import', 'backfill_estimate'), or None to
            leave the trigger default ('interactive').
    """
    if developer_id is not None:
        await conn.execute(
            "SELECT set_config('app.developer_id', $1, true)", developer_id
        )
    if source is not None:
        await conn.execute(
            "SELECT set_config('app.change_source', $1, true)", source
        )
