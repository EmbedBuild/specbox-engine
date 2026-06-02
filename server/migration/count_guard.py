"""Count guard for backend-switch executions (UC-811).

A migration/switch that writes to a real database (native/Cloud) must never run
off the wrong source. The dry-run reports ``read_counts`` (us/uc/ac); the
execute must carry a ``confirmed_count`` that matches. This module is the pure,
I/O-free decision layer:

* ``verify_count`` raises ``CountGuardError`` when the source is empty or when
  the confirmed count does not match what the preview read.

The orchestrator (UC-812) and the legacy execute paths call this before any
write so a 0-item read (path/content wrong) or a mismatch (client confirmed a
different shape than the preview) blocks the real migration.
"""

from __future__ import annotations

from typing import Any


class CountGuardError(RuntimeError):
    """Raised when an execute is refused on count grounds (AC-04 / AC-05)."""


def _normalize(counts: Any) -> dict[str, int]:
    """Coerce a counts payload to ``{us, uc}`` ints (ac is informational)."""
    if not isinstance(counts, dict):
        return {"us": 0, "uc": 0}
    return {"us": int(counts.get("us", 0) or 0), "uc": int(counts.get("uc", 0) or 0)}


def verify_count(
    read_counts: dict[str, int],
    confirmed_count: dict[str, int] | None,
) -> None:
    """Gate an execute against the preview's read counts.

    Args:
        read_counts: ``{us, uc, ac?}`` the preview actually read from the source.
        confirmed_count: ``{us, uc}`` the client confirmed before executing, or
            ``None`` when the client did not confirm.

    Raises:
        CountGuardError:
            * (AC-04) when ``us + uc == 0`` — the source read nothing, so the
              path/content is almost certainly wrong; never execute.
            * (AC-05) when ``confirmed_count`` is missing or its ``us``/``uc``
              do not match ``read_counts``.
    """
    read = _normalize(read_counts)
    if read["us"] + read["uc"] == 0:
        raise CountGuardError(
            "refusing to execute: dry-run read 0 items — source path/content "
            "likely wrong"
        )

    if confirmed_count is None:
        raise CountGuardError(
            f"count not confirmed: preview read {read['us']}/{read['uc']} "
            "(us/uc) — pass confirmed_count to execute"
        )

    confirmed = _normalize(confirmed_count)
    if confirmed != read:
        raise CountGuardError(
            f"count mismatch: preview read {read['us']}/{read['uc']}, execute "
            f"confirmed {confirmed['us']}/{confirmed['uc']}"
        )
