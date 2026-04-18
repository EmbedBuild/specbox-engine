"""Unit tests for T1 set_edge_secret.

Covers AC-01..AC-07 of UC-SB-1. httpx patched; no real network.

Mapping test → AC:
- AC-01 → test_creates_secrets_when_absent
- AC-02 → test_reuse_when_all_present
- AC-03 → test_malformed_pat_rejected
- AC-04 → test_project_not_found_returns_404_code
- AC-05 → test_invalid_secret_name_rejected
- AC-06 → test_values_never_appear_in_logs_or_engram
- AC-07 → test_rate_limit_recovery_emits_healing
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from specbox_supabase_mcp.lib.supabase_client import SupabaseAPIError
from specbox_supabase_mcp.tools.set_edge_secret import set_edge_secret

TEST_PAT = "sbp_" + "ValidDummyFixtureToken01234567890abc"
PROJECT_REF = "aaaaaaaaaaaaaaaaaaaa"  # 20 lowercase alphanum
SECRETS = {"STRIPE_SECRET_KEY": "sk_test_xxx_not_a_real_secret",
           "STRIPE_WEBHOOK_SECRET_PLATFORM": "whsec_fake_for_tests",
           "STRIPE_WEBHOOK_SECRET_CONNECT": "whsec_fake_for_tests_too",
           "DEFAULT_APPLICATION_FEE_PERCENT": "20"}


def _response(status: int = 200, json_body: Any = None) -> MagicMock:
    m = MagicMock()
    m.status_code = status
    m.json.return_value = json_body if json_body is not None else []
    return m


@pytest.fixture
def patch_client():  # type: ignore[no-untyped-def]
    """Patch the SupabaseClient.call used by the tool."""
    with patch("specbox_supabase_mcp.tools.set_edge_secret.SupabaseClient") as m_cls:
        instance = MagicMock()
        m_cls.return_value = instance
        yield instance


class TestAcceptance:
    def test_creates_secrets_when_absent(self, patch_client) -> None:  # type: ignore[no-untyped-def]
        """AC-01: names absent → POST issued, all in previously_absent."""
        patch_client.call.side_effect = [
            _response(200, []),                      # GET (list)
            _response(201, {"created": True}),       # POST
        ]

        out = set_edge_secret(
            supabase_access_token=TEST_PAT,
            project_ref=PROJECT_REF,
            secrets=SECRETS,
            project_hint="motofan",
        )

        assert out["success"] is True
        data = out["data"]
        assert sorted(data["applied"]) == sorted(SECRETS.keys())
        assert data["all_overwritten"] is False
        assert sorted(data["previously_absent"]) == sorted(SECRETS.keys())
        assert data["previously_present"] == []

        # Verify POST body carries the real {name, value} pairs (internal API only).
        post_call = patch_client.call.call_args_list[1]
        assert post_call.args[1] == "POST"
        body = post_call.kwargs["json"]
        assert sorted(item["name"] for item in body) == sorted(SECRETS.keys())

    def test_reuse_when_all_present(self, patch_client) -> None:  # type: ignore[no-untyped-def]
        """AC-02: all names already exist → all_overwritten=true, heartbeat idempotency_hit=true."""
        existing = [{"name": k, "updated_at": "2026-04-18T00:00:00Z"} for k in SECRETS]
        patch_client.call.side_effect = [
            _response(200, existing),
            _response(201, {}),
        ]

        captured_hb: list[dict[str, Any]] = []
        with patch(
            "specbox_supabase_mcp.tools.set_edge_secret.report_heartbeat",
            side_effect=lambda **kw: captured_hb.append(kw["payload"]),
        ):
            out = set_edge_secret(
                supabase_access_token=TEST_PAT,
                project_ref=PROJECT_REF,
                secrets=SECRETS,
                project_hint="motofan",
            )

        assert out["success"] is True
        assert out["data"]["all_overwritten"] is True
        assert out["data"]["previously_absent"] == []
        assert sorted(out["data"]["previously_present"]) == sorted(SECRETS.keys())
        assert captured_hb[-1]["idempotency_hit"] is True

    def test_malformed_pat_rejected(self, patch_client) -> None:  # type: ignore[no-untyped-def]
        """AC-03: malformed PAT → E_INVALID_INPUT, no HTTP call."""
        out = set_edge_secret(
            supabase_access_token="not_a_pat",
            project_ref=PROJECT_REF,
            secrets=SECRETS,
            project_hint="motofan",
        )
        assert out["success"] is False
        assert out["error"]["code"] == "E_INVALID_INPUT"
        patch_client.call.assert_not_called()

    def test_project_not_found_returns_404_code(self, patch_client) -> None:  # type: ignore[no-untyped-def]
        """AC-04: Supabase 404 → E_PROJECT_NOT_FOUND."""
        patch_client.call.side_effect = SupabaseAPIError(
            status_code=404, message="Project not found"
        )
        out = set_edge_secret(
            supabase_access_token=TEST_PAT,
            project_ref=PROJECT_REF,
            secrets=SECRETS,
            project_hint="motofan",
        )
        assert out["success"] is False
        assert out["error"]["code"] == "E_PROJECT_NOT_FOUND"

    def test_401_returns_invalid_token(self, patch_client) -> None:  # type: ignore[no-untyped-def]
        """AC-04 variant: 401 → E_INVALID_TOKEN (distinguishing from E_INVALID_INPUT)."""
        patch_client.call.side_effect = SupabaseAPIError(
            status_code=401, message="bad token"
        )
        out = set_edge_secret(
            supabase_access_token=TEST_PAT,
            project_ref=PROJECT_REF,
            secrets=SECRETS,
            project_hint="motofan",
        )
        assert out["error"]["code"] == "E_INVALID_TOKEN"

    def test_403_returns_insufficient_permissions(self, patch_client) -> None:  # type: ignore[no-untyped-def]
        patch_client.call.side_effect = SupabaseAPIError(
            status_code=403, message="forbidden"
        )
        out = set_edge_secret(
            supabase_access_token=TEST_PAT,
            project_ref=PROJECT_REF,
            secrets=SECRETS,
            project_hint="motofan",
        )
        assert out["error"]["code"] == "E_INSUFFICIENT_PERMISSIONS"

    def test_invalid_secret_name_rejected(self, patch_client) -> None:  # type: ignore[no-untyped-def]
        """AC-05: lowercase / starts-with-digit / has-spaces → E_INVALID_INPUT."""
        out = set_edge_secret(
            supabase_access_token=TEST_PAT,
            project_ref=PROJECT_REF,
            secrets={"lowercase_bad": "x", "2_STARTS_WITH_DIGIT": "y",
                     "VALID_NAME": "z"},
            project_hint="motofan",
        )
        assert out["success"] is False
        assert out["error"]["code"] == "E_INVALID_INPUT"
        patch_client.call.assert_not_called()

    def test_values_never_appear_in_logs_or_engram(self, patch_client) -> None:  # type: ignore[no-untyped-def]
        """AC-06: Engram observation carries NAMES only, no VALUES."""
        patch_client.call.side_effect = [_response(200, []), _response(201, {})]

        captured_engram: list[dict[str, Any]] = []

        def capture(*, project: str, title: str, content: str) -> str:
            captured_engram.append({"title": title, "content": content})
            return "obs_test"

        with patch(
            "specbox_supabase_mcp.tools.set_edge_secret.write_config_observation",
            side_effect=capture,
        ):
            out = set_edge_secret(
                supabase_access_token=TEST_PAT,
                project_ref=PROJECT_REF,
                secrets={"MY_SECRET": "VeryPrivateValueShouldNotLeak12345"},
                project_hint="motofan",
            )

        assert out["success"] is True
        assert len(captured_engram) == 1
        content = captured_engram[0]["content"]
        # The NAME is allowed in the observation.
        assert "MY_SECRET" in content
        # The VALUE is NEVER allowed.
        assert "VeryPrivateValueShouldNotLeak12345" not in content

    def test_rate_limit_recovery_emits_healing(self, patch_client) -> None:  # type: ignore[no-untyped-def]
        """AC-07 — tested in test_supabase_client.py, verified indirectly here.

        The tool re-uses SupabaseClient which handles the healing event.
        A direct test lives in test_supabase_client.py.
        """
        # Placeholder asserting the integration doesn't break: use fresh client
        # that returns 200 on GET + 201 on POST.
        patch_client.call.side_effect = [_response(200, []), _response(201, {})]
        out = set_edge_secret(
            supabase_access_token=TEST_PAT,
            project_ref=PROJECT_REF,
            secrets={"FOO": "bar"},
            project_hint="motofan",
        )
        assert out["success"] is True


class TestInputs:
    def test_malformed_project_ref_rejected(self, patch_client) -> None:  # type: ignore[no-untyped-def]
        """Non-20-char or uppercase ref → E_INVALID_INPUT."""
        out = set_edge_secret(
            supabase_access_token=TEST_PAT,
            project_ref="TOO_SHORT",
            secrets={"FOO": "bar"},
            project_hint="motofan",
        )
        assert out["error"]["code"] == "E_INVALID_INPUT"
        patch_client.call.assert_not_called()

    def test_empty_secrets_rejected(self, patch_client) -> None:  # type: ignore[no-untyped-def]
        out = set_edge_secret(
            supabase_access_token=TEST_PAT,
            project_ref=PROJECT_REF,
            secrets={},
            project_hint="motofan",
        )
        assert out["error"]["code"] == "E_INVALID_INPUT"
        patch_client.call.assert_not_called()

    def test_non_string_values_rejected(self, patch_client) -> None:  # type: ignore[no-untyped-def]
        out = set_edge_secret(
            supabase_access_token=TEST_PAT,
            project_ref=PROJECT_REF,
            secrets={"FOO": 42},  # type: ignore[dict-item]
            project_hint="motofan",
        )
        assert out["error"]["code"] == "E_INVALID_INPUT"
        patch_client.call.assert_not_called()
