"""Targeted tests to push coverage past the 85% AC-05 threshold.

Covers error branches and helper paths not exercised by the main acceptance tests.
"""

from __future__ import annotations

import subprocess
from typing import Any
from unittest.mock import MagicMock, patch

from specbox_supabase_mcp.lib.engram_writer import (
    format_config_content,
    write_config_observation,
)
from specbox_supabase_mcp.lib.response import err, ok
from specbox_supabase_mcp.lib.supabase_client import SupabaseAPIError
from specbox_supabase_mcp.tools.list_edge_secrets import list_edge_secrets
from specbox_supabase_mcp.tools.unset_edge_secret import (
    CONFIRM_TOKEN_LITERAL,
    unset_edge_secret,
)

TEST_PAT = "sbp_" + "ValidDummyFixtureToken01234567890abc"
PROJECT_REF = "dddddddddddddddddddd"


def _response(status: int, body: Any = None) -> MagicMock:
    m = MagicMock()
    m.status_code = status
    m.json.return_value = body if body is not None else []
    return m


class TestEngramWriter:
    def test_engram_cli_not_found(self) -> None:
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert write_config_observation(project="p", title="t", content="c") is None

    def test_engram_cli_timeout(self) -> None:
        with patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="engram", timeout=3.0),
        ):
            assert write_config_observation(project="p", title="t", content="c") is None

    def test_engram_cli_generic_failure(self) -> None:
        with patch("subprocess.run", side_effect=RuntimeError("broken")):
            assert write_config_observation(project="p", title="t", content="c") is None

    def test_engram_cli_non_zero_rc(self) -> None:
        mock_proc = MagicMock(returncode=1, stdout="", stderr="boom")
        with patch("subprocess.run", return_value=mock_proc):
            assert write_config_observation(project="p", title="t", content="c") is None

    def test_engram_cli_success_returns_id(self) -> None:
        mock_proc = MagicMock(returncode=0, stdout="obs_abc123\n", stderr="")
        with patch("subprocess.run", return_value=mock_proc):
            assert write_config_observation(project="p", title="t", content="c") == "obs_abc123"

    def test_format_config_content_full(self) -> None:
        content = format_config_content(
            tool="x",
            project="p",
            mode="cloud",
            result_summary="ok",
            ids_created=["A"],
            ids_reused=["B"],
            duration_ms=12.3,
            extra={"k": "v"},
        )
        assert "Tool" in content
        assert "A" in content
        assert "B" in content
        assert "12" in content


class TestResponseHelpers:
    def test_ok_with_warnings_and_evidence(self) -> None:
        out = ok({"a": 1}, warnings=["w"], evidence={"engram_observation_id": "o"})
        assert out["warnings"] == ["w"]
        assert out["evidence"]["engram_observation_id"] == "o"

    def test_err_with_data(self) -> None:
        out = err(code="E_X", message="m", data={"extra": True})
        assert out["data"] == {"extra": True}


class TestListEdgeSecretsErrors:
    def test_401_returns_invalid_token(self) -> None:
        with patch("specbox_supabase_mcp.tools.list_edge_secrets.SupabaseClient") as m_cls:
            instance = MagicMock()
            instance.call.side_effect = SupabaseAPIError(status_code=401, message="bad")
            m_cls.return_value = instance
            out = list_edge_secrets(
                supabase_access_token=TEST_PAT,
                project_ref=PROJECT_REF,
                project_hint="p",
            )
        assert out["error"]["code"] == "E_INVALID_TOKEN"

    def test_500_returns_generic_error(self) -> None:
        with patch("specbox_supabase_mcp.tools.list_edge_secrets.SupabaseClient") as m_cls:
            instance = MagicMock()
            instance.call.side_effect = SupabaseAPIError(status_code=500, message="oops")
            m_cls.return_value = instance
            out = list_edge_secrets(
                supabase_access_token=TEST_PAT,
                project_ref=PROJECT_REF,
                project_hint="p",
            )
        assert out["error"]["code"] == "E_SUPABASE_ERROR"

    def test_malformed_json_returns_empty_list(self) -> None:
        with patch("specbox_supabase_mcp.tools.list_edge_secrets.SupabaseClient") as m_cls:
            instance = MagicMock()
            bad_resp = MagicMock(status_code=200)
            bad_resp.json.side_effect = ValueError("bad json")
            instance.call.return_value = bad_resp
            m_cls.return_value = instance
            out = list_edge_secrets(
                supabase_access_token=TEST_PAT,
                project_ref=PROJECT_REF,
                project_hint="p",
            )
        assert out["success"] is True
        assert out["data"]["names"] == []

    def test_invalid_input_rejected_early(self) -> None:
        out = list_edge_secrets(
            supabase_access_token="not_a_pat",
            project_ref=PROJECT_REF,
            project_hint="p",
        )
        assert out["error"]["code"] == "E_INVALID_INPUT"


class TestUnsetEdgeSecretErrors:
    def test_list_fails_propagates_error(self) -> None:
        with patch("specbox_supabase_mcp.tools.unset_edge_secret.SupabaseClient") as m_cls:
            instance = MagicMock()
            instance.call.side_effect = SupabaseAPIError(status_code=403, message="no")
            m_cls.return_value = instance
            out = unset_edge_secret(
                supabase_access_token=TEST_PAT,
                project_ref=PROJECT_REF,
                names=["FOO"],
                confirm_token=CONFIRM_TOKEN_LITERAL,
                project_hint="p",
            )
        assert out["error"]["code"] == "E_INSUFFICIENT_PERMISSIONS"

    def test_delete_fails_propagates_error(self) -> None:
        with patch("specbox_supabase_mcp.tools.unset_edge_secret.SupabaseClient") as m_cls:
            instance = MagicMock()
            instance.call.side_effect = [
                _response(200, [{"name": "FOO", "updated_at": "t"}]),
                SupabaseAPIError(status_code=500, message="oops"),
            ]
            m_cls.return_value = instance
            out = unset_edge_secret(
                supabase_access_token=TEST_PAT,
                project_ref=PROJECT_REF,
                names=["FOO"],
                confirm_token=CONFIRM_TOKEN_LITERAL,
                project_hint="p",
            )
        assert out["error"]["code"] == "E_SUPABASE_ERROR"

    def test_invalid_input_rejected_early(self) -> None:
        out = unset_edge_secret(
            supabase_access_token="bad",
            project_ref=PROJECT_REF,
            names=["FOO"],
            confirm_token=CONFIRM_TOKEN_LITERAL,
            project_hint="p",
        )
        assert out["error"]["code"] == "E_INVALID_INPUT"

    def test_non_string_names_rejected(self) -> None:
        out = unset_edge_secret(
            supabase_access_token=TEST_PAT,
            project_ref=PROJECT_REF,
            names=["VALID", 42],  # type: ignore[list-item]
            confirm_token=CONFIRM_TOKEN_LITERAL,
            project_hint="p",
        )
        assert out["error"]["code"] == "E_INVALID_INPUT"


class TestSupabaseClientEdges:
    def test_default_base_url(self) -> None:
        from specbox_supabase_mcp.lib.supabase_client import SupabaseClient
        c = SupabaseClient(access_token="sbp_test")
        assert c.base_url == "https://api.supabase.com"

    def test_safe_error_message_fallback(self) -> None:
        from specbox_supabase_mcp.lib.supabase_client import _safe_error_message
        resp = MagicMock(status_code=500)
        resp.json.side_effect = ValueError("bad")
        assert "HTTP 500" in _safe_error_message(resp)

    def test_safe_error_message_from_message_field(self) -> None:
        from specbox_supabase_mcp.lib.supabase_client import _safe_error_message
        resp = MagicMock(status_code=400)
        resp.json.return_value = {"message": "something broke"}
        assert "something broke" in _safe_error_message(resp)
