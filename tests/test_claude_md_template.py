"""UC-12209 — el CLAUDE.md de plantilla se queda en lo que el agente necesita en cada sesión.

- AC-01: el CLAUDE.md que genera la plantilla ocupa 200 líneas o menos (todos los stacks).
- AC-02: cada sección retirada aparece en una skill o en la documentación del engine
  (``RELOCATIONS``, la guía ``doc/guides/claude-md.md``); la tabla del changelog va con la release.
- AC-03: ``upgrade_project`` con el CLAUDE.md del cliente sustituye solo las zonas de la plantilla
  y deja lo del proyecto byte a byte.
- AC-04: las reglas innegociables están en la plantilla, cada una en su zona.
- AC-05: un CLAUDE.md que ya existía (sin marcadores, el de la plantilla 6.37) solo cambia con
  ``upgrade_project``, que antes devuelve qué sale y adónde va; sin su contenido, no se toca.

Estado real y sucio (UC-827): ``tests/fixtures/claude_md/proyecto_6_37.md`` es la plantilla 6.37
rellenada, con dos secciones propias del proyecto (una con un ``##`` dentro de un bloque de código).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastmcp import FastMCP

from server.claude_md import (
    GUIDE,
    PROJECT_SECTIONS,
    RELOCATIONS,
    MalformedZones,
    claude_md_for_upgrade,
    merge_claude_md,
    split_zones,
    zone_ids,
)
from server.coordination.scope import CallerScope
from server.tools.onboarding import _generate_onboarding_files

ENGINE = Path(__file__).resolve().parent.parent
OLD = (ENGINE / "tests" / "fixtures" / "claude_md" / "proyecto_6_37.md").read_text(encoding="utf-8")
STACKS = ("flutter", "react", "python", "go", "google-apps-script")
ZONES = ["version", "memoria", "calidad", "recorrido", "agentes", "pruebas", "permisos"]


def _rendered(stack: str = "react") -> str:
    files, _, warnings = _generate_onboarding_files(ENGINE, "demo", stack, ["supabase"], "dev")
    assert not [w for w in warnings if w.startswith("CLAUDE.md")], warnings
    return files["CLAUDE.md"]


def _zone(text: str, zid: str) -> str:
    return next(s.text for s in split_zones(text) if s.kind == "zone" and s.zone_id == zid)


def _outside(text: str) -> str:
    return "".join(s.text for s in split_zones(text) if s.kind == "text")


# ── AC-01 / AC-04 ─────────────────────────────────────────────────────


@pytest.mark.parametrize("stack", STACKS)
def test_ac01_the_generated_claude_md_has_200_lines_or_fewer(stack):
    assert len(_rendered(stack).splitlines()) <= 200


def test_ac04_the_non_negotiable_rules_are_in_their_zones():
    text = _rendered()
    assert zone_ids(text) == ZONES
    calidad = _zone(text, "calidad")
    for rule in ("Lee antes de escribir", "Piensa antes de actuar", "Verifica antes de cerrar",
                 "Pregunta antes de adivinar", "Una correcta > tres rapidas"):
        assert rule in calidad, rule
    memoria = _zone(text, "memoria")
    assert "Regla innegociable" in memoria and "mem_context" in memoria and "mem_search" in memoria
    assert "**para**" in memoria  # sin Engram, se para
    recorrido = _zone(text, "recorrido")
    steps = ["find_next_uc", "start_uc", "feature/UC-XXX", "mark_ac_batch", "move_uc", "complete_uc"]
    positions = [recorrido.index(s) for s in steps]
    assert positions == sorted(positions), "el recorrido va en orden"


def test_the_compliance_audit_still_reads_the_version():
    """specbox-audit.mjs lee la versión con «SpecBox Engine v([\\d.]+)»: nada de punto detrás."""
    from server.tools.onboarding import _read_engine_version

    match = re.search(r"SpecBox Engine v([\d.]+)", _rendered())
    assert match and match.group(1) == _read_engine_version(ENGINE)


def test_the_project_sections_stay_outside_the_zones():
    outside = _outside(_rendered())
    for section in PROJECT_SECTIONS:
        assert f"## {section}" in outside, section


# ── AC-02 ─────────────────────────────────────────────────────────────


# Lo que cada destino tiene que traer de la sección que se llevó.
DESTINATIONS = {
    "doc/guides/memoria-engram.md": ["engram_1.7.1_darwin_arm64", "engram_1.7.1_windows_amd64",
                                     "mem_session_start", "mem_timeline", "mem_stats", "mem_context"],
    "rules/GLOBAL_RULES.md": ["Antipatrones prohibidos", "Acceptance Testing"],
    "docs/agent-teams.md": ["Agent Teams"],
    ".claude/skills/implement/SKILL.md": ["# language: es", "bdd_widget_test", "playwright-bdd", "pytest-bdd"],
    ".claude/skills/visual-setup/SKILL.md": ["Pilar 1", "Pilar 2", "Pilar 3"],
    ".claude/skills/plan/SKILL.md": ["Paso 2.5b"],
    "architecture/flutter/e2e-testing.md": ["Playwright"],
    "architecture/react/e2e-testing.md": ["Playwright"],
    "doc/guides/permisos.md": ["settings.local.json"],
    "doc/guides/hooks.md": ["exit 2"],
    GUIDE: ["Tarjeta con la etiqueta «US»", "Elementos del checklist", "attach_evidence"],
}


def test_ac02_every_section_of_the_previous_template_has_a_place():
    old_sections = re.findall(r"^## (.+)$", OLD, re.MULTILINE)
    project_own = {"Qué es este repositorio", "Despliegue", "esto no es un encabezado: va dentro del bloque de código"}
    relocated = {r["section"] for r in RELOCATIONS}
    for section in old_sections:
        if section in project_own:
            continue
        assert section in relocated or section in PROJECT_SECTIONS, f"«{section}» no tiene destino"


@pytest.mark.parametrize("path", sorted(DESTINATIONS))
def test_ac02_each_destination_has_what_it_received(path):
    text = (ENGINE / path).read_text(encoding="utf-8")
    for needle in DESTINATIONS[path]:
        assert needle in text, f"{path} no trae «{needle}»"


def test_ac02_every_destination_named_in_the_table_exists_and_the_guide_lists_each_section():
    guide = (ENGINE / GUIDE).read_text(encoding="utf-8")
    for r in RELOCATIONS:
        assert f"| {r['section']} |" in guide, r["section"]
        assert f"«{r['zone']}»" in r["goes_to"]
        for path in re.findall(r"(?:doc|docs|rules|\.claude|architecture)/[\w./{}-]+\.md", r["goes_to"]):
            if "{stack}" in path:
                assert (ENGINE / path.replace("{stack}", "react")).is_file(), path
            else:
                assert (ENGINE / path).is_file(), path
            assert path in DESTINATIONS or "{stack}" in path, f"{path} sin comprobación de contenido"


# ── AC-03: con marcadores, solo cambian las zonas ─────────────────────


def _marked_project() -> str:
    """Un CLAUDE.md de la 6.38 que el proyecto ha tocado: secciones suyas y una zona vieja."""
    text = _rendered()
    text = text.replace("## Arquitectura\n", "## Arquitectura\n\nWeb en Astro y api en FastAPI, sin ORM.\n", 1)
    text = text.replace("- TODO: regla especifica del proyecto\n- TODO: regla especifica del proyecto\n",
                        "- Los precios van en céntimos.\n", 1)
    text += "\n## Despliegue\n\n```bash\n## dentro de un bloque\n./deploy.sh\n```\n"
    old_body = _zone(text, "agentes")
    return text.replace(old_body, '<!-- @specbox:claude-md start id="agentes" -->\n## Agentes\n\nTabla vieja.\n<!-- @specbox:claude-md end -->\n')


def test_ac03_merge_replaces_only_the_template_zones():
    current = _marked_project()
    # Una zona que la plantilla ya no tiene y otra que la plantilla añade.
    current = current.replace(_zone(current, "pruebas"), '<!-- @specbox:claude-md start id="obsoleta" -->\nvieja\n<!-- @specbox:claude-md end -->\n')
    template = _rendered()
    merged = merge_claude_md(current, template)
    assert _outside(merged.content) == _outside(current), "lo del proyecto queda byte a byte"
    assert "agentes" in merged.replaced and merged.added == ["pruebas"] and merged.removed == ["obsoleta"]
    for zid in ZONES:
        assert _zone(merged.content, zid) == _zone(template, zid)
    assert zone_ids(merged.content) == ZONES, "la zona nueva entra en su sitio"
    assert merge_claude_md(merged.content, template).content == merged.content  # idempotente


def test_malformed_markers_are_reported_and_nothing_is_written():
    broken = _rendered().replace("<!-- @specbox:claude-md end -->\n", "", 1)
    with pytest.raises(MalformedZones):
        split_zones(broken)
    content, report = claude_md_for_upgrade(broken, _rendered())
    assert content is None and report["status"] == "malformed"


# ── AC-05: un CLAUDE.md sin marcadores no se sobrescribe ──────────────


def test_ac05_an_unmarked_claude_md_gets_a_proposal_and_is_not_written():
    template = _rendered()
    content, report = claude_md_for_upgrade(OLD, template)
    assert content is None and report["status"] == "proposal"
    leaving = {s["section"]: s["goes_to"] for s in report["sections_leaving"]}
    assert set(leaving) == {r["section"] for r in RELOCATIONS}
    assert leaving["Trello — Fuente de Verdad (Spec-Driven)"].startswith("zona «recorrido»")
    assert report["sections_kept"] == ["Stack", "Arquitectura", "Qué es este repositorio", "Reglas del Proyecto",
                                       "Sistema de Diseño", "Servicios Externos", "Despliegue"]
    proposed = report["proposed_content"]
    assert proposed.startswith("# tienda-demo\n")
    assert zone_ids(proposed) == ZONES
    for section in ("## Qué es este repositorio\n\nLa tienda online de Demo SL", "## Despliegue",
                    "## esto no es un encabezado", "Los precios se guardan en céntimos."):
        assert section in proposed, section
    assert "Memoria Persistente (Engram) — REQUERIDO" not in proposed
    assert len(proposed.splitlines()) < len(OLD.splitlines())

    applied, report2 = claude_md_for_upgrade(OLD, template, confirm=True)
    assert report2["status"] == "applied" and applied == proposed
    # Una vez aplicada, la siguiente actualización ya solo toca las zonas.
    assert claude_md_for_upgrade(applied, template) == (None, {"status": "unchanged"})


def test_ac05_without_content_the_claude_md_is_left_alone_and_empty_means_create():
    template = _rendered()
    assert claude_md_for_upgrade(None, template)[0] is None
    assert claude_md_for_upgrade(None, template)[1]["status"] == "content_required"
    assert claude_md_for_upgrade("", template) == (template, {"status": "created", "zones": ZONES})


# ── upgrade_project de extremo a extremo ──────────────────────────────

ALICE = CallerScope("alice", "Alice", frozenset())


def _seed(state: Path) -> None:
    state.mkdir(parents=True, exist_ok=True)
    (state / "registry.json").write_text(json.dumps({"projects": {"tienda": {
        "stack": "react", "infra": ["supabase"], "registered_by": "alice",
        "registered_at": "2026-10-01T00:00:00+00:00", "engine_version": "6.37.0"}}}), encoding="utf-8")
    (state / "projects" / "tienda").mkdir(parents=True)
    (state / "projects" / "tienda" / "meta.json").write_text(json.dumps({"stack": "react", "engine_version": "6.37.0"}))


async def _upgrade(state: Path, **kwargs: Any) -> dict:
    from server.tools.onboarding import register_onboarding_tools

    mcp = FastMCP(name="t-claude-md")
    register_onboarding_tools(mcp, engine_path=ENGINE, state_path=state)
    tool = (await mcp.get_tool("upgrade_project")).fn
    with patch("server.tools.onboarding.resolve_caller_scope", new=AsyncMock(return_value=ALICE)):
        return await tool(project="tienda", ctx=None, **kwargs)


async def test_upgrade_project_keeps_the_project_sections(tmp_path):
    _seed(tmp_path)
    blind = await _upgrade(tmp_path)
    assert "CLAUDE.md" not in blind["files"] and blind["claude_md"]["status"] == "content_required"
    assert ".claude/settings.json" in blind["files"], "el resto de ficheros sigue igual"

    proposal = await _upgrade(tmp_path, claude_md_content=OLD)
    assert "CLAUDE.md" not in proposal["files"] and proposal["claude_md"]["status"] == "proposal"
    applied = await _upgrade(tmp_path, claude_md_content=OLD, confirm_claude_md=True)
    assert applied["files"]["CLAUDE.md"] == proposal["claude_md"]["proposed_content"]

    current = applied["files"]["CLAUDE.md"] + "\n## Notas del equipo\n\nNo tocar los viernes.\n"
    again = await _upgrade(tmp_path, claude_md_content=current)
    assert again["claude_md"]["status"] == "unchanged" and "CLAUDE.md" not in again["files"]
    stale = current.replace(_zone(current, "permisos"), '<!-- @specbox:claude-md start id="permisos" -->\nviejo\n<!-- @specbox:claude-md end -->\n')
    merged = await _upgrade(tmp_path, claude_md_content=stale)
    assert merged["claude_md"] == {"status": "merged", "replaced": ["permisos"], "added": [], "removed": []}
    assert merged["files"]["CLAUDE.md"] == current
