"""A name from the client never leaves the folder it names a file in — US-107 · UC-10701.

The engine's read-only tools (plans, hooks, skills, agent prompts, architecture
and infra docs, quality baselines, evidence, session logs) take a name and
join it to a folder under the engine: ``plans_dir / plan_name``. With pathlib,
an absolute name replaces the folder and ``..`` climbs out of it, so on the
hosted MCP a caller without a token could read any file of the container —
``/proc/self/environ`` included, with the database credential (audit of
2026-10-27, ENG-S-01).

:func:`child_within` is the only way those tools turn a client name into a
path: the name must be one segment (no ``/``, ``\\``, NUL, ``.`` or ``..``) and
the resolved path must stay inside the folder, symlinks included. Anything
else is ``None``, which each tool answers like a name that does not exist.
``tests/test_remote_surface_inventory.py`` fails when a tool joins one of its
parameters to a path without it.
"""

from __future__ import annotations

from pathlib import Path

_FORBIDDEN = ("/", "\\", "\x00")


def child_within(base: Path, name: str) -> Path | None:
    """``base / name`` when ``name`` is a single segment that stays inside ``base``; else ``None``."""
    if not isinstance(name, str) or not name or name in (".", ".."):
        return None
    if any(ch in name for ch in _FORBIDDEN):
        return None
    candidate = base / name
    try:
        if not candidate.resolve().is_relative_to(base.resolve()):
            return None
    except (OSError, RuntimeError, ValueError):
        return None
    return candidate
