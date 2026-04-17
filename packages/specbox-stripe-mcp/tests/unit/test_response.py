"""Tests for the standard response envelope."""

from __future__ import annotations

from specbox_stripe_mcp.lib.response import err, ok


def test_ok_minimal() -> None:
    out = ok({"foo": 1})
    assert out == {"success": True, "data": {"foo": 1}}


def test_ok_with_warnings_and_evidence() -> None:
    out = ok(
        {"foo": 1},
        warnings=["note"],
        evidence={"engram_observation_id": "obs_abc"},
    )
    assert out["success"] is True
    assert out["warnings"] == ["note"]
    assert out["evidence"] == {"engram_observation_id": "obs_abc"}


def test_err_minimal() -> None:
    out = err(code="E_X", message="bad")
    assert out == {"success": False, "error": {"code": "E_X", "message": "bad"}}


def test_err_with_remediation_and_data() -> None:
    out = err(
        code="E_CONNECT_NOT_ENABLED",
        message="not enabled",
        remediation="go to dashboard",
        data={"enabled": False},
    )
    assert out["success"] is False
    assert out["error"]["remediation"] == "go to dashboard"
    assert out["data"] == {"enabled": False}
