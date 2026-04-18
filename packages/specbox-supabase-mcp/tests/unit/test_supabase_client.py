"""Tests for lib/supabase_client.py — retry + healing + error classification."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from specbox_supabase_mcp.lib.supabase_client import (
    SupabaseAPIError,
    SupabaseClient,
)


def _response(status: int, body: dict | list | None = None) -> MagicMock:
    m = MagicMock()
    m.status_code = status
    m.json.return_value = body if body is not None else {}
    return m


class TestRetry:
    def test_success_no_retry(self) -> None:
        client = SupabaseClient(access_token="sbp_test")
        with patch("httpx.Client") as m_http:
            instance = MagicMock()
            instance.__enter__ = lambda self_: self_
            instance.__exit__ = lambda *a: None
            instance.request.return_value = _response(200, [])
            m_http.return_value = instance
            response = client.call("op", "GET", "/x")
        assert response.status_code == 200

    def test_429_retries_then_succeeds_emits_healing(self) -> None:
        client = SupabaseClient(access_token="sbp_test", project_hint="testproj")
        responses = [_response(429), _response(200, [])]

        class _Ctx:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def request(self, *a, **kw):
                return responses.pop(0)

        captured_heal: list[dict] = []

        def capture(**kw):
            captured_heal.append(kw)

        with patch("httpx.Client", return_value=_Ctx()), patch(
            "specbox_supabase_mcp.lib.supabase_client.report_healing",
            side_effect=capture,
        ), patch("time.sleep"):
            response = client.call("secrets.list", "GET", "/x")

        assert response.status_code == 200
        assert captured_heal
        assert captured_heal[0]["root_cause"] == "rate_limit"
        assert captured_heal[0]["resolution"] == "retry"

    def test_connection_error_retries(self) -> None:
        client = SupabaseClient(access_token="sbp_test", project_hint="testproj")

        attempts = {"n": 0}

        class _Ctx:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def request(self, *a, **kw):
                attempts["n"] += 1
                if attempts["n"] == 1:
                    raise httpx.ConnectError("glitch")
                return _response(200, [])

        with patch("httpx.Client", return_value=_Ctx()), patch(
            "specbox_supabase_mcp.lib.supabase_client.report_healing"
        ), patch("time.sleep"):
            response = client.call("op", "GET", "/x")

        assert response.status_code == 200
        assert attempts["n"] == 2

    def test_404_propagates_as_supabase_error(self) -> None:
        client = SupabaseClient(access_token="sbp_test")

        class _Ctx:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def request(self, *a, **kw):
                m = _response(404, {"message": "not found"})
                return m

        with patch("httpx.Client", return_value=_Ctx()):
            with pytest.raises(SupabaseAPIError) as ei:
                client.call("op", "GET", "/x")
        assert ei.value.status_code == 404

    def test_base_url_override(self) -> None:
        client = SupabaseClient(access_token="sbp_test", base_url="https://other.test/")
        assert client.base_url == "https://other.test"
