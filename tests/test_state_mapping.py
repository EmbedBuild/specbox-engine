"""Tests for server.migration.state_mapping (UC-402).

Covers the three acceptance criteria:

* AC-04 — canonical ↔ native matrix + lossless round-trip for the identity
  backends (freeform/native/trello), with ``in_progress`` round-tripping on all
  four backends.
* AC-05 — Plane degradation detection (``review``→``in_progress``,
  ``user_stories``→``backlog``) and the unknown-state fallback to ``backlog``.
* AC-06 — AC ``done`` is an independent boolean that never passes through
  state_mapping; the functions operate only on workflow-state strings.
"""

from __future__ import annotations

import pytest

from server.migration.state_mapping import (
    BACKEND_NATIVE_STATES,
    CANONICAL_STATES,
    detect_degradation,
    from_native,
    map_state_for_migration,
    to_native,
)

IDENTITY_BACKENDS = ("freeform", "native", "trello")
ALL_BACKENDS = ("freeform", "native", "trello", "plane")


# ── AC-04: canonical ↔ native matrix + round-trip ────────────────────


def test_canonical_states_match_abc():
    """The five canonical states match server.models.WorkflowState order."""
    assert CANONICAL_STATES == (
        "user_stories",
        "backlog",
        "in_progress",
        "review",
        "done",
    )


@pytest.mark.parametrize("backend", ALL_BACKENDS)
@pytest.mark.parametrize("canonical", CANONICAL_STATES)
def test_to_native_returns_a_native_state(backend: str, canonical: str):
    """For every backend and canonical state, to_native yields a non-empty str."""
    native = to_native(backend, canonical)
    assert isinstance(native, str)
    assert native
    # the produced native must be a value present in the backend's matrix
    assert native in BACKEND_NATIVE_STATES[backend].values()


@pytest.mark.parametrize("backend", IDENTITY_BACKENDS)
@pytest.mark.parametrize("canonical", CANONICAL_STATES)
def test_identity_backends_round_trip_lossless(backend: str, canonical: str):
    """freeform/native/trello: from_native(to_native(s)) == s for every state."""
    assert from_native(backend, to_native(backend, canonical)) == canonical


@pytest.mark.parametrize("backend", ALL_BACKENDS)
def test_in_progress_round_trips_on_all_backends(backend: str):
    """A UC in 'in_progress' migrated to any backend re-reads as 'in_progress'."""
    assert from_native(backend, to_native(backend, "in_progress")) == "in_progress"


def test_plane_matrix_reflects_state_groups():
    """Plane matrix mirrors plane_backend._STATE_GROUPS (the real collapse)."""
    assert BACKEND_NATIVE_STATES["plane"] == {
        "user_stories": "backlog",
        "backlog": "backlog",
        "in_progress": "started",
        "review": "started",
        "done": "completed",
    }


def test_from_native_resolves_ambiguity_to_representative():
    """Plane's collapsed natives resolve to the representative canonical key."""
    # 'started' maps from both in_progress and review -> first-in-order wins
    assert from_native("plane", "started") == "in_progress"
    # 'backlog' maps from both user_stories and backlog -> the key named
    # 'backlog' is the representative (matches Plane's group-name read-back)
    assert from_native("plane", "backlog") == "backlog"
    assert from_native("plane", "completed") == "done"


def test_to_native_unknown_backend_raises():
    with pytest.raises(ValueError):
        to_native("notabackend", "in_progress")


def test_to_native_unknown_state_raises():
    with pytest.raises(ValueError):
        to_native("plane", "frozen")


def test_from_native_unknown_native_raises():
    with pytest.raises(ValueError):
        from_native("plane", "nonexistent")


# ── AC-05: degradation detection + fallback ──────────────────────────


@pytest.mark.parametrize("backend", IDENTITY_BACKENDS)
@pytest.mark.parametrize("canonical", CANONICAL_STATES)
def test_identity_backends_never_degrade(backend: str, canonical: str):
    assert detect_degradation(backend, canonical) is None


def test_plane_review_degrades_to_in_progress():
    assert detect_degradation("plane", "review") == "in_progress"


def test_plane_user_stories_degrades_to_backlog():
    assert detect_degradation("plane", "user_stories") == "backlog"


@pytest.mark.parametrize("canonical", ("backlog", "in_progress", "done"))
def test_plane_lossless_states_do_not_degrade(canonical: str):
    assert detect_degradation("plane", canonical) is None


def test_map_state_plane_review_emits_warning():
    state, warning = map_state_for_migration("plane", "review")
    # the canonical state is still what we write — the backend collapses it
    assert state == "review"
    assert warning is not None
    assert warning["original_state"] == "review"
    assert warning["degrades_to"] == "in_progress"
    assert warning["reason"] == "lossy_round_trip"


def test_map_state_plane_user_stories_degrades_to_backlog():
    state, warning = map_state_for_migration("plane", "user_stories")
    assert state == "user_stories"
    assert warning is not None
    assert warning["degrades_to"] == "backlog"
    assert warning["reason"] == "lossy_round_trip"


def test_map_state_unknown_state_falls_back_to_backlog():
    state, warning = map_state_for_migration("plane", "frozen")
    assert state == "backlog"
    assert warning is not None
    assert warning["original_state"] == "frozen"
    assert warning["degrades_to"] == "backlog"
    assert warning["reason"] == "unknown_state"


@pytest.mark.parametrize("backend", IDENTITY_BACKENDS)
@pytest.mark.parametrize("canonical", CANONICAL_STATES)
def test_map_state_identity_backends_no_warning(backend: str, canonical: str):
    state, warning = map_state_for_migration(backend, canonical)
    assert state == canonical
    assert warning is None


# ── AC-06: AC.done is an independent bool, not touched by state_mapping ─


def test_map_state_only_handles_strings_never_booleans():
    """state_mapping operates exclusively on workflow-state strings.

    AC.done (ChecklistItemDTO.done) is a separate boolean preserved by
    write_target via mark_acceptance_criterion (UC-401). It must never be
    confused with a workflow state. We verify the returned state is always a
    str and the warning (when present) contains only str values — no booleans
    leak through this layer.
    """
    for backend in ALL_BACKENDS:
        for canonical in CANONICAL_STATES:
            state, warning = map_state_for_migration(backend, canonical)
            assert isinstance(state, str)
            assert not isinstance(state, bool)
            if warning is not None:
                for value in warning.values():
                    assert isinstance(value, str)
                    assert not isinstance(value, bool)


def test_done_workflow_state_is_distinct_from_ac_done_bool():
    """The 'done' workflow state is a string and unrelated to the done bool.

    Round-tripping the 'done' workflow state preserves it on all backends; this
    is orthogonal to whether an AC's done flag is True/False.
    """
    for backend in ALL_BACKENDS:
        assert to_native(backend, "done")  # a non-empty native string
        assert detect_degradation(backend, "done") is None
