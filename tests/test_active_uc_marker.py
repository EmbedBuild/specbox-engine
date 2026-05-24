"""UC-613 — `.quality/active_uc.json` cache uses the `reservation` key.

AC-02 of UC-613: the marker file written by
:func:`server.tools.spec_driven._write_active_uc_marker` for a native
session must use the literal key ``reservation`` (not ``claim``) so the
Python writer and the Node reader (spec-guard hook) share the same
vocabulary.

These tests exercise the writer with a tmp working directory so the
production cache file is never touched.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from server.tools.spec_driven import _write_active_uc_marker


@pytest.fixture
def tmp_cwd(tmp_path: Path, monkeypatch):
    """Move CWD to ``tmp_path`` so the marker lands in an isolated dir."""
    monkeypatch.chdir(tmp_path)
    yield tmp_path


def test_active_uc_marker_uses_reservation_key(tmp_cwd: Path):
    """AC-02: a marker written from a native reservation dict carries the
    ``reservation`` key (no ``claim`` key) and the dict inside has
    ``uc_id`` / ``developer_id`` / ``reserved_at`` / ``backend``."""
    _write_active_uc_marker(
        uc_id="UC-301",
        board_id="ff-test",
        feature="uc-301-feature",
        reservation={
            "uc_id": "UC-301",
            "developer_id": "alice",
            "reserved_at": "2026-05-25T10:00:00+00:00",
            "branch": "feature/uc-301",
        },
    )

    marker_path = tmp_cwd / ".quality" / "active_uc.json"
    assert marker_path.exists(), "the marker was not written"
    payload = json.loads(marker_path.read_text())

    # New key must be present with the expected shape.
    assert "reservation" in payload, (
        f"marker is missing the new 'reservation' key; got keys {list(payload)!r}"
    )
    reservation_block = payload["reservation"]
    assert reservation_block["uc_id"] == "UC-301"
    assert reservation_block["developer_id"] == "alice"
    assert reservation_block["reserved_at"] == "2026-05-25T10:00:00+00:00"
    assert reservation_block["backend"] == "native"

    # Legacy key must be ABSENT — UC-613 removed it from the writer.
    assert "claim" not in payload, (
        f"marker still carries the legacy 'claim' key: {payload!r}"
    )


def test_active_uc_marker_accepts_legacy_claimed_at_input(tmp_cwd: Path):
    """Backwards-compat: a caller still passing the legacy ``claimed_at``
    key in the input dict (e.g. mid-migration code) sees the value
    rewritten under ``reserved_at`` in the output."""
    _write_active_uc_marker(
        uc_id="UC-301",
        board_id="ff-test",
        reservation={
            "uc_id": "UC-301",
            "developer_id": "alice",
            # Legacy key from a pre-UC-602 caller.
            "claimed_at": "2026-05-25T10:00:00+00:00",
        },
    )

    payload = json.loads((tmp_cwd / ".quality" / "active_uc.json").read_text())
    assert payload["reservation"]["reserved_at"] == "2026-05-25T10:00:00+00:00"
    # ``claimed_at`` is normalised away in the output block.
    assert "claimed_at" not in payload["reservation"]


def test_active_uc_marker_without_reservation_writes_no_reservation_block(
    tmp_cwd: Path,
):
    """A non-native session (FreeForm/Trello/Plane) writes the marker
    without any ``reservation`` block at all."""
    _write_active_uc_marker(uc_id="UC-301", board_id="ff-test", feature="x")

    payload = json.loads((tmp_cwd / ".quality" / "active_uc.json").read_text())
    assert "reservation" not in payload
    assert "claim" not in payload
    assert payload["uc_id"] == "UC-301"
    assert payload["feature"] == "x"


def test_native_reservation_cache_key_constant_was_removed():
    """UC-613 AC-01 (Python side): the compat constant
    ``_NATIVE_RESERVATION_CACHE_KEY = "claim"`` introduced in UC-602 no
    longer exists in ``server.tools.spec_driven``."""
    import server.tools.spec_driven as spec_driven

    assert not hasattr(spec_driven, "_NATIVE_RESERVATION_CACHE_KEY"), (
        "_NATIVE_RESERVATION_CACHE_KEY constant should have been removed in UC-613"
    )
