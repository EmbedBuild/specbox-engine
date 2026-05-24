"""UC-604 — DeprecationWarning + dual payload for the legacy ``claim_uc`` MCP tool.

The legacy tool is reintroduced in v5.35.0 as a deprecated alias of
:func:`server.tools.coordination.reserve_uc`. This module pins down its
observable behaviour so v5.37.0 (UC-612) can remove it cleanly:

- AC-01: registered description starts with the literal deprecation prefix.
- AC-02: response payload carries BOTH vocabularies simultaneously.
- AC-03: a single ``DeprecationWarning`` + structured ``deprecated_tool_called``
  log line is emitted per call.
- AC-04: the new ``reserve_uc`` tool emits no warning and does NOT add the
  legacy ``claimed_at`` / ``legacy_code`` aliases.

The tests stub out :func:`reserve_uc` so the wrapper logic is the only thing
under test — no DB, no asyncpg, no FastMCP context plumbing.
"""

from __future__ import annotations

from typing import Any

import pytest

import server.tools.coordination as coord


# ── Pure helpers ─────────────────────────────────────────────────────


def test_add_legacy_aliases_success_payload_carries_both_vocabularies():
    """AC-02: a success payload from ``reserve_uc`` (code=RESERVED, reserved_at=...)
    gains ``claimed_at`` (= ``reserved_at``) and ``legacy_code='CLAIMED'``
    when passed through the deprecation wrapper enrichment."""
    new_payload: dict[str, Any] = {
        "success": True,
        "code": "RESERVED",
        "uc_id": "UC-301",
        "developer_id": "alice",
        "reserved_at": "2026-05-25T10:00:00+00:00",
        "branch": "feature/uc-301",
        "summary": "UC UC-301 reservado por alice.",
    }
    enriched = coord._add_legacy_aliases(new_payload)

    # Both vocabularies present
    assert enriched["reserved_at"] == "2026-05-25T10:00:00+00:00"
    assert enriched["claimed_at"] == enriched["reserved_at"]
    assert enriched["code"] == "RESERVED"
    assert enriched["legacy_code"] == "CLAIMED"

    # Original dict not mutated
    assert "claimed_at" not in new_payload
    assert "legacy_code" not in new_payload


def test_add_legacy_aliases_conflict_payload_maps_already_reserved():
    """AC-02: a conflict payload (code=ALREADY_RESERVED) maps the legacy_code
    to ALREADY_CLAIMED and mirrors reserved_at into claimed_at."""
    conflict_payload: dict[str, Any] = {
        "error": "UC 'UC-301' is already reserved by 'bob' since 2026-05-25T09:00:00+00:00 (branch: feature/uc-301-bob).",
        "code": "ALREADY_RESERVED",
        "uc_id": "UC-301",
        "owner": "bob",
        "reserved_at": "2026-05-25T09:00:00+00:00",
        "branch": "feature/uc-301-bob",
    }
    enriched = coord._add_legacy_aliases(conflict_payload)

    assert enriched["claimed_at"] == "2026-05-25T09:00:00+00:00"
    assert enriched["legacy_code"] == "ALREADY_CLAIMED"
    assert enriched["code"] == "ALREADY_RESERVED"


def test_add_legacy_aliases_auth_error_passes_through_untouched():
    """Non-rename codes (UNAUTHENTICATED, FORBIDDEN, NOT_NATIVE_SESSION) are
    not mapped to a legacy_code — they predate the rename and have no
    legacy equivalent."""
    for code in ("UNAUTHENTICATED", "FORBIDDEN", "NOT_NATIVE_SESSION"):
        payload = {"error": "...", "code": code}
        enriched = coord._add_legacy_aliases(payload)
        assert enriched["code"] == code
        assert "legacy_code" not in enriched, (
            f"non-rename code {code!r} must not get a legacy_code annotation"
        )
        assert "claimed_at" not in enriched, (
            f"non-rename code {code!r} has no reserved_at to mirror"
        )


def test_add_legacy_aliases_does_not_overwrite_existing_claimed_at():
    """Defensive: if a payload already carries ``claimed_at`` for some reason,
    the enrichment does NOT clobber it."""
    payload = {
        "code": "RESERVED",
        "reserved_at": "2026-05-25T10:00:00+00:00",
        "claimed_at": "PREEXISTING",
    }
    enriched = coord._add_legacy_aliases(payload)
    assert enriched["claimed_at"] == "PREEXISTING"
    assert enriched["reserved_at"] == "2026-05-25T10:00:00+00:00"


# ── claim_uc wrapper: DeprecationWarning + structured log + dual payload ─


async def _fake_reserve_uc_success(uc_id: str, ctx: Any, branch: str = "") -> dict[str, Any]:
    """Stub of :func:`reserve_uc` returning a v5.35.0 success payload."""
    return {
        "success": True,
        "code": "RESERVED",
        "uc_id": uc_id,
        "developer_id": "alice",
        "reserved_at": "2026-05-25T10:00:00+00:00",
        "branch": branch or "",
        "summary": f"UC {uc_id} reservado por alice.",
    }


async def _fake_reserve_uc_conflict(uc_id: str, ctx: Any, branch: str = "") -> dict[str, Any]:
    """Stub of :func:`reserve_uc` returning a v5.35.0 ALREADY_RESERVED payload."""
    return {
        "error": "UC 'UC-301' is already reserved by 'bob' since 2026-05-25T09:00:00+00:00 (branch: feature/uc-301-bob).",
        "code": "ALREADY_RESERVED",
        "uc_id": uc_id,
        "owner": "bob",
        "reserved_at": "2026-05-25T09:00:00+00:00",
        "branch": "feature/uc-301-bob",
    }


async def test_claim_uc_emits_deprecation_warning(monkeypatch):
    """AC-03 — calling ``claim_uc`` emits a single :class:`DeprecationWarning`
    whose message names both the version since deprecated and the removal
    version, so callers can grep for the migration path."""
    monkeypatch.setattr(coord, "reserve_uc", _fake_reserve_uc_success)
    with pytest.warns(DeprecationWarning) as captured:
        await coord.claim_uc("UC-301", ctx=object())
    assert len(captured) == 1, f"expected exactly 1 DeprecationWarning, got {len(captured)}"
    msg = str(captured[0].message)
    assert "claim_uc" in msg
    assert "v5.35.0" in msg
    assert "v5.37.0" in msg
    assert "reserve_uc" in msg


async def test_claim_uc_logs_structured_deprecated_tool_called(monkeypatch):
    """AC-03 — calling ``claim_uc`` logs an info-level structured record
    ``deprecated_tool_called`` carrying tool / since_version / remove_in_version
    / replacement so observability dashboards can quantify legacy usage.

    Intercepts the call at the ``logger.info`` boundary in
    :mod:`server.tools.coordination` so the test does not depend on the
    repo's structlog processor chain (which differs between local dev,
    pytest, and the MCP runtime)."""
    monkeypatch.setattr(coord, "reserve_uc", _fake_reserve_uc_success)

    captured: list[tuple[str, dict[str, Any]]] = []

    class _RecordingLogger:
        def info(self_inner, event, **kwargs):
            captured.append((event, dict(kwargs)))

    monkeypatch.setattr(coord, "logger", _RecordingLogger())

    with pytest.warns(DeprecationWarning):
        await coord.claim_uc("UC-301", ctx=object())

    deprecated_events = [
        (event, kwargs) for event, kwargs in captured if event == "deprecated_tool_called"
    ]
    assert len(deprecated_events) == 1, (
        f"expected exactly one deprecated_tool_called event, got "
        f"{len(deprecated_events)} in {captured!r}"
    )
    _, kwargs = deprecated_events[0]
    assert kwargs["tool"] == "claim_uc"
    assert kwargs["since_version"] == "v5.35.0"
    assert kwargs["remove_in_version"] == "v5.37.0"
    assert kwargs["replacement"] == "reserve_uc"


async def test_claim_uc_success_payload_carries_both_vocabularies(monkeypatch):
    """AC-02 — a successful ``claim_uc`` returns the v5.35.0 keys (reserved_at,
    code=RESERVED) AND the v5.34.x aliases (claimed_at, legacy_code=CLAIMED)."""
    monkeypatch.setattr(coord, "reserve_uc", _fake_reserve_uc_success)
    with pytest.warns(DeprecationWarning):
        payload = await coord.claim_uc("UC-301", ctx=object())

    # New vocabulary
    assert payload["code"] == "RESERVED"
    assert payload["reserved_at"] == "2026-05-25T10:00:00+00:00"
    # Legacy aliases
    assert payload["legacy_code"] == "CLAIMED"
    assert payload["claimed_at"] == payload["reserved_at"]


async def test_claim_uc_conflict_payload_carries_both_vocabularies(monkeypatch):
    """AC-02 — a conflicted ``claim_uc`` returns ALREADY_RESERVED + the
    ALREADY_CLAIMED legacy alias side by side."""
    monkeypatch.setattr(coord, "reserve_uc", _fake_reserve_uc_conflict)
    with pytest.warns(DeprecationWarning):
        payload = await coord.claim_uc("UC-301", ctx=object())

    assert payload["code"] == "ALREADY_RESERVED"
    assert payload["legacy_code"] == "ALREADY_CLAIMED"
    assert payload["reserved_at"] == payload["claimed_at"] == "2026-05-25T09:00:00+00:00"
    assert payload["owner"] == "bob"


# ── reserve_uc must NOT exhibit the deprecation surface ──────────────


async def test_reserve_uc_does_not_emit_deprecation_warning(monkeypatch):
    """AC-04 — calling the new ``reserve_uc`` tool emits zero
    DeprecationWarning. Verified by recording warnings explicitly so a
    `pytest.warns` assertion failure is unambiguous."""
    import warnings as _w

    # Patch the underlying _reserve_uc + auth gate so the tool body runs
    # without touching the DB. We assert on warnings only.
    async def _fake_authed_dev(ctx):
        # Return a stub triple (project_id, dev, pool) acceptable to the body.
        class _Dev:
            developer_id = "alice"

        class _Pool:
            def acquire(self):
                class _Cm:
                    async def __aenter__(self_inner):
                        return None

                    async def __aexit__(self_inner, *a):
                        return False

                return _Cm()

        return ("p", _Dev(), _Pool())

    async def _fake_reserve(*_a, **_k):
        # Stub the inner reservations.reserve_uc call.
        class _R:
            def to_public(self_inner):
                return {
                    "uc_id": "UC-301",
                    "developer_id": "alice",
                    "reserved_at": "2026-05-25T10:00:00+00:00",
                    "branch": "",
                }

        return _R()

    monkeypatch.setattr(coord, "_authed_dev", _fake_authed_dev)
    monkeypatch.setattr(coord, "_reserve_uc", _fake_reserve)

    with _w.catch_warnings(record=True) as recorded:
        _w.simplefilter("always")
        payload = await coord.reserve_uc("UC-301", ctx=object())

    deprecations = [w for w in recorded if issubclass(w.category, DeprecationWarning)]
    assert deprecations == [], (
        f"reserve_uc emitted DeprecationWarning(s): {[str(w.message) for w in deprecations]}"
    )

    # AC-04: reserve_uc payload must NOT contain the legacy aliases.
    assert "claimed_at" not in payload, (
        f"reserve_uc payload leaks legacy alias claimed_at: {payload!r}"
    )
    assert "legacy_code" not in payload, (
        f"reserve_uc payload leaks legacy alias legacy_code: {payload!r}"
    )


# ── AC-01: registered description prefix ─────────────────────────────


def test_claim_uc_deprecated_description_has_literal_prefix():
    """AC-01 — the FastMCP ``description`` registered for claim_uc starts
    with the literal deprecation prefix mandated by the AC."""
    expected_prefix = (
        "[DEPRECATED desde v5.35.0 — usa reserve_uc. Se elimina en v5.37.0]"
    )
    assert coord._CLAIM_UC_DEPRECATED_DESCRIPTION.startswith(expected_prefix), (
        f"description does not start with the AC-01 prefix; "
        f"got: {coord._CLAIM_UC_DEPRECATED_DESCRIPTION[:120]!r}"
    )
