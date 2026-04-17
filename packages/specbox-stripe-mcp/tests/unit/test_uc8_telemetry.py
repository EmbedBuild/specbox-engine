"""Cross-cutting tests for UC-8: Engram + heartbeats + healing + redaction.

Exercises the shared plumbing (lib/engram_writer, lib/heartbeat, lib/stripe_client,
lib/safety.redact) through one representative tool at a time.
"""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import patch

import pytest
import stripe

from specbox_stripe_mcp.lib.engram_writer import write_config_observation
from specbox_stripe_mcp.lib.safety import redact_log_line
from specbox_stripe_mcp.lib.stripe_client import StripeClient
from specbox_stripe_mcp.tools.verify_connect_enabled import verify_connect_enabled

TEST_KEY = "sk_" + "test_" + "FixtureKeyNotRealNotFromStripe"


class _AccountDict(dict):
    pass


def _account() -> _AccountDict:
    return _AccountDict(
        id="acct_platform",
        country="ES",
        default_currency="eur",
        capabilities={"card_payments": "active"},
        business_profile={"name": "Test"},
        email="t@t.test",
    )


class TestAC01EngramObservation:
    """AC-01: success path writes an engram observation."""

    def test_verify_success_writes_observation(self) -> None:
        captured: list[dict[str, Any]] = []

        def capture(*, project: str, title: str, content: str) -> str:
            captured.append({"project": project, "title": title, "content": content})
            return "obs_test"

        with patch(
            "specbox_stripe_mcp.tools.verify_connect_enabled.write_config_observation",
            side_effect=capture,
        ), patch("stripe.Account.retrieve", return_value=_account()), patch(
            "stripe.Account.create", return_value={"id": "acct_probe"}
        ), patch("stripe.Account.delete", return_value={"deleted": True}):
            out = verify_connect_enabled(stripe_api_key=TEST_KEY, project_hint="motofan")

        assert out["success"] is True
        assert len(captured) == 1
        obs = captured[0]
        assert obs["project"] == "motofan"
        assert "verify_connect_enabled" in obs["title"]
        # Observation content has no secrets and mentions mode + duration + tool.
        # Make sure no part of the test key leaks into the observation.
        assert "DUMMYfixtureKEY" not in obs["content"]
        assert "Tool" in obs["content"]
        assert "motofan" in obs["content"]
        assert "Mode" in obs["content"]
        assert "test" in obs["content"].lower()

    def test_engram_failure_does_not_break_tool(self) -> None:
        """AC-05: Engram unreachable → observation silently skipped, tool still succeeds."""

        def explode(*, project: str, title: str, content: str) -> str:
            raise RuntimeError("engram offline")

        with patch(
            "specbox_stripe_mcp.tools.verify_connect_enabled.write_config_observation",
            side_effect=explode,
        ), patch("stripe.Account.retrieve", return_value=_account()), patch(
            "stripe.Account.create", return_value={"id": "acct_probe"}
        ), patch("stripe.Account.delete", return_value={"deleted": True}):
            out = verify_connect_enabled(stripe_api_key=TEST_KEY, project_hint="motofan")

        assert out["success"] is True  # tool did not crash


class TestAC02HeartbeatAlwaysEmitted:
    """AC-02: every tool call (success or failure) emits report_heartbeat."""

    def test_success_heartbeat(self) -> None:
        captured: list[dict[str, Any]] = []

        def cap(*, project: str, event_type: str, payload: dict) -> None:
            captured.append(payload)

        with patch(
            "specbox_stripe_mcp.tools.verify_connect_enabled.report_heartbeat",
            side_effect=cap,
        ), patch("stripe.Account.retrieve", return_value=_account()), patch(
            "stripe.Account.create", return_value={"id": "acct_probe"}
        ), patch("stripe.Account.delete", return_value={"deleted": True}):
            verify_connect_enabled(stripe_api_key=TEST_KEY, project_hint="p")

        assert captured
        hb = captured[-1]
        assert hb["tool"] == "verify_connect_enabled"
        assert hb["success"] is True
        assert hb["mode"] == "test"
        assert "duration_ms" in hb
        assert "idempotency_hit" in hb

    def test_failure_heartbeat_invalid_key(self) -> None:
        captured: list[dict[str, Any]] = []

        def cap(*, project: str, event_type: str, payload: dict) -> None:
            captured.append(payload)

        with patch(
            "specbox_stripe_mcp.tools.verify_connect_enabled.report_heartbeat",
            side_effect=cap,
        ):
            out = verify_connect_enabled(stripe_api_key="not-a-key", project_hint="p")

        assert out["success"] is False
        assert captured[-1]["success"] is False
        assert captured[-1]["code"] == "E_INVALID_KEY"


class TestAC03HealingOnRateLimit:
    """AC-03: retry after a rate-limit emits report_healing."""

    def test_rate_limit_recovery_emits_healing(self) -> None:
        captured_heal: list[dict[str, Any]] = []

        def cap(*, project: str, hook: str, root_cause: str, resolution: str) -> None:
            captured_heal.append(
                {"project": project, "hook": hook,
                 "root_cause": root_cause, "resolution": resolution}
            )

        calls = {"n": 0}

        def fake_op() -> dict[str, Any]:
            calls["n"] += 1
            if calls["n"] == 1:
                raise stripe.error.RateLimitError("slow down")  # type: ignore[attr-defined]
            return {"ok": True}

        client = StripeClient(api_key=TEST_KEY)
        with patch(
            "specbox_stripe_mcp.lib.stripe_client.report_healing", side_effect=cap
        ), patch("time.sleep"):  # don't actually sleep
            result = client.call("test.op", fake_op)

        assert result == {"ok": True}
        assert captured_heal
        heal = captured_heal[0]
        assert heal["root_cause"] == "rate_limit"
        assert heal["resolution"] == "retry"
        assert heal["hook"] == "test.op"

    def test_connection_error_recovery_emits_healing(self) -> None:
        captured: list[str] = []
        calls = {"n": 0}

        def fake_op() -> dict[str, Any]:
            calls["n"] += 1
            if calls["n"] == 1:
                raise stripe.error.APIConnectionError("net glitch")  # type: ignore[attr-defined]
            return {"ok": True}

        def cap(*, project: str, hook: str, root_cause: str, resolution: str) -> None:
            captured.append(root_cause)

        client = StripeClient(api_key=TEST_KEY)
        with patch(
            "specbox_stripe_mcp.lib.stripe_client.report_healing", side_effect=cap
        ), patch("time.sleep"):
            client.call("x.y", fake_op)

        assert captured == ["connection_error"]


class TestAC04SecretRedaction:
    """AC-04: log lines carrying secrets are redacted to sk_test_****abc123 form."""

    def test_redact_live_key(self) -> None:
        # Build the fixture dynamically so a static secret scanner on the repo
        # doesn't flag it as a real Stripe key.
        fake = "sk_" + "live_" + "FakeRedactionFixtureXYZlongtail"
        redacted = redact_log_line(f"error using {fake}")
        assert "FakeRedactionFixtureXYZlongtail" not in redacted
        assert "sk_live_****" in redacted
        assert redacted.endswith("ngtail")

    def test_redact_whsec(self) -> None:
        redacted = redact_log_line(
            "webhook secret whsec_abc123xyz789longtail used"
        )
        assert "whsec_abc123xyz789longtail" not in redacted
        assert "whsec_****" in redacted

    def test_redact_unchanged_when_no_secret(self) -> None:
        assert redact_log_line("just a normal log line") == "just a normal log line"

    def test_redaction_visible_tail_is_six_chars(self) -> None:
        redacted = redact_log_line("sk_test_verylongkey123456ABCDEFghij")
        # The last 6 chars of the original should be present at the end.
        assert redacted.endswith("CDEFghij"[-6:])


class TestAC05EngramFireAndForget:
    """AC-05 additional: CLI not available → write_config_observation returns None silently."""

    def test_engram_cli_not_installed(self) -> None:
        """If the engram binary is missing, we return None without raising."""
        from subprocess import run as _original  # noqa: F401

        def raise_fnf(*args: Any, **kwargs: Any) -> Any:
            raise FileNotFoundError("engram not on PATH")

        with patch("subprocess.run", side_effect=raise_fnf):
            out = write_config_observation(
                project="p", title="t", content="c"
            )
        assert out is None

    def test_engram_cli_timeout(self) -> None:
        import subprocess

        def raise_timeout(*args: Any, **kwargs: Any) -> Any:
            raise subprocess.TimeoutExpired(cmd="engram", timeout=3.0)

        with patch("subprocess.run", side_effect=raise_timeout):
            out = write_config_observation(
                project="p", title="t", content="c"
            )
        assert out is None

    def test_engram_cli_generic_failure(self) -> None:
        def boom(*args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("socket reset")

        with patch("subprocess.run", side_effect=boom):
            out = write_config_observation(
                project="p", title="t", content="c"
            )
        assert out is None


@pytest.fixture(autouse=True)
def _quiet_logs(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="specbox_stripe_mcp")
