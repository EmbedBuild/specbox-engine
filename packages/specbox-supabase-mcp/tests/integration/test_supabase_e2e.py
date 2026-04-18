"""Integration tests for specbox-supabase-mcp MVP against real Supabase.

Skipped unless SUPABASE_CI_ACCESS_TOKEN + SUPABASE_CI_PROJECT_REF are set.
All secret names are prefixed SPECBOX_CI_ so the autouse teardown can clean up.
"""

from __future__ import annotations

import os

import pytest

from specbox_supabase_mcp.tools.list_edge_secrets import list_edge_secrets
from specbox_supabase_mcp.tools.set_edge_secret import set_edge_secret
from specbox_supabase_mcp.tools.unset_edge_secret import (
    CONFIRM_TOKEN_LITERAL,
    unset_edge_secret,
)

pytestmark = pytest.mark.integration


def _creds() -> tuple[str, str]:
    return os.environ["SUPABASE_CI_ACCESS_TOKEN"], os.environ["SUPABASE_CI_PROJECT_REF"]


class TestT1SetEdgeSecret:
    def test_create_then_reuse(self) -> None:
        token, ref = _creds()
        secrets = {
            "SPECBOX_CI_ALPHA": "value-alpha",
            "SPECBOX_CI_BETA": "value-beta",
        }
        # First run — create
        first = set_edge_secret(
            supabase_access_token=token, project_ref=ref, secrets=secrets,
            project_hint="ci",
        )
        assert first["success"] is True
        assert first["data"]["all_overwritten"] is False
        assert sorted(first["data"]["previously_absent"]) == sorted(secrets.keys())

        # Second run — reuse
        second = set_edge_secret(
            supabase_access_token=token, project_ref=ref, secrets=secrets,
            project_hint="ci",
        )
        assert second["success"] is True
        assert second["data"]["all_overwritten"] is True


class TestT2ListEdgeSecrets:
    def test_diff_against_expected(self) -> None:
        token, ref = _creds()
        set_edge_secret(
            supabase_access_token=token, project_ref=ref,
            secrets={"SPECBOX_CI_GAMMA": "x"},
            project_hint="ci",
        )
        out = list_edge_secrets(
            supabase_access_token=token, project_ref=ref,
            expected_names=["SPECBOX_CI_GAMMA", "SPECBOX_CI_DOES_NOT_EXIST"],
            project_hint="ci",
        )
        assert "SPECBOX_CI_GAMMA" in out["data"]["names"]
        assert "SPECBOX_CI_DOES_NOT_EXIST" in out["data"]["missing_names"]


class TestT3UnsetEdgeSecret:
    def test_delete_existing_and_report_skipped(self) -> None:
        token, ref = _creds()
        set_edge_secret(
            supabase_access_token=token, project_ref=ref,
            secrets={"SPECBOX_CI_DELTA": "x"},
            project_hint="ci",
        )
        out = unset_edge_secret(
            supabase_access_token=token, project_ref=ref,
            names=["SPECBOX_CI_DELTA", "SPECBOX_CI_NEVER_THERE"],
            confirm_token=CONFIRM_TOKEN_LITERAL,
            project_hint="ci",
        )
        assert out["success"] is True
        assert out["data"]["deleted"] == ["SPECBOX_CI_DELTA"]
        assert out["data"]["skipped"] == ["SPECBOX_CI_NEVER_THERE"]
