"""US-49 · UC-4901 — reading the system tokens and checking a document against them."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from server.design_system import (
    SystemTokensError,
    allowed_values,
    find_values_outside,
    parse_system_tokens,
)

FIXTURE = Path(__file__).parent / "fixtures" / "design_system" / "tinta.design-system.tokens.json"


@pytest.fixture(scope="module")
def tinta():
    return parse_system_tokens(FIXTURE.read_text(encoding="utf-8"), source="src/styles/tokens/design-system.tokens.json")


def _minimal(**overrides) -> dict:
    data = {
        "name": "Mini",
        "version": 1,
        "color": {
            "themes": [{"id": "light"}, {"id": "dark"}],
            "tokens": [
                {"name": "primary", "value": {"light": "#112233", "dark": "#DDEEFF"}},
                {"name": "background", "value": "#FFFFFF"},
                {"name": "text", "value": {"light": "{primary}", "dark": "#000000"}},
            ],
        },
        "type": {
            "families": {"sans": '"Work Sans", sans-serif'},
            "groups": [
                {
                    "name": "All",
                    "family": "sans",
                    "styles": [
                        {"name": "h1", "fontSize": "28px", "lineHeight": "34px", "fontWeight": 600},
                        {"name": "h2", "fontSize": "22px", "lineHeight": "28px", "fontWeight": 600},
                        {"name": "body", "fontSize": "15px", "lineHeight": "22px", "fontWeight": 400},
                    ],
                }
            ],
        },
        "radius": {"tokens": [{"name": "md", "value": "8px"}]},
    }
    data.update(overrides)
    return data


# ── parsing ─────────────────────────────────────────────────────────────


class TestParse:
    def test_reads_the_real_system(self, tinta):
        assert tinta.name == "SpecBox"
        assert tinta.themes == ("light", "dark")
        assert tinta.source == "src/styles/tokens/design-system.tokens.json"
        assert tinta.primary_family("sans") == "IBM Plex Sans"
        assert tinta.primary_family("mono") == "IBM Plex Mono"
        assert tinta.font_weights() == {400, 500, 600}
        assert tinta.radius_role("md") == "6px"

    def test_resolves_aliases_per_theme(self, tinta):
        # accent = {ink-900} in both themes → the ink-900 value of each theme.
        assert tinta.color("accent", "light") == tinta.color("ink-900", "light") == "#1A1B1E"
        assert tinta.color("accent", "dark") == tinta.color("ink-900", "dark") == "#F2F1EE"
        assert tinta.color("danger-text", "light") == tinta.color("status-blocked-text", "light")

    def test_maps_semantic_roles(self, tinta):
        assert tinta.role_color_name("primary") == "accent"
        assert tinta.role_color("background") == "#F7F6F4"
        assert tinta.role_color("surface") == "#FFFFFF"
        assert tinta.role_color("text_primary") == "#1A1B1E"
        assert tinta.role_color("error") == "#991B1B"
        assert tinta.text_role("h1").name == "display-xl"
        assert tinta.text_role("body").name == "body-md"

    def test_plain_names_are_read_too(self):
        tokens = parse_system_tokens(json.dumps(_minimal()))
        assert tokens.role_color("primary") == "#112233"
        assert tokens.role_color("text_primary") == "#112233"  # alias of primary
        assert tokens.role_color("text_primary", "dark") == "#000000"
        assert tokens.text_role("h1").font_size == "28px"

    def test_single_value_applies_to_every_theme(self):
        tokens = parse_system_tokens(json.dumps(_minimal()))
        assert tokens.color("background", "dark") == "#FFFFFF"

    @pytest.mark.parametrize(
        ("content", "message"),
        [
            ("not json", "not valid JSON"),
            ("[]", "JSON object"),
            (json.dumps({"type": {}}), "colour tokens"),
        ],
    )
    def test_rejects_what_is_not_the_format(self, content, message):
        with pytest.raises(SystemTokensError, match=message):
            parse_system_tokens(content)

    def test_rejects_an_alias_to_nowhere(self):
        data = _minimal()
        data["color"]["tokens"][2]["value"] = "{nope}"
        with pytest.raises(SystemTokensError, match="'nope'"):
            parse_system_tokens(json.dumps(data))

    def test_rejects_an_alias_cycle(self):
        data = _minimal()
        data["color"]["tokens"] += [{"name": "a", "value": "{b}"}, {"name": "b", "value": "{a}"}]
        with pytest.raises(SystemTokensError, match="cycle"):
            parse_system_tokens(json.dumps(data))

    def test_names_the_missing_roles(self):
        data = _minimal()
        data["color"]["tokens"] = [{"name": "primary", "value": "#112233"}]
        with pytest.raises(SystemTokensError) as exc:
            parse_system_tokens(json.dumps(data))
        assert "background" in str(exc.value) and "text_primary" in str(exc.value)

    def test_rejects_a_style_with_an_unknown_family(self):
        data = _minimal()
        data["type"]["groups"][0]["family"] = "serif"
        with pytest.raises(SystemTokensError, match="family 'serif'"):
            parse_system_tokens(json.dumps(data))


# ── conformance ─────────────────────────────────────────────────────────


class TestConformance:
    def test_allowed_values_come_from_token_values(self, tinta):
        allowed = allowed_values(tinta)
        assert "#1A1B1E" in allowed.colors
        assert "rgba(26,27,30,0.55)" in allowed.colors
        assert {"6px", "30px", "-0.01em", "120ms", "999px"} <= allowed.lengths
        assert allowed.weights == {400, 500, 600}
        assert {"ibm plex sans", "ibm plex mono", "sans-serif"} <= allowed.families

    def test_a_document_with_only_token_values_is_clean(self, tinta):
        doc = (
            "---\ncolors:\n  primary: '#1A1B1E'\ntypography:\n  fontFamily:\n"
            "    body: '\"IBM Plex Sans\", sans-serif'\n  fontWeight:\n    semibold: 600\n---\n\n"
            "## Shapes\n\n- radius-md: `6px`, sombra `0 1px 2px 0 rgba(26, 27, 30, 0.06)`\n"
        )
        assert find_values_outside(doc, tinta) == []

    def test_reports_each_kind_of_value_outside(self, tinta):
        doc = (
            "---\ncolors:\n  primary: '#5B5BD6'\ntypography:\n  fontFamily:\n    heading: Inter, sans-serif\n"
            "  fontWeight:\n    bold: 700\n  lineHeight:\n    normal: 1.5\ntheme:\n  roundness: ROUND_FULL\n"
            "  headlineFont: SPACE_GROTESK\n---\n\n"
            "Texto con `#0EA5E9`, borde 3px y pesos 400/800 en Roboto.\n"
        )
        found = {(d.kind, d.value) for d in find_values_outside(doc, tinta)}
        assert ("color", "#5B5BD6") in found
        assert ("font_family", "inter") in found
        assert ("font_weight", "700") in found
        assert ("line_height", "1.5") in found
        assert ("length", "ROUND_FULL (9999px)") in found
        assert ("font_family", "space grotesk") in found
        assert ("color", "#0EA5E9") in found
        assert ("length", "3px") in found
        assert ("font_weight", "800") in found
        assert ("font_family", "roboto") in found

    def test_says_where_each_value_is(self, tinta):
        doc = "---\ncolors:\n  primary: '#5B5BD6'\n---\n\nLínea uno\nLínea con #ABCDEF\n"
        where = {d.value: d.where for d in find_values_outside(doc, tinta)}
        assert where["#5B5BD6"] == "front-matter: colors.primary"
        assert where["#ABCDEF"] == "line 7"

    def test_an_issue_number_is_not_a_colour(self, tinta):
        assert find_values_outside("Ver PR #128 y #4507.", tinta) == []
