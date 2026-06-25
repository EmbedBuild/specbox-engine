"""Tests for the VEG visual-provider abstraction (US-29 · UC-2901).

Covers AC-01 (validation), AC-02 (legacy ⇒ stitch), AC-03 (claude_design
preferred when gate ready), AC-04 (claude_design config block).
"""

from __future__ import annotations

import pytest

from server.veg.visual_provider import (
    DEFAULT_PROVIDERS,
    GateResult,
    VisualProviderConfigError,
    claude_design_config,
    parse_providers,
    resolve_effective_provider,
)


# --------------------------------------------------------------------------
# AC-01 — validation of veg.providers
# --------------------------------------------------------------------------

def test_accepts_stitch_only() -> None:
    assert parse_providers({"veg": {"providers": ["stitch"]}}) == ["stitch"]


def test_accepts_claude_design_only() -> None:
    assert parse_providers({"veg": {"providers": ["claude_design"]}}) == [
        "claude_design"
    ]


def test_accepts_both() -> None:
    assert parse_providers(
        {"veg": {"providers": ["stitch", "claude_design"]}}
    ) == ["stitch", "claude_design"]


def test_dedupes_preserving_order() -> None:
    assert parse_providers(
        {"veg": {"providers": ["claude_design", "stitch", "claude_design"]}}
    ) == ["claude_design", "stitch"]


def test_unknown_provider_raises_naming_the_value() -> None:
    with pytest.raises(VisualProviderConfigError) as exc:
        parse_providers({"veg": {"providers": ["figma"]}})
    assert "figma" in str(exc.value)


def test_empty_providers_list_raises() -> None:
    with pytest.raises(VisualProviderConfigError):
        parse_providers({"veg": {"providers": []}})


# --------------------------------------------------------------------------
# AC-02 — a project without veg.providers resolves to stitch (legacy intact)
# --------------------------------------------------------------------------

def test_no_settings_defaults_to_stitch() -> None:
    assert parse_providers(None) == list(DEFAULT_PROVIDERS) == ["stitch"]


def test_legacy_config_without_veg_block_defaults_to_stitch() -> None:
    # A real legacy settings.local.json: has stitch + plane but no veg.
    legacy = {"stitch": {"projectId": "p_123"}, "plane": {"defaultProject": "X"}}
    assert parse_providers(legacy) == ["stitch"]


def test_veg_block_without_providers_key_defaults_to_stitch() -> None:
    assert parse_providers({"veg": {"enabled": True}}) == ["stitch"]


def test_default_provider_resolves_to_stitch_effective() -> None:
    providers = parse_providers(None)
    resolved = resolve_effective_provider(providers, gate=None)
    assert resolved.effective == "stitch"
    assert resolved.claude_design_pending is False


# --------------------------------------------------------------------------
# AC-03 — claude_design preferred when both active AND gate ready
# --------------------------------------------------------------------------

def test_both_providers_with_ready_gate_prefers_claude_design() -> None:
    providers = ["stitch", "claude_design"]
    resolved = resolve_effective_provider(providers, GateResult(ready=True))
    assert resolved.effective == "claude_design"
    assert resolved.fallback == "stitch"
    assert resolved.claude_design_pending is False


def test_claude_design_only_with_ready_gate_has_no_fallback() -> None:
    resolved = resolve_effective_provider(
        ["claude_design"], GateResult(ready=True)
    )
    assert resolved.effective == "claude_design"
    assert resolved.fallback is None


def test_both_providers_with_not_ready_gate_falls_back_to_stitch_pending() -> None:
    resolved = resolve_effective_provider(
        ["stitch", "claude_design"],
        GateResult(ready=False, reason="missing dist/ at /repo"),
    )
    assert resolved.effective == "stitch"
    assert resolved.claude_design_pending is True
    assert "dist/" in resolved.pending_reason


def test_claude_design_only_not_ready_reports_pending_without_raising() -> None:
    # JR-CD.3: no design-system yet → pending, never raises, /plan continues.
    resolved = resolve_effective_provider(
        ["claude_design"],
        GateResult(ready=False, reason="no compiled design-system"),
    )
    assert resolved.effective == "claude_design"
    assert resolved.claude_design_pending is True
    assert resolved.pending_reason == "no compiled design-system"


def test_stitch_only_ignores_gate() -> None:
    resolved = resolve_effective_provider(["stitch"], gate=None)
    assert resolved.effective == "stitch"
    assert resolved.claude_design_pending is False


# --------------------------------------------------------------------------
# AC-04 — veg.claude_design config block
# --------------------------------------------------------------------------

def test_claude_design_config_reads_block() -> None:
    settings = {
        "veg": {
            "providers": ["claude_design"],
            "claude_design": {"projectId": "uuid-1", "syncRepo": "salacal-web"},
        }
    }
    block = claude_design_config(settings)
    assert block["projectId"] == "uuid-1"
    assert block["syncRepo"] == "salacal-web"


def test_claude_design_config_absent_returns_empty() -> None:
    assert claude_design_config({"veg": {"providers": ["stitch"]}}) == {}
    assert claude_design_config(None) == {}


def test_claude_design_config_missing_projectid_is_readable() -> None:
    # projectId absent (not yet created) must be safely readable as None.
    settings = {"veg": {"claude_design": {"syncRepo": "web"}}}
    block = claude_design_config(settings)
    assert block.get("projectId") is None
