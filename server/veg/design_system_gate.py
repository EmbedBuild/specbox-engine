"""Design-system precondition gate for Claude Design (US-29 · UC-2903).

Claude Design designs with the **real compiled components** of a project's
design-system, so it only applies when such a design-system exists. *Where*
the design-system lives depends on the repo topology:

- **Multirepo orchestrator/satellite**: the design-system lives ONCE in the
  **orchestrator**. The Claude Design ``projectId`` is anchored there and its
  ``dist/`` is synced once; UI satellites (web, mobile, …) **consume** that
  same library (JR-CD.4).
- **Monorepo**: the design-system lives in the **repo itself** (JR-CD.5).

The gate resolves that site from ``multirepo`` settings, then checks whether a
**compiled** design-system is present there (``package.json`` AND ``dist/`` —
or a Storybook config). When it is not, the gate returns ``ready=False`` with
a human-readable reason so the VEG can mark ``claude_design`` as *pending*
(JR-CD.3) — it never raises.

This module is filesystem-aware but side-effect free: it only reads paths and
settings. It does not call DesignSync or the network.

Trazabilidad: Discovery ``disc-52cbe4033fae`` · US-29 · UC-2903.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .visual_provider import GateResult

Role = Literal["orchestrator", "satellite", "monorepo"]

# Markers that indicate a compiled / buildable design-system at a site.
_PACKAGE_MARKER = "package.json"
_DIST_MARKERS: tuple[str, ...] = ("dist", "storybook-static")
_STORYBOOK_MARKERS: tuple[str, ...] = (".storybook", "storybook.config.js")


@dataclass(frozen=True)
class SiteResolution:
    """Where the design-system should live for this project.

    - ``role`` is the resolved topology role.
    - ``site_path`` is the absolute path of the repo that owns the
      design-system (the orchestrator in multirepo, the repo itself in
      monorepo).
    - ``anchor_settings_path`` is the settings.local.json where the Claude
      Design ``projectId`` is anchored (always the orchestrator's in
      multirepo; the repo's own in monorepo).
    - ``consumes_from_orchestrator`` is ``True`` for a satellite: it reads the
      ``projectId`` from the orchestrator rather than creating its own
      (JR-CD.4).
    """

    role: Role
    site_path: Path
    anchor_settings_path: Path
    consumes_from_orchestrator: bool


def _read_multirepo(project_root: Path) -> dict[str, Any]:
    """Read the ``multirepo`` block from a repo's settings.local.json.

    Mirrors ``milestone_management._read_multirepo_settings`` but scoped to a
    repo root. Returns ``{}`` when missing or malformed (never raises).
    """
    settings = project_root / ".claude" / "settings.local.json"
    if not settings.exists():
        return {}
    try:
        data = json.loads(settings.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    mr = data.get("multirepo")
    return mr if isinstance(mr, dict) else {}


def resolve_site(project_root: str | Path) -> SiteResolution:
    """Resolve where the design-system lives for ``project_root``.

    - ``multirepo.role == "orchestrator"`` → site is this repo; anchor here
      (AC-01).
    - ``multirepo.role == "satellite"`` → site is the orchestrator, resolved
      from ``multirepo.orchestrator`` (a relative path such as ``../..`` in
      the nested layout). The satellite consumes the orchestrator's projectId
      (AC-02).
    - no ``multirepo`` / null role → monorepo: site is this repo (AC-03).
    """
    root = Path(project_root).resolve()
    mr = _read_multirepo(root)
    role = mr.get("role")

    if role == "orchestrator":
        return SiteResolution(
            role="orchestrator",
            site_path=root,
            anchor_settings_path=root / ".claude" / "settings.local.json",
            consumes_from_orchestrator=False,
        )

    if role == "satellite":
        # The orchestrator path is relative to the satellite root (nested
        # layout: ../.. ). Fall back to the repo itself if not declared.
        orch_rel = mr.get("orchestrator")
        if isinstance(orch_rel, str) and orch_rel:
            orch_path = (root / orch_rel).resolve()
        else:
            orch_path = root
        return SiteResolution(
            role="satellite",
            site_path=orch_path,
            anchor_settings_path=orch_path / ".claude" / "settings.local.json",
            consumes_from_orchestrator=True,
        )

    # Monorepo (no multirepo block or unrecognised role).
    return SiteResolution(
        role="monorepo",
        site_path=root,
        anchor_settings_path=root / ".claude" / "settings.local.json",
        consumes_from_orchestrator=False,
    )


def _has_compiled_design_system(site: Path) -> tuple[bool, str]:
    """Check for a compiled design-system at ``site``.

    Ready iff ``package.json`` exists AND (a ``dist/``-style build output OR a
    Storybook config) is present. Returns ``(ready, reason)``; ``reason`` is
    empty when ready, otherwise a precise, legible motive (AC-04, AC-05).
    """
    if not (site / _PACKAGE_MARKER).exists():
        return False, f"no compiled design-system at {site}: missing package.json"

    has_dist = any((site / d).is_dir() for d in _DIST_MARKERS)
    has_storybook = any((site / s).exists() for s in _STORYBOOK_MARKERS)
    if has_dist or has_storybook:
        return True, ""

    return (
        False,
        f"no compiled design-system at {site}: missing dist/ "
        "(build the design-system, or add a Storybook config)",
    )


def evaluate_gate(project_root: str | Path) -> tuple[GateResult, SiteResolution]:
    """Resolve the site and evaluate the design-system precondition.

    Returns a :class:`~server.veg.visual_provider.GateResult` (consumed by
    ``resolve_effective_provider``) and the :class:`SiteResolution` so callers
    know where to anchor/sync. Never raises — a missing design-system yields
    ``ready=False`` with a motive (JR-CD.3).
    """
    site = resolve_site(project_root)
    ready, reason = _has_compiled_design_system(site.site_path)
    return GateResult(ready=ready, reason=reason), site
