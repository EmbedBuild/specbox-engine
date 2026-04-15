"""Unit tests for server/tools/_mutation_helpers.py.

See doc/design/v5.23.0-full-mutations.md (Tier 1 — Shared helpers).
"""

from __future__ import annotations

import json
from pathlib import Path

from src.spec_backend import ChecklistItemDTO, ItemDTO
from src.tools import _mutation_helpers as mh


# ── validate_milestone / validate_link_type ──────────────────────────


def test_validate_milestone_accepts_h1_to_h4():
    for m in ("H1", "H2", "H3", "H4"):
        ok, err = mh.validate_milestone(m)
        assert ok is True
        assert err is None


def test_validate_milestone_rejects_invalid():
    ok, err = mh.validate_milestone("H5")
    assert ok is False
    assert "H5" in err


def test_validate_link_type_rejects_unknown():
    ok, err = mh.validate_link_type("supersedes")
    assert ok is True
    ok, err = mh.validate_link_type("bogus")
    assert ok is False
    assert "bogus" in err


# ── validate_satellite ───────────────────────────────────────────────


def test_validate_satellite_empty_rejected():
    ok, err = mh.validate_satellite("", None)
    assert ok is False


def test_validate_satellite_no_settings_accepts_any(tmp_path: Path):
    ok, err = mh.validate_satellite("anything", tmp_path / "missing.json")
    assert ok is True


def test_validate_satellite_empty_satellites_dict_accepts(tmp_path: Path):
    settings = tmp_path / "settings.local.json"
    settings.write_text(json.dumps({"multirepo": {"satellites": {}}}))
    ok, err = mh.validate_satellite("backend", settings)
    assert ok is True


def test_validate_satellite_declared_key_accepted(tmp_path: Path):
    settings = tmp_path / "settings.local.json"
    settings.write_text(
        json.dumps(
            {
                "multirepo": {
                    "satellites": {
                        "backend": {"path": "../api"},
                        "mobile": {"path": "../mobile"},
                    }
                }
            }
        )
    )
    ok, _ = mh.validate_satellite("backend", settings)
    assert ok is True


def test_validate_satellite_unknown_key_rejected(tmp_path: Path):
    settings = tmp_path / "settings.local.json"
    settings.write_text(
        json.dumps({"multirepo": {"satellites": {"backend": {}}}})
    )
    ok, err = mh.validate_satellite("mobile", settings)
    assert ok is False
    assert "declared" in err


# ── validate_ac_text ─────────────────────────────────────────────────


def test_validate_ac_text_too_short():
    issues = mh.validate_ac_text("short")
    assert "too_short" in issues
    assert "not_testable" in issues


def test_validate_ac_text_vague_but_measurable():
    issues = mh.validate_ac_text("debe responder")
    assert "vague" in issues
    assert "not_testable" not in issues


def test_validate_ac_text_gherkin_passes():
    text = "Dado un usuario autenticado cuando pulsa login entonces ve el dashboard"
    issues = mh.validate_ac_text(text)
    assert issues == []


# ── merge_meta ───────────────────────────────────────────────────────


def test_merge_meta_ignores_none_values():
    existing = {"horas": 5.0, "actor": "user"}
    updates = {"horas": None, "milestone": "H1"}
    merged, changed = mh.merge_meta(existing, updates)
    assert merged == {"horas": 5.0, "actor": "user", "milestone": "H1"}
    assert changed == ["milestone"]


def test_merge_meta_no_change_returns_empty_changed():
    existing = {"horas": 8.0, "milestone": "H2"}
    updates = {"horas": 8.0, "milestone": "H2"}
    merged, changed = mh.merge_meta(existing, updates)
    assert changed == []
    assert merged == existing


def test_merge_meta_lists_compared_deeply():
    existing = {"pantallas": ["A", "B"]}
    updates = {"pantallas": ["A", "B"]}
    _, changed = mh.merge_meta(existing, updates)
    assert changed == []

    _, changed2 = mh.merge_meta(existing, {"pantallas": ["A", "B", "C"]})
    assert changed2 == ["pantallas"]


def test_merge_meta_handles_none_existing():
    merged, changed = mh.merge_meta(None, {"milestone": "H1"})
    assert merged == {"milestone": "H1"}
    assert changed == ["milestone"]


# ── next_ac_id / format_uc_id ────────────────────────────────────────


def test_next_ac_id_empty_list_returns_ac01():
    assert mh.next_ac_id([]) == "AC-01"


def test_next_ac_id_increments_max():
    acs = [
        ChecklistItemDTO(id="AC-01", text="a"),
        ChecklistItemDTO(id="AC-03", text="c"),
        ChecklistItemDTO(id="AC-02", text="b"),
    ]
    assert mh.next_ac_id(acs) == "AC-04"


def test_format_uc_id_zero_pads():
    assert mh.format_uc_id(7) == "UC-007"
    assert mh.format_uc_id(128) == "UC-128"


# ── classify_ac ──────────────────────────────────────────────────────


def test_classify_ac_e2e_wins_over_integration():
    assert mh.classify_ac("E2E test que llama a API") == "e2e"


def test_classify_ac_integration():
    assert mh.classify_ac("Integra con el webhook de Stripe") == "integration"


def test_classify_ac_simple_default():
    assert mh.classify_ac("Muestra el nombre del usuario") == "simple"
    assert mh.classify_ac("Texto sin palabras clave") == "simple"


# ── compute_distribution ─────────────────────────────────────────────


def _uc(uc_id: str, milestone: str | None) -> ItemDTO:
    return ItemDTO(
        id=f"id-{uc_id}",
        name=f"{uc_id}: demo",
        labels=["UC"],
        meta={"uc_id": uc_id, "milestone": milestone} if milestone else {"uc_id": uc_id},
    )


def test_compute_distribution_happy_path():
    items = [
        _uc("UC-001", "H1"),
        _uc("UC-002", "H1"),
        _uc("UC-003", "H2"),
        _uc("UC-004", None),  # ignored
    ]
    ac_counts = {"UC-001": 3, "UC-002": 2, "UC-003": 5, "UC-004": 10}
    dist = mh.compute_distribution(items, ac_counts)
    assert dist["H1"]["ucs"] == ["UC-001", "UC-002"]
    assert dist["H1"]["ac_count"] == 5
    assert dist["H2"]["ac_count"] == 5
    assert dist["H3"]["ac_count"] == 0
    # Total relevant ACs = 10 (UC-004 is excluded)
    assert dist["H1"]["pct_acs"] == 0.5
    assert dist["H2"]["pct_acs"] == 0.5
