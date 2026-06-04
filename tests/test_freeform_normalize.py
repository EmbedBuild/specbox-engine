"""FreeForm exploded → items.json normalization (UC-709).

Pure-function tests (no DB) for server.migration.freeform_normalize and the
M3 actionable error in FreeformBackend memory-mode. Models the dogfooding case
that blocked DDBoss-Web-Saas: a nested index.json (15 US / 82 UC / 501 AC) that
switch_project_backend rejected with "got dict".
"""

from __future__ import annotations

import json

import pytest

from server.backends.freeform_backend import FreeformBackend
from server.migration.freeform_normalize import (
    is_flat_items,
    looks_like_exploded,
    normalize_exploded_index,
    normalize_source_content,
)


# ── dialect detection ────────────────────────────────────────────────


def test_looks_like_exploded_true_for_nested_index():
    assert looks_like_exploded({"user_stories": []}) is True
    assert looks_like_exploded({"user_stories": [{"us_id": "US-01"}]}) is True


def test_looks_like_exploded_false_for_flat_and_other():
    assert looks_like_exploded([]) is False
    assert looks_like_exploded({"foo": "bar"}) is False
    assert is_flat_items([{"id": "US-01"}]) is True
    assert is_flat_items({"user_stories": []}) is False


# ── nested → flat (degraded: AC from counts) ─────────────────────────


def _ddboss_like_index():
    """A small index.json mirroring the DDBoss exploded shape."""
    return {
        "schema_version": 1,
        "project": "DDBoss-Web-Saas",
        "user_stories": [
            {
                "us_id": "US-01",
                "name": "Migración Supabase",
                "status": "in_progress",
                "hours": 200,
                "adr": "ADR-0007",
                "use_cases": [
                    {"uc_id": "UC-001", "name": "Bootstrap", "status": "review",
                     "ac_total": 3, "ac_done": 3},
                    {"uc_id": "UC-004b", "name": "Write paths", "status": "done",
                     "ac_total": 2, "ac_done": 1},
                ],
            },
            {
                "us_id": "US-02",
                "name": "Gestor documental",
                "status": "in_progress",
                "hours": 80,
                "use_cases": [
                    {"uc_id": "UC-009", "name": "Doc store", "status": "done",
                     "ac_total": 0, "ac_done": 0},
                ],
            },
        ],
    }


def test_normalize_degraded_counts_round_trip():
    out = normalize_exploded_index(_ddboss_like_index())
    assert out["counts"] == {"us": 2, "uc": 3, "ac": 5}  # 3 + 2 + 0
    assert out["ac_degraded"] is True
    items = out["items"]
    # US present with US label and no parent.
    us01 = next(i for i in items if i["id"] == "US-01")
    assert us01["labels"] == ["US"]
    assert us01["parent_id"] is None
    assert us01["meta"]["us_id"] == "US-01"
    assert us01["meta"]["adr"] == "ADR-0007"
    # UC points at its US via parent_id.
    uc = next(i for i in items if i["id"] == "UC-004b")
    assert uc["labels"] == ["UC"]
    assert uc["parent_id"] == "US-01"
    assert uc["meta"]["us_id"] == "US-01"
    # The alpha-suffixed UC id is preserved verbatim (UC-707 parser also covers it).
    assert uc["meta"]["uc_id"] == "UC-004b"


def test_normalize_degraded_ac_done_split():
    out = normalize_exploded_index(_ddboss_like_index())
    items = out["items"]
    acs_004b = [i for i in items if i["parent_id"] == "UC-004b"]
    assert len(acs_004b) == 2
    done = [a for a in acs_004b if a["state"] == "done"]
    backlog = [a for a in acs_004b if a["state"] == "backlog"]
    assert len(done) == 1  # ac_done=1
    assert len(backlog) == 1
    # AC id namespaced under its UC.
    assert {a["id"] for a in acs_004b} == {"UC-004b::AC-01", "UC-004b::AC-02"}


# ── nested → flat (faithful: AC texts supplied) ──────────────────────


def test_normalize_faithful_with_ac_texts():
    idx = _ddboss_like_index()
    ac_texts = {
        "UC-001": [
            {"text": "Supabase CLI instalado", "done": True},
            {"text": "Link al proyecto", "done": True},
            "Extensiones activadas",  # plain str → pending
        ],
    }
    out = normalize_exploded_index(idx, ac_texts=ac_texts)
    items = out["items"]
    acs_001 = [i for i in items if i["parent_id"] == "UC-001"]
    assert len(acs_001) == 3
    assert acs_001[0]["name"] == "AC-01: Supabase CLI instalado"
    assert acs_001[0]["state"] == "done"
    assert acs_001[2]["state"] == "backlog"  # plain str → pending
    # UC-004b falls back to degraded counts (no ac_texts entry).
    assert out["ac_degraded"] is True


# ── source_content dispatcher ────────────────────────────────────────


def test_normalize_source_content_passes_flat_through_unchanged():
    flat = json.dumps([
        {"id": "US-01", "name": "US-01: x", "labels": ["US"], "parent_id": None},
        {"id": "UC-001", "name": "UC-001: y", "labels": ["UC"], "parent_id": "US-01"},
    ])
    out = normalize_source_content(flat)
    assert out["converted"] is False
    assert out["counts"] == {"us": 1, "uc": 1, "ac": 0}
    assert out["items_content"] == flat


def test_normalize_source_content_converts_nested():
    nested = json.dumps(_ddboss_like_index())
    out = normalize_source_content(nested)
    assert out["converted"] is True
    assert out["counts"] == {"us": 2, "uc": 3, "ac": 5}
    # The converted content is now a flat array the backend accepts.
    reparsed = json.loads(out["items_content"])
    assert isinstance(reparsed, list)


def test_normalize_source_content_rejects_garbage():
    with pytest.raises(ValueError, match="neither a flat items.json"):
        normalize_source_content(json.dumps({"foo": "bar"}))


# ── M3: FreeformBackend memory-mode actionable error ─────────────────


def test_freeform_memory_mode_rejects_nested_with_actionable_error():
    nested = json.dumps(_ddboss_like_index())
    with pytest.raises(ValueError, match="nested FreeForm index.json"):
        FreeformBackend(items_content=nested)
    # The message names the fix.
    try:
        FreeformBackend(items_content=nested)
    except ValueError as e:
        assert "normalize_source_content" in str(e)
        assert "AC texts live" in str(e)


def test_freeform_memory_mode_accepts_normalized_output():
    nested = json.dumps(_ddboss_like_index())
    normalized = normalize_source_content(nested)["items_content"]
    # The normalized flat array is accepted by the backend (no raise).
    backend = FreeformBackend(items_content=normalized)
    assert backend is not None


def test_freeform_memory_mode_still_rejects_plain_dict_generically():
    with pytest.raises(ValueError, match="must be a JSON array"):
        FreeformBackend(items_content=json.dumps({"foo": "bar"}))
