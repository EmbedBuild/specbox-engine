"""Tests for lib/response.py and lib/heartbeat.py.

The response helpers are copied verbatim from specbox-stripe-mcp (PRD §6 Opción A),
so these tests just confirm the copy works and the envelope fields are correct.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from specbox_supabase_mcp.lib import heartbeat
from specbox_supabase_mcp.lib.response import err, ok


class TestResponseEnvelope:
    def test_ok_minimal(self) -> None:
        out = ok({"a": 1})
        assert out == {"success": True, "data": {"a": 1}}

    def test_err_minimal(self) -> None:
        out = err(code="E_X", message="bad")
        assert out["success"] is False
        assert out["error"]["code"] == "E_X"

    def test_err_with_remediation(self) -> None:
        out = err(code="E_X", message="bad", remediation="do this")
        assert out["error"]["remediation"] == "do this"


class TestHeartbeat:
    def test_no_endpoint_is_noop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SPECBOX_ENGINE_MCP_URL", raising=False)
        with patch("httpx.post") as m_post:
            heartbeat.report_heartbeat(project="p", event_type="x", payload={})
        m_post.assert_not_called()

    def test_posts_to_endpoint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SPECBOX_ENGINE_MCP_URL", "https://mcp.specbox.test")
        with patch("httpx.post") as m_post:
            heartbeat.report_heartbeat(
                project="p", event_type="supabase_mcp_call", payload={"t": "x"}
            )
        assert m_post.called
        kwargs = m_post.call_args.kwargs
        args = m_post.call_args.args
        url = args[0] if args else kwargs.get("url")
        assert url.endswith("/api/report/heartbeat")

    def test_network_error_swallowed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SPECBOX_ENGINE_MCP_URL", "https://mcp.specbox.test")
        with patch("httpx.post", side_effect=RuntimeError("boom")):
            heartbeat.report_heartbeat(project="p", event_type="x", payload={})

    def test_healing_reports_correct_agent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Must be specbox-supabase-mcp (not stripe)."""
        monkeypatch.setenv("SPECBOX_ENGINE_MCP_URL", "https://mcp.specbox.test")
        with patch("httpx.post") as m_post:
            heartbeat.report_healing(
                project="p", hook="h", root_cause="rate_limit", resolution="retry"
            )
        body = m_post.call_args.kwargs["json"]
        assert body["agent"] == "specbox-supabase-mcp"


class TestReadmeToolCoverage:
    """AC-04 of UC-SB-6 mirror: enforce that every TOOL_NAME appears in README."""

    def test_all_tools_in_readme(self) -> None:
        from pathlib import Path

        from specbox_supabase_mcp.tools import (
            list_edge_secrets as mod_list,
        )
        from specbox_supabase_mcp.tools import (
            set_edge_secret as mod_set,
        )
        from specbox_supabase_mcp.tools import (
            unset_edge_secret as mod_unset,
        )

        readme = Path(__file__).resolve().parents[2] / "README.md"
        text = readme.read_text(encoding="utf-8")
        for name in (mod_set.TOOL_NAME, mod_list.TOOL_NAME, mod_unset.TOOL_NAME):
            assert name in text, f"{name} missing from README.md"
