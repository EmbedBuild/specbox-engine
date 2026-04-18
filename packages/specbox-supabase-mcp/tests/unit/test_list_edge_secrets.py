"""Unit tests for T2 list_edge_secrets.

Covers AC-01..AC-05 of UC-SB-2.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from specbox_supabase_mcp.tools.list_edge_secrets import list_edge_secrets

TEST_PAT = "sbp_" + "ValidDummyFixtureToken01234567890abc"
PROJECT_REF = "bbbbbbbbbbbbbbbbbbbb"


def _response(status: int = 200, json_body: Any = None) -> MagicMock:
    m = MagicMock()
    m.status_code = status
    m.json.return_value = json_body if json_body is not None else []
    return m


@pytest.fixture
def patch_client():  # type: ignore[no-untyped-def]
    with patch("specbox_supabase_mcp.tools.list_edge_secrets.SupabaseClient") as m_cls:
        instance = MagicMock()
        m_cls.return_value = instance
        yield instance


class TestAcceptance:
    def test_returns_sorted_names_and_count(self, patch_client) -> None:  # type: ignore[no-untyped-def]
        """AC-01: 4 secrets → names sorted alphabetically + count=4 + last_updated_at."""
        patch_client.call.return_value = _response(
            200,
            [
                {"name": "ZETA", "updated_at": "2026-04-18T12:00:00Z"},
                {"name": "ALPHA", "updated_at": "2026-04-17T09:00:00Z"},
                {"name": "MIKE", "updated_at": "2026-04-18T13:30:00Z"},
                {"name": "BRAVO", "updated_at": "2026-04-16T08:00:00Z"},
            ],
        )
        out = list_edge_secrets(
            supabase_access_token=TEST_PAT,
            project_ref=PROJECT_REF,
            project_hint="motofan",
        )
        assert out["success"] is True
        assert out["data"]["names"] == ["ALPHA", "BRAVO", "MIKE", "ZETA"]
        assert out["data"]["count"] == 4
        assert out["data"]["last_updated_at"] == "2026-04-18T13:30:00Z"

    def test_expected_names_diff(self, patch_client) -> None:  # type: ignore[no-untyped-def]
        """AC-02: expected=[A,B,C] actual=[A,C,D] → missing=[B] extra=[D]."""
        patch_client.call.return_value = _response(
            200,
            [
                {"name": "A", "updated_at": "2026-04-18T00:00:00Z"},
                {"name": "C", "updated_at": "2026-04-18T00:00:00Z"},
                {"name": "D", "updated_at": "2026-04-18T00:00:00Z"},
            ],
        )
        out = list_edge_secrets(
            supabase_access_token=TEST_PAT,
            project_ref=PROJECT_REF,
            expected_names=["A", "B", "C"],
            project_hint="motofan",
        )
        assert out["data"]["missing_names"] == ["B"]
        assert out["data"]["extra_names"] == ["D"]

    def test_tool_is_read_only(self, patch_client) -> None:  # type: ignore[no-untyped-def]
        """AC-03: only GET is ever invoked on the client."""
        patch_client.call.return_value = _response(200, [])
        list_edge_secrets(
            supabase_access_token=TEST_PAT,
            project_ref=PROJECT_REF,
            project_hint="motofan",
        )
        list_edge_secrets(
            supabase_access_token=TEST_PAT,
            project_ref=PROJECT_REF,
            project_hint="motofan",
        )
        # All recorded calls must be GET
        for call_ in patch_client.call.call_args_list:
            assert call_.args[1] == "GET"

    def test_defensive_parsing_never_returns_values(self, patch_client) -> None:  # type: ignore[no-untyped-def]
        """AC-04: even if response contaminated with 'value' field, data.names only has names."""
        patch_client.call.return_value = _response(
            200,
            [
                # Pretend a future Supabase API or attacker injected a `value` field.
                {"name": "SECRET_A", "value": "SHOULD_NEVER_APPEAR",
                 "updated_at": "2026-04-18T00:00:00Z"},
            ],
        )
        out = list_edge_secrets(
            supabase_access_token=TEST_PAT,
            project_ref=PROJECT_REF,
            project_hint="motofan",
        )
        # Response must be pure list of NAMES.
        assert out["data"]["names"] == ["SECRET_A"]
        import json
        assert "SHOULD_NEVER_APPEAR" not in json.dumps(out)

    def test_heartbeat_idempotency_hit_always_true(self, patch_client) -> None:  # type: ignore[no-untyped-def]
        """AC-05: read-only → idempotency_hit=true on every heartbeat."""
        patch_client.call.return_value = _response(200, [])
        captured: list[dict[str, Any]] = []
        with patch(
            "specbox_supabase_mcp.tools.list_edge_secrets.report_heartbeat",
            side_effect=lambda **kw: captured.append(kw["payload"]),
        ):
            list_edge_secrets(
                supabase_access_token=TEST_PAT,
                project_ref=PROJECT_REF,
                project_hint="motofan",
            )
        assert captured and captured[-1]["idempotency_hit"] is True
