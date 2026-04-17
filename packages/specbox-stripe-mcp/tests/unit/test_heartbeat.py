"""Tests for lib/heartbeat.py."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from specbox_stripe_mcp.lib import heartbeat


def test_heartbeat_no_endpoint_configured_is_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    """If SPECBOX_ENGINE_MCP_URL is unset, nothing happens and nothing raises."""
    monkeypatch.delenv("SPECBOX_ENGINE_MCP_URL", raising=False)
    with patch("httpx.post") as m_post:
        heartbeat.report_heartbeat(
            project="p", event_type="x", payload={"k": "v"}
        )
    m_post.assert_not_called()


def test_heartbeat_posts_to_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPECBOX_ENGINE_MCP_URL", "https://mcp.specbox.test")
    monkeypatch.setenv("SPECBOX_SYNC_TOKEN", "secret_token")
    with patch("httpx.post") as m_post:
        heartbeat.report_heartbeat(
            project="p", event_type="stripe_mcp_call", payload={"tool": "t"}
        )
    assert m_post.called
    args, kwargs = m_post.call_args
    url = args[0] if args else kwargs.get("url")
    assert url == "https://mcp.specbox.test/api/report/heartbeat"
    headers = kwargs["headers"]
    assert headers["Authorization"] == "Bearer secret_token"
    body = kwargs["json"]
    assert body["project"] == "p"
    assert body["event_type"] == "stripe_mcp_call"
    assert body["payload"] == {"tool": "t"}


def test_heartbeat_network_error_is_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPECBOX_ENGINE_MCP_URL", "https://mcp.specbox.test")
    with patch("httpx.post", side_effect=RuntimeError("net error")):
        # Should not raise
        heartbeat.report_heartbeat(
            project="p", event_type="x", payload={}
        )


def test_healing_no_endpoint_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SPECBOX_ENGINE_MCP_URL", raising=False)
    with patch("httpx.post") as m_post:
        heartbeat.report_healing(
            project="p", hook="h", root_cause="rate_limit", resolution="retry"
        )
    m_post.assert_not_called()


def test_healing_posts_to_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPECBOX_ENGINE_MCP_URL", "https://mcp.specbox.test/")  # trailing slash
    with patch("httpx.post") as m_post:
        heartbeat.report_healing(
            project="p", hook="accounts.retrieve",
            root_cause="rate_limit", resolution="retry",
        )
    assert m_post.called
    args, kwargs = m_post.call_args
    url = args[0] if args else kwargs.get("url")
    assert url == "https://mcp.specbox.test/api/report/healing"
    body = kwargs["json"]
    assert body["agent"] == "specbox-stripe-mcp"
    assert body["root_cause"] == "rate_limit"


def test_healing_network_error_is_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPECBOX_ENGINE_MCP_URL", "https://mcp.specbox.test")
    with patch("httpx.post", side_effect=RuntimeError("boom")):
        heartbeat.report_healing(
            project="p", hook="h", root_cause="x", resolution="y"
        )
