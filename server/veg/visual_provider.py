"""Visual provider abstraction for the VEG.

The VEG (Visual Engine Generation) historically generated UI through a
single provider: **Stitch** (text-to-design → HTML mockup → design-to-code).
This module introduces the concept of a *visual provider* so a project can
choose, per project, between:

- ``stitch``        — the existing text-to-mockup provider (default).
- ``claude_design`` — claude.ai/design, operated through the harness
  ``DesignSync`` tool. It designs with the **real compiled components** of
  the project's design-system (1:1 mapping to code), so it only applies when
  a compiled design-system exists (see ``design_system_gate``).

Design choice
-------------
The provider list lives in ``.claude/settings.local.json`` under
``veg.providers``. A project **without** that key resolves to ``["stitch"]``
— byte-for-byte the current behaviour, so legacy projects never break
(no-objetivo "no romper Stitch").

When both providers are active and a compiled design-system is present, the
**preferred** provider is ``claude_design`` (SpecBox is an agentic system for
Claude; the design platform should match the execution platform). Stitch
remains the fallback for the early phase without code, or when the gate is
not ready.

This module is intentionally pure: it parses config and resolves the
effective provider given a gate result. It does **not** call DesignSync,
Stitch, or touch the network. The gate lives in ``design_system_gate`` and
the MCP tools in ``server/tools/claude_design.py``.

Trazabilidad: Discovery ``disc-52cbe4033fae`` · US-29 · UC-2901.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

# The closed set of known visual providers. Adding a provider means adding it
# here AND wiring its generation path in /plan + /visual-setup.
VisualProvider = Literal["stitch", "claude_design"]

KNOWN_PROVIDERS: frozenset[str] = frozenset({"stitch", "claude_design"})

# A project with no veg.providers key behaves exactly like today.
DEFAULT_PROVIDERS: tuple[str, ...] = ("stitch",)


class VisualProviderConfigError(ValueError):
    """Raised when ``veg.providers`` contains an unknown provider.

    The message always names the offending value so the operator can fix the
    config without guessing (AC-01).
    """


@dataclass(frozen=True)
class GateResult:
    """Outcome of the design-system precondition gate (UC-2903).

    ``ready`` means a compiled design-system was found at the resolved site
    (orchestrator in multirepo, the repo itself in monorepo). ``reason`` is a
    human-readable explanation, populated when ``ready`` is ``False`` so the
    VEG can mark ``claude_design`` as *pending* with a motive instead of
    raising (AC of UC-2903).
    """

    ready: bool
    reason: str = ""


@dataclass(frozen=True)
class ResolvedProvider:
    """The effective provider choice for a generation run.

    - ``effective`` is the provider the VEG will use to design now.
    - ``fallback`` is the provider to fall back to (or ``None``).
    - ``claude_design_pending`` + ``pending_reason`` record the case where
      ``claude_design`` was requested but the gate was not ready, so the run
      proceeds with Stitch and the pending state is reported, never raised.
    """

    effective: VisualProvider
    fallback: VisualProvider | None = None
    claude_design_pending: bool = False
    pending_reason: str = ""


def parse_providers(settings: dict[str, Any] | None) -> list[str]:
    """Read and validate ``veg.providers`` from a settings dict.

    Accepts exactly ``["stitch"]``, ``["claude_design"]`` or both (in any
    order). A missing ``veg`` block or a missing ``providers`` key resolves to
    the default ``["stitch"]`` — identical to the current behaviour (AC-02).

    Any unknown provider raises :class:`VisualProviderConfigError` naming the
    offending value (AC-01). An empty list is also rejected — an explicit
    empty ``providers`` is a config mistake, not "use the default".
    """
    if not settings:
        return list(DEFAULT_PROVIDERS)

    veg = settings.get("veg")
    if not isinstance(veg, dict) or "providers" not in veg:
        return list(DEFAULT_PROVIDERS)

    providers = veg.get("providers")
    if not isinstance(providers, list) or not providers:
        raise VisualProviderConfigError(
            "veg.providers must be a non-empty list of "
            f"{sorted(KNOWN_PROVIDERS)}; got {providers!r}"
        )

    unknown = [p for p in providers if p not in KNOWN_PROVIDERS]
    if unknown:
        raise VisualProviderConfigError(
            f"veg.providers contains unknown provider(s) {unknown!r}; "
            f"allowed values are {sorted(KNOWN_PROVIDERS)}"
        )

    # De-duplicate while preserving first-seen order.
    seen: set[str] = set()
    ordered: list[str] = []
    for p in providers:
        if p not in seen:
            seen.add(p)
            ordered.append(p)
    return ordered


def resolve_effective_provider(
    providers: list[str],
    gate: GateResult | None,
) -> ResolvedProvider:
    """Resolve which provider the VEG should use given the gate outcome.

    Rules:

    - If ``claude_design`` is **not** requested → use ``stitch`` (the only
      other known provider today). No gate needed.
    - If ``claude_design`` **is** requested and the gate is ``ready`` →
      ``claude_design`` is preferred; ``stitch`` is the fallback when also
      present (AC-03, JR-CD.6).
    - If ``claude_design`` is requested but the gate is **not ready** → the
      effective provider is ``stitch`` (if requested) and ``claude_design`` is
      marked *pending* with the gate's reason. Never raises (JR-CD.3).
    - If only ``claude_design`` is requested and the gate is not ready → the
      effective provider is still reported as ``claude_design`` but pending,
      so the caller (e.g. /plan) can register the pending state and continue
      without generating.
    """
    wants_claude = "claude_design" in providers
    wants_stitch = "stitch" in providers

    if not wants_claude:
        # Only Stitch (or unknown-but-validated-away). Current behaviour.
        return ResolvedProvider(effective="stitch")

    gate_ready = bool(gate and gate.ready)
    if gate_ready:
        return ResolvedProvider(
            effective="claude_design",
            fallback="stitch" if wants_stitch else None,
        )

    # claude_design requested but gate not ready → pending, never raise.
    reason = gate.reason if gate else "design-system gate not evaluated"
    if wants_stitch:
        return ResolvedProvider(
            effective="stitch",
            fallback=None,
            claude_design_pending=True,
            pending_reason=reason,
        )
    # claude_design is the only requested provider: report it pending so the
    # caller can record the motive and skip generation (no Stitch fallback was
    # asked for).
    return ResolvedProvider(
        effective="claude_design",
        fallback=None,
        claude_design_pending=True,
        pending_reason=reason,
    )


def claude_design_config(settings: dict[str, Any] | None) -> dict[str, Any]:
    """Return the ``veg.claude_design`` config block (or an empty default).

    The block carries ``projectId`` (optional UUID — auto-created and
    persisted on first ``create_project``) and ``syncRepo`` (optional — the
    site whose ``dist/`` is synced). Absence resolves to an empty block so
    callers can read ``.get("projectId")`` safely (AC-04).
    """
    if not settings:
        return {}
    veg = settings.get("veg")
    if not isinstance(veg, dict):
        return {}
    block = veg.get("claude_design")
    return block if isinstance(block, dict) else {}
