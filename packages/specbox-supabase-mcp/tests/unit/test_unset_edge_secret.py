"""Unit tests for T3 unset_edge_secret.

Covers AC-01..AC-05 of UC-SB-3.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from specbox_supabase_mcp.tools.unset_edge_secret import (
    CONFIRM_TOKEN_LITERAL,
    unset_edge_secret,
)

TEST_PAT = "sbp_" + "ValidDummyFixtureToken01234567890abc"
PROJECT_REF = "cccccccccccccccccccc"


def _response(status: int = 200, json_body: Any = None) -> MagicMock:
    m = MagicMock()
    m.status_code = status
    m.json.return_value = json_body if json_body is not None else []
    return m


@pytest.fixture
def patch_client():  # type: ignore[no-untyped-def]
    with patch("specbox_supabase_mcp.tools.unset_edge_secret.SupabaseClient") as m_cls:
        instance = MagicMock()
        m_cls.return_value = instance
        yield instance


class TestAcceptance:
    def test_confirm_token_mismatch_blocks_call(self, patch_client) -> None:  # type: ignore[no-untyped-def]
        """AC-01: wrong token → E_CONFIRM_TOKEN_MISMATCH, zero Supabase calls."""
        out = unset_edge_secret(
            supabase_access_token=TEST_PAT,
            project_ref=PROJECT_REF,
            names=["SOMETHING"],
            confirm_token="nope",
            project_hint="motofan",
        )
        assert out["success"] is False
        assert out["error"]["code"] == "E_CONFIRM_TOKEN_MISMATCH"
        patch_client.call.assert_not_called()

    def test_partial_delete_reports_skipped(self, patch_client) -> None:  # type: ignore[no-untyped-def]
        """AC-02: names mixed existing+missing → deleted filters to existing, skipped the rest."""
        patch_client.call.side_effect = [
            _response(200, [
                {"name": "EXISTING_A", "updated_at": "t"},
                {"name": "EXISTING_B", "updated_at": "t"},
                {"name": "OTHER_UNMANAGED", "updated_at": "t"},
            ]),
            _response(200, {}),  # DELETE
        ]
        out = unset_edge_secret(
            supabase_access_token=TEST_PAT,
            project_ref=PROJECT_REF,
            names=["EXISTING_A", "EXISTING_B", "NOT_THERE"],
            confirm_token=CONFIRM_TOKEN_LITERAL,
            project_hint="motofan",
        )
        assert out["success"] is True
        assert out["data"]["deleted"] == ["EXISTING_A", "EXISTING_B"]
        assert out["data"]["skipped"] == ["NOT_THERE"]
        # Verify DELETE body only contains the deleted names.
        delete_call = patch_client.call.call_args_list[1]
        assert delete_call.args[1] == "DELETE"
        assert sorted(delete_call.kwargs["json"]) == ["EXISTING_A", "EXISTING_B"]

    def test_pre_action_engram_observation(self, patch_client) -> None:  # type: ignore[no-untyped-def]
        """AC-03: pre-action Engram observation written BEFORE the DELETE with exact IDs."""
        patch_client.call.side_effect = [
            _response(200, [{"name": "SECRET_A", "updated_at": "t"}]),
            _response(200, {}),
        ]
        captured: list[dict[str, Any]] = []
        with patch(
            "specbox_supabase_mcp.tools.unset_edge_secret.write_config_observation",
            side_effect=lambda **kw: (captured.append(kw), "obs_id"),
        ):
            unset_edge_secret(
                supabase_access_token=TEST_PAT,
                project_ref=PROJECT_REF,
                names=["SECRET_A", "SECRET_B"],
                confirm_token=CONFIRM_TOKEN_LITERAL,
                project_hint="motofan",
            )
        assert len(captured) == 1
        obs = captured[0]
        assert "PRE-ACTION" in obs["title"]
        content = obs["content"]
        assert "SECRET_A" in content  # marked for deletion
        assert PROJECT_REF in content

    def test_empty_names_rejected(self, patch_client) -> None:  # type: ignore[no-untyped-def]
        """AC-04: names=[] → E_INVALID_INPUT, zero Supabase calls."""
        out = unset_edge_secret(
            supabase_access_token=TEST_PAT,
            project_ref=PROJECT_REF,
            names=[],
            confirm_token=CONFIRM_TOKEN_LITERAL,
            project_hint="motofan",
        )
        assert out["error"]["code"] == "E_INVALID_INPUT"
        patch_client.call.assert_not_called()

    def test_all_skipped_has_idempotency_hit_true(self, patch_client) -> None:  # type: ignore[no-untyped-def]
        """AC-05: all names in skipped → heartbeat idempotency_hit=true, no DELETE issued."""
        patch_client.call.return_value = _response(200, [])  # none exist
        captured: list[dict[str, Any]] = []
        with patch(
            "specbox_supabase_mcp.tools.unset_edge_secret.report_heartbeat",
            side_effect=lambda **kw: captured.append(kw["payload"]),
        ):
            out = unset_edge_secret(
                supabase_access_token=TEST_PAT,
                project_ref=PROJECT_REF,
                names=["NOPE", "ALSO_NOPE"],
                confirm_token=CONFIRM_TOKEN_LITERAL,
                project_hint="motofan",
            )
        assert out["success"] is True
        assert out["data"]["deleted"] == []
        assert sorted(out["data"]["skipped"]) == ["ALSO_NOPE", "NOPE"]
        assert captured[-1]["idempotency_hit"] is True
        # Only the GET was issued; DELETE never happened.
        assert patch_client.call.call_count == 1
        assert patch_client.call.call_args.args[1] == "GET"
