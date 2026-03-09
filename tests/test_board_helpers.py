"""Tests for board_helpers module."""

import pytest

from src.board_helpers import (
    build_custom_field_map,
    build_uc_description,
    build_us_description,
    extract_custom_field_value,
    find_option_id,
    get_card_custom_value,
    get_state_for_list,
    is_uc_card,
    is_us_card,
    parse_checklist_acs,
    parse_uc_description,
)


class TestBuildCustomFieldMap:
    def test_builds_map(self, sample_custom_fields):
        cf_map = build_custom_field_map(sample_custom_fields)
        assert "tipo" in cf_map
        assert cf_map["tipo"]["id"] == "cf_tipo"
        assert cf_map["tipo"]["type"] == "list"
        assert "horas" in cf_map
        assert cf_map["horas"]["type"] == "number"

    def test_empty_fields(self):
        cf_map = build_custom_field_map([])
        assert cf_map == {}


class TestExtractCustomFieldValue:
    def test_text_field(self, sample_uc_card):
        val = extract_custom_field_value(sample_uc_card, "cf_uc_id", "text")
        assert val == "UC-001"

    def test_number_field(self, sample_uc_card):
        val = extract_custom_field_value(sample_uc_card, "cf_horas", "number")
        assert val == 3.0

    def test_list_field(self, sample_uc_card, sample_custom_fields):
        val = extract_custom_field_value(sample_uc_card, "cf_tipo", "list", sample_custom_fields)
        assert val == "UC"

    def test_missing_field(self, sample_uc_card):
        val = extract_custom_field_value(sample_uc_card, "cf_nonexistent", "text")
        assert val is None


class TestIsUsUcCard:
    def test_is_us(self, sample_us_card, sample_custom_fields):
        cf_map = build_custom_field_map(sample_custom_fields)
        assert is_us_card(sample_us_card, cf_map, sample_custom_fields) is True
        assert is_uc_card(sample_us_card, cf_map, sample_custom_fields) is False

    def test_is_uc(self, sample_uc_card, sample_custom_fields):
        cf_map = build_custom_field_map(sample_custom_fields)
        assert is_uc_card(sample_uc_card, cf_map, sample_custom_fields) is True
        assert is_us_card(sample_uc_card, cf_map, sample_custom_fields) is False


class TestGetStateForList:
    def test_known_list(self, sample_lists):
        state = get_state_for_list("list_backlog", sample_lists)
        assert state == "user_stories"

    def test_done_list(self, sample_lists):
        state = get_state_for_list("list_done", sample_lists)
        assert state == "done"

    def test_unknown_list(self, sample_lists):
        state = get_state_for_list("list_unknown", sample_lists)
        assert state == "unknown"


class TestParseUcDescription:
    def test_full_parse(self, sample_uc_card):
        result = parse_uc_description(sample_uc_card["desc"])
        assert result["uc_id"] == "UC-001"
        assert result["name"] == "Iniciar sesion con email y contrasena"
        assert result["us_id"] == "US-01"
        assert result["actor"] == "Todos"
        assert result["hours"] == 3.0
        assert result["screens"] == ["1A", "1B", "1C"]
        assert len(result["acceptance_criteria"]) == 3
        assert result["acceptance_criteria"][0]["id"] == "AC-01"
        assert "Supabase" in result["context"]

    def test_empty_description(self):
        result = parse_uc_description("")
        assert result["uc_id"] == ""
        assert result["acceptance_criteria"] == []

    def test_partial_description(self):
        desc = "## UC-005: Simple test\n\n**Actor**: Admin\n"
        result = parse_uc_description(desc)
        assert result["uc_id"] == "UC-005"
        assert result["actor"] == "Admin"


class TestBuildDescriptions:
    def test_build_us_description(self):
        desc = build_us_description("US-01", "Auth", 11, "1A, 1B", "Detailed desc")
        assert "## US-01: Auth" in desc
        assert "**Horas**: 11" in desc
        assert "Detailed desc" in desc

    def test_build_uc_description(self):
        desc = build_uc_description(
            "UC-001", "Login", "US-01", "Auth", "Todos", 3, "1A",
            ["Validates email", "Shows error"], "Supabase Auth"
        )
        assert "## UC-001: Login" in desc
        assert "**User Story**: US-01 Auth" in desc
        assert "AC-01: Validates email" in desc
        assert "AC-02: Shows error" in desc
        assert "Supabase Auth" in desc


class TestParseChecklistAcs:
    def test_parses_acs(self, sample_checklists):
        acs = parse_checklist_acs(sample_checklists)
        assert len(acs) == 3
        assert acs[0].id == "AC-01"
        assert acs[0].text == "Valida formato email"
        assert acs[0].done is False
        assert acs[2].done is True

    def test_empty_checklists(self):
        acs = parse_checklist_acs([])
        assert acs == []

    def test_non_ac_checklist(self):
        checklists = [{"name": "Random Stuff", "checkItems": [{"name": "item1", "state": "complete"}]}]
        acs = parse_checklist_acs(checklists)
        assert acs == []


class TestFindOptionId:
    def test_finds_option(self, sample_custom_fields):
        opt_id = find_option_id(sample_custom_fields, "tipo", "US")
        assert opt_id == "opt_us"

    def test_not_found(self, sample_custom_fields):
        opt_id = find_option_id(sample_custom_fields, "tipo", "NONEXISTENT")
        assert opt_id is None
