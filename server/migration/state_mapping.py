"""Canonical ↔ native workflow-state mapping for N×N backend migration (UC-402).

The SpecBox ABC defines five canonical workflow states (see
``server.models.WorkflowState``)::

    ("user_stories", "backlog", "in_progress", "review", "done")

Every backend stores and returns ``ItemDTO.state`` in these *canonical* keys
(``FreeformBackend`` and ``NativeBackend`` are the identity; ``PlaneBackend``
normalizes back to canonical on read). However Plane has fewer *native* states
than the canonical set: it collapses ``user_stories`` and ``backlog`` into a
single ``backlog`` group, and ``in_progress`` and ``review`` into a single
``started`` group (see ``server.backends.plane_backend._STATE_GROUPS``). That
collapse is **lossy**: a UC written to Plane as ``review`` re-reads as
``in_progress``; a US written as ``user_stories`` re-reads as ``backlog``.

This module is the single source of truth for that translation. It is **pure**
(no I/O, no async) and provides:

* ``BACKEND_NATIVE_STATES`` — the full canonical→native matrix per backend.
* ``to_native`` / ``from_native`` — directional lookups.
* ``detect_degradation`` — does a round-trip to this backend lose information?
* ``map_state_for_migration`` — the state to write plus an optional structured
  warning for the migration report (AC-05 fallback applied).

NOTE on ``ItemDTO.done`` (acceptance criteria): the boolean ``done`` flag of an
AC (``ChecklistItemDTO.done``) is **independent** of workflow state and does not
pass through this module. ``write_target`` (UC-401) preserves it directly via
``mark_acceptance_criterion``. None of the functions here read or mutate booleans
— they operate exclusively on workflow-state strings (AC-06).
"""

from __future__ import annotations

# The five canonical workflow states, in canonical order. Mirrors
# ``server.models.WorkflowState``. Order matters: ``from_native`` resolves
# ambiguous native states to the FIRST canonical key that maps to them.
CANONICAL_STATES: tuple[str, ...] = (
    "user_stories",
    "backlog",
    "in_progress",
    "review",
    "done",
)

# Fallback state used when the source state is unknown (AC-05).
_FALLBACK_STATE = "backlog"

# Per-backend canonical→native mapping.
#
# freeform / native / trello are the identity: each canonical state maps to
# itself, so round-trips are lossless.
#
# plane reflects ``plane_backend._STATE_GROUPS`` (lines 57-63): the canonical
# set is collapsed onto Plane's native state groups. ``user_stories`` and
# ``backlog`` both become ``backlog``; ``in_progress`` and ``review`` both
# become ``started``; ``done`` becomes ``completed``. This collapse is what
# makes ``review`` and ``user_stories`` lossy on Plane.
_IDENTITY: dict[str, str] = {s: s for s in CANONICAL_STATES}

BACKEND_NATIVE_STATES: dict[str, dict[str, str]] = {
    "freeform": dict(_IDENTITY),
    "native": dict(_IDENTITY),
    "trello": dict(_IDENTITY),
    "plane": {
        "user_stories": "backlog",
        "backlog": "backlog",
        "in_progress": "started",
        "review": "started",
        "done": "completed",
    },
}


def _backend_map(backend_type: str) -> dict[str, str]:
    """Return the canonical→native map for ``backend_type``.

    Raises ``KeyError`` (via ``ValueError``) for unknown backends so callers
    fail loudly rather than silently degrading on a typo.
    """
    try:
        return BACKEND_NATIVE_STATES[backend_type]
    except KeyError as exc:  # pragma: no cover - defensive
        raise ValueError(
            f"Unknown backend_type {backend_type!r}; expected one of {sorted(BACKEND_NATIVE_STATES)}"
        ) from exc


def to_native(backend_type: str, canonical: str) -> str:
    """Translate a canonical workflow state to ``backend_type``'s native state.

    Raises ``ValueError`` if ``backend_type`` is unknown or ``canonical`` is not
    a known canonical state.
    """
    mapping = _backend_map(backend_type)
    try:
        return mapping[canonical]
    except KeyError as exc:
        raise ValueError(f"Unknown canonical state {canonical!r}; expected one of {list(CANONICAL_STATES)}") from exc


def from_native(backend_type: str, native: str) -> str:
    """Translate a native state back to a canonical workflow state.

    For lossy backends (plane) several canonical states map to the same native
    state, so the inverse is ambiguous. We resolve it deterministically to the
    *representative* canonical key for that native group, mirroring how
    ``plane_backend`` reads a state group back:

    1. If a canonical key equals the native value (the group's own name —
       e.g. ``backlog`` for native ``backlog``), that key is the representative.
    2. Otherwise the FIRST canonical key (in :data:`CANONICAL_STATES` order)
       that maps to ``native`` wins (e.g. ``in_progress`` for native
       ``started``, since ``in_progress`` precedes ``review``).

    This is exactly why Plane's ``started`` resolves to ``in_progress`` (not
    ``review``) and ``backlog`` resolves to ``backlog`` (not ``user_stories``)
    — and hence why ``review`` and ``user_stories`` are lost on a Plane
    round-trip.

    Raises ``ValueError`` if ``backend_type`` is unknown or no canonical state
    maps to ``native``.
    """
    mapping = _backend_map(backend_type)
    candidates = [canonical for canonical in CANONICAL_STATES if mapping.get(canonical) == native]
    if not candidates:
        raise ValueError(f"Native state {native!r} has no canonical equivalent on backend {backend_type!r}")
    # Rule 1: prefer the canonical key whose name IS the native value.
    if native in candidates:
        return native
    # Rule 2: first canonical key in order wins.
    return candidates[0]


def detect_degradation(backend_type: str, canonical: str) -> str | None:
    """Return the canonical state a round-trip would degrade to, or ``None``.

    A canonical state degrades on ``backend_type`` when writing it and reading
    it back yields a *different* canonical state, i.e.
    ``from_native(backend_type, to_native(backend_type, canonical)) != canonical``.

    * For freeform / native / trello (identity maps) this is always ``None``.
    * For plane: ``review`` degrades to ``"in_progress"`` and ``user_stories``
      degrades to ``"backlog"``; every other state is lossless (``None``).

    Raises ``ValueError`` if ``backend_type`` or ``canonical`` is unknown.
    """
    native = to_native(backend_type, canonical)
    round_trip = from_native(backend_type, native)
    return None if round_trip == canonical else round_trip


def map_state_for_migration(target_backend_type: str, canonical_state: str) -> tuple[str, dict[str, str] | None]:
    """Resolve the state to write for a migration plus an optional warning.

    The returned state is always the *canonical* state to hand to
    ``write_target`` — the target backend performs its own internal collapse
    when persisting. The warning is purely informational, for the migration
    report.

    AC-05 fallback rules:

    * If ``canonical_state`` is not a known canonical state, write the
      :data:`_FALLBACK_STATE` (``"backlog"``) and emit a warning with
      ``reason="unknown_state"``.
    * If the state would degrade on a round-trip (``detect_degradation`` is not
      ``None``), keep the canonical state but emit a warning with
      ``degrades_to`` set and ``reason="lossy_round_trip"``.
    * Otherwise return ``(canonical_state, None)``.

    Returns a ``(state_to_write, warning_or_none)`` tuple. The warning, when
    present, is a dict with keys ``original_state``, ``degrades_to`` and
    ``reason``.
    """
    if canonical_state not in CANONICAL_STATES:
        warning: dict[str, str] = {
            "original_state": canonical_state,
            "degrades_to": _FALLBACK_STATE,
            "reason": "unknown_state",
        }
        return _FALLBACK_STATE, warning

    degrades_to = detect_degradation(target_backend_type, canonical_state)
    if degrades_to is not None:
        warning = {
            "original_state": canonical_state,
            "degrades_to": degrades_to,
            "reason": "lossy_round_trip",
        }
        return canonical_state, warning

    return canonical_state, None
