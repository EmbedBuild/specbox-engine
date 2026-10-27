"""Tests for the v6.0.1 content-passing app_docs tools (UC-616).

Exercises both:
  * the pure helpers `read_app_docs_from_content` / `get_inheritable_values_from_content`
  * the @mcp.tool wrappers registered by `register_app_docs_tools`
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from fastmcp import FastMCP


REPO_ROOT = Path(__file__).resolve().parent.parent


# ─── Sample content fixtures ────────────────────────────────────────


VALID_PRD = """# App PRD

<!-- @specbox:zone start kind="manual" id="vision" -->
Real vision content describing the app and its purpose.
<!-- @specbox:zone end -->

<!-- @specbox:zone start kind="manual" id="audience" -->
Real audience: senior developers using SpecBox at work.
<!-- @specbox:zone end -->

<!-- @specbox:zone start kind="manual" id="scope" -->
Real scope: deliver feature X by Q3.
<!-- @specbox:zone end -->

<!-- @specbox:zone start kind="hybrid" id="success_metrics" -->
- 80% adoption by Q4
<!-- @specbox:zone end -->

<!-- @specbox:zone start kind="auto" id="roadmap" -->
- US-001
<!-- @specbox:zone end -->

<!-- @specbox:zone start kind="manual" id="stakeholders" -->
- PM: Alice
<!-- @specbox:zone end -->
"""


VALID_SPEC = """# App Spec

<!-- @specbox:zone start kind="auto" id="stack" -->
Python 3.12 + FastAPI
<!-- @specbox:zone end -->

<!-- @specbox:zone start kind="auto" id="tracking_backend" -->
- Tipo: freeform
- Path absoluto: /Users/jps/repo/doc/tracking
<!-- @specbox:zone end -->

<!-- @specbox:zone start kind="manual" id="brand_visual" -->
- Modo VEG: uniform
- VEG arquetipo: corporate
<!-- @specbox:zone end -->

<!-- @specbox:zone start kind="manual" id="conventions" -->
- Naming: snake_case
<!-- @specbox:zone end -->

<!-- @specbox:zone start kind="auto" id="autopilot" -->
- Level: equilibrado
- Image budget: 5.0 €
<!-- @specbox:zone end -->

<!-- @specbox:zone start kind="hybrid" id="canonical_decisions" -->
(none yet)
<!-- @specbox:zone end -->
"""


# ─── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def app_docs_tools():
    """Extract the registered MCP tools as raw callables for synchronous tests."""
    from server.tools.app_docs import register_app_docs_tools

    mcp = FastMCP(name="test-app-docs")
    register_app_docs_tools(mcp, engine_path=REPO_ROOT)

    async def _gather():
        out: dict[str, Any] = {}
        for name in ("read_app_docs_tool", "get_inheritable_values_tool"):
            tool = await mcp.get_tool(name)
            out[name] = tool.fn
        return out

    return asyncio.run(_gather())


# ─── read_app_docs_tool ──────────────────────────────────────────────


class TestReadAppDocsContentAPI:
    def test_happy_path_both_docs(self, app_docs_tools):
        result = app_docs_tools["read_app_docs_tool"](
            app_prd_content=VALID_PRD,
            app_spec_content=VALID_SPEC,
        )
        assert result["has_app_prd"] is True
        assert result["has_app_spec"] is True
        assert result["prd"]["well_formed"] is True
        assert result["spec"]["well_formed"] is True
        assert "OK; valores heredables disponibles" in result["summary"]

    def test_both_missing(self, app_docs_tools):
        result = app_docs_tools["read_app_docs_tool"](
            app_prd_content=None,
            app_spec_content=None,
        )
        assert result["has_app_prd"] is False
        assert result["has_app_spec"] is False
        assert result["prd"] is None
        assert result["spec"] is None
        assert "doc/app/ no existe" in result["summary"]

    def test_blank_string_treated_as_missing(self, app_docs_tools):
        result = app_docs_tools["read_app_docs_tool"](
            app_prd_content="   \n",
            app_spec_content=None,
        )
        assert result["has_app_prd"] is False

    def test_only_prd_present(self, app_docs_tools):
        result = app_docs_tools["read_app_docs_tool"](
            app_prd_content=VALID_PRD,
            app_spec_content=None,
        )
        assert result["has_app_prd"] is True
        assert result["has_app_spec"] is False
        assert "Solo uno de los documentos" in result["summary"]

    def test_malformed_prd_reports_errors(self, app_docs_tools):
        """A doc missing the required `vision` zone produces errors."""
        result = app_docs_tools["read_app_docs_tool"](
            app_prd_content="# Empty\nNo zones at all.\n",
            app_spec_content=None,
        )
        assert result["has_app_prd"] is True
        prd = result["prd"]
        # Either not well-formed OR has error-severity entries
        if prd["well_formed"]:
            pytest.fail("PRD with no required zones should not be well-formed")


# ─── get_inheritable_values_tool ─────────────────────────────────────


class TestGetInheritableValuesContentAPI:
    def test_all_false_when_no_docs(self, app_docs_tools):
        out = app_docs_tools["get_inheritable_values_tool"](
            app_prd_content=None,
            app_spec_content=None,
        )
        assert out["audience_defined"] is False
        assert out["scope_defined"] is False
        assert out["veg_mode_known"] is False
        assert out["stack_known"] is False
        assert out["backend_type"] is None

    def test_full_extraction(self, app_docs_tools):
        out = app_docs_tools["get_inheritable_values_tool"](
            app_prd_content=VALID_PRD,
            app_spec_content=VALID_SPEC,
        )
        assert out["audience_defined"] is True
        assert "senior developers" in out["audience_text"]
        assert out["scope_defined"] is True
        assert out["veg_mode_known"] is True
        assert out["veg_archetype"] == "corporate"
        assert out["stack_known"] is True
        assert "Python" in out["stack_text"]
        assert out["backend_type"] == "freeform"
        assert out["freeform_root_absolute"] == "/Users/jps/repo/doc/tracking"
        assert out["autopilot_level"] == "equilibrado"
        assert out["image_budget_eur_per_feature"] == 5.0

    def test_invalid_autopilot_value_ignored(self, app_docs_tools):
        bad_spec = VALID_SPEC.replace("Level: equilibrado", "Level: turbomax")
        out = app_docs_tools["get_inheritable_values_tool"](
            app_prd_content=VALID_PRD,
            app_spec_content=bad_spec,
        )
        assert out["autopilot_level"] is None

    def test_template_placeholder_audience_treated_as_undefined(self, app_docs_tools):
        prd = VALID_PRD.replace(
            "Real audience: senior developers using SpecBox at work.",
            "Audience: {target_name}",
        )
        out = app_docs_tools["get_inheritable_values_tool"](
            app_prd_content=prd,
            app_spec_content=VALID_SPEC,
        )
        assert out["audience_defined"] is False
        assert out["audience_text"] is None

    def test_partial_bundle_prd_only(self, app_docs_tools):
        out = app_docs_tools["get_inheritable_values_tool"](
            app_prd_content=VALID_PRD,
            app_spec_content=None,
        )
        # PRD-derived fields populated
        assert out["audience_defined"] is True
        # Spec-derived fields remain default
        assert out["stack_known"] is False
        assert out["backend_type"] is None


# ─── UC-11005: values in backticks, bold or with a comment; the 4 backends ───


def _spec_with(tipo_line: str, level_line: str = "- Level: equilibrado") -> str:
    return VALID_SPEC.replace("- Tipo: freeform", tipo_line).replace("- Level: equilibrado", level_line)


class TestInheritableValuesAsWritten:
    @pytest.mark.parametrize("backend", ["freeform", "trello", "plane", "native"])
    @pytest.mark.parametrize(
        "line",
        [
            "- Tipo: {b}",
            "- **Tipo:** {b}",
            "- **Tipo:** `{b}`",
            "- **Tipo:** `{b}` (comentario con `código` dentro)",
        ],
    )
    def test_every_backend_in_every_way_it_is_written(self, app_docs_tools, backend, line):
        out = app_docs_tools["get_inheritable_values_tool"](
            app_prd_content=VALID_PRD, app_spec_content=_spec_with(line.format(b=backend))
        )
        assert out["backend_type"] == backend

    @pytest.mark.parametrize("line", ["- Level: agresivo", "- **Level:** agresivo", "- **Level:** `agresivo`"])
    def test_autopilot_level_without_markdown(self, app_docs_tools, line):
        out = app_docs_tools["get_inheritable_values_tool"](
            app_prd_content=VALID_PRD, app_spec_content=_spec_with("- Tipo: freeform", line)
        )
        assert out["autopilot_level"] == "agresivo"

    def test_the_manager_documents_as_they_are_written(self, app_docs_tools):
        """The lines of doc/app/app_spec.md of EmbedBuild/specbox-manager that returned nothing."""
        spec = _spec_with(
            "- **Tipo:** `native` (Postgres gestionado en Supabase, proyecto `SpecBox-Cloud`)",
            "- **Level:** `agresivo`",
        ).replace("- Image budget: 5.0 €", "- **Image budget €/feature:** `5`")
        out = app_docs_tools["get_inheritable_values_tool"](app_prd_content=VALID_PRD, app_spec_content=spec)
        assert (out["backend_type"], out["autopilot_level"], out["image_budget_eur_per_feature"]) == ("native", "agresivo", 5.0)

    def test_an_unknown_value_in_backticks_is_still_ignored(self, app_docs_tools):
        out = app_docs_tools["get_inheritable_values_tool"](
            app_prd_content=VALID_PRD, app_spec_content=_spec_with("- **Tipo:** `jira`", "- **Level:** `turbo`")
        )
        assert out["backend_type"] is None and out["autopilot_level"] is None
