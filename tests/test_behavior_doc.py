"""UC-12605 (US-126) — una spec viva por funcionalidad, aparte de los PRD de cada cambio.

La parte del servidor; el hook que escribe el documento tiene sus pruebas en
tests/hooks/behavior-doc.test.mjs.

- AC-01: complete_uc(with_behavior_doc=True) devuelve la sección de la historia con sus UC cerradas y
  sus criterios, y las historias con todas sus UC cerradas.
- AC-02: la marca de PRD superado (fecha y documento) va debajo de la de formato.
- AC-03: run_acceptance_check y get_e2e_gap_report dejan fuera los PRD superados y leen el documento.
- AC-05: sin ningún PRD superado, el contenido y el resultado son los de antes.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from server.behavior_doc import (
    current_prd_content,
    is_superseded,
    mark_superseded,
    prd_stories,
    render_section,
    replace_story_section,
    split_documents,
)
from server.prd_writer import find_prd_path
from server.tools.acceptance import _find_prd_files, get_e2e_gap_report_from_content, run_acceptance_check_from_content
from server.tools.spec_driven import complete_uc
from tests.test_spec_gate_start_uc import CTX

ROOT = Path(__file__).resolve().parent.parent

ITEMS = [
    {"id": "us1", "name": "US-01: Cobrar", "labels": ["US"], "state": "in_progress", "meta": {"us_id": "US-01"}},
    {"id": "uc1", "name": "UC-001: Cobrar con tarjeta", "labels": ["UC"], "state": "done", "parent_id": "us1",
     "meta": {"uc_id": "UC-001"}},
    {"id": "ac1", "name": "[AC-01] El cobro queda registrado", "labels": ["AC"], "state": "done", "parent_id": "uc1",
     "meta": {"ac_id": "AC-01"}},
    {"id": "uc2", "name": "UC-002: Devolver", "labels": ["UC"], "state": "review", "parent_id": "us1",
     "meta": {"uc_id": "UC-002"}},
    {"id": "ac2", "name": "[AC-01] La devolución queda registrada", "labels": ["AC"], "state": "done",
     "parent_id": "uc2", "meta": {"ac_id": "AC-01"}},
]

PRD_A = "# PRD: Cobros\n\n<!-- @specbox:prd format=\"2\" -->\n\n## US-01 — Cobrar\n\n### UC-001: Cobrar\n- [ ] **AC-01**: El cobro queda registrado\n- [ ] **AC-02**: Viejo criterio\n"
PRD_B = "# PRD: Avisos\n\n## US-02 — Avisar\n\n### UC-010: Avisar\n- [ ] **AC-01**: El aviso sale\n"
SPEC = ("# Comportamiento: cobros\n\n<!-- @specbox:spec us=\"US-01\" start -->\n## US-01 — Cobrar\n\n"
        "### UC-001: Cobrar\n\n- [x] **AC-01**: El cobro queda registrado\n\n<!-- @specbox:spec us=\"US-01\" end -->\n")


async def test_complete_uc_returns_the_section_of_the_story_and_the_complete_stories():
    out = await complete_uc("ff", "UC-002", CTX, items_content=json.dumps(ITEMS), with_behavior_doc=True)
    doc = out["behavior_doc"]
    assert doc["ok"] and doc["us_id"] == "US-01" and doc["complete_stories"] == ["US-01"]
    assert "### UC-001: Cobrar con tarjeta\n\n- [x] **AC-01**: El cobro queda registrado" in doc["section"]
    assert "### UC-002: Devolver\n\n- [x] **AC-01**: La devolución queda registrada" in doc["section"]
    plain = await complete_uc("ff", "UC-002", CTX, items_content=json.dumps(ITEMS))
    assert "behavior_doc" not in plain  # sin pedirlo, la respuesta es la de antes


def test_the_section_is_the_same_as_the_hooks(tmp_path):
    """El hook calcula lo mismo con items.json (FreeForm por fragmentos)."""
    if not shutil.which("node"):
        pytest.skip("sin node")
    import asyncio

    from server.backends.freeform_backend import FreeformBackend
    from server.behavior_doc import behavior_doc_from_backend

    py = asyncio.run(behavior_doc_from_backend(FreeformBackend(items_content=json.dumps(ITEMS)), "ff", "UC-001"))
    script = (
        "import { sectionFromItems, completeStoriesFromItems } from './.claude/hooks/lib/behavior-doc.mjs';"
        f"const items = {json.dumps(ITEMS)};"
        "console.log(JSON.stringify({section: sectionFromItems(items, 'UC-001').section, complete: completeStoriesFromItems(items)}));"
    )
    js = json.loads(subprocess.run(["node", "--input-type=module", "-e", script], cwd=ROOT, capture_output=True,
                                   text=True, check=True).stdout)
    assert js["section"] == py["section"] and js["complete"] == []  # UC-002 sigue en revisión
    assert py["complete_stories"] == []


def test_the_superseded_mark_goes_under_the_format_mark_once():
    marked = mark_superseded(PRD_A, "2026-11-19", "doc/spec/cobros.md")
    assert '<!-- @specbox:prd format="2" -->\n<!-- @specbox:prd status="superseded" date="2026-11-19" by="doc/spec/cobros.md" -->' in marked
    assert is_superseded(marked) and mark_superseded(marked, "x", "y") == marked
    assert mark_superseded("sin título", "d", "b").startswith("<!-- @specbox:prd status")
    assert prd_stories(PRD_A) == ["US-01"]


def _norm(result: dict) -> str:
    import re

    return re.sub(r"\d{4}-\d\d-\d\dT[\d:.]+(?:\+00:00|Z)?", "T", json.dumps(result, sort_keys=True))


def test_without_superseded_prds_the_content_is_byte_for_byte_the_same():
    content = PRD_A + "\n" + PRD_B
    assert current_prd_content(content) == (content, 0)
    base = run_acceptance_check_from_content(prd_content=content, item_id="UC-001")
    again = run_acceptance_check_from_content(prd_content=current_prd_content(content)[0], item_id="UC-001")
    assert _norm(base) == _norm(again) and "superseded_prds" not in base
    # Los PRD reales del orquestador (ninguno superado) pasan intactos.
    orchestrator = ROOT.parent.parent / "doc" / "prd"
    if orchestrator.is_dir():
        real = "\n".join(f.read_text(encoding="utf-8") for f in sorted(orchestrator.rglob("*.md")))
        assert current_prd_content(real) == (real, 0)


def test_superseded_prds_are_left_out_and_the_behavior_doc_is_read():
    old = mark_superseded(PRD_A, "2026-11-19", "doc/spec/cobros.md")
    marked = "\n".join(
        f'<!-- @specbox:file path="{p}" -->\n{t}' for p, t in
        (("doc/prd/cobros/prd.md", old), ("doc/prd/avisos/prd.md", PRD_B), ("doc/spec/cobros.md", SPEC))
    )
    kept, dropped = current_prd_content(marked)
    assert dropped == 1 and "Viejo criterio" not in kept and "El aviso sale" in kept
    out = run_acceptance_check_from_content(prd_content=marked, item_id="UC-001")
    [uc] = out["uc_results"]
    assert [c["ac_id"] for c in uc["criteria"]] == ["AC-01"] and out["superseded_prds"] == 1
    gap = get_e2e_gap_report_from_content(prd_content=marked, project_name="p", stack="python")
    assert gap["superseded_prds"] == 1
    # Sin marcas de fichero, los documentos se parten por su título.
    assert len(split_documents(old + "\n" + PRD_B)) == 2


def test_the_section_replaces_its_own_block_and_renders_closed_ucs():
    story = {"us_id": "US-01", "title": "Cobrar"}
    section = render_section(story, [{"uc_id": "UC-001", "title": "Cobrar", "criteria": [
        {"ac_id": "AC-02", "text": "Dos", "done": False}, {"ac_id": "AC-01", "text": "Uno", "done": True}]}])
    assert section.index("AC-01") < section.index("AC-02") and "- [ ] **AC-02**: Dos" in section
    doc = replace_story_section("", "US-01", section, "cobros")
    assert doc.startswith("# Comportamiento: cobros") and replace_story_section(doc, "US-01", section, "cobros") == doc


def test_the_prd_of_a_new_story_skips_superseded_prds(tmp_path):
    (tmp_path / "doc/prd/cobros").mkdir(parents=True)
    (tmp_path / "doc/prd/cobros/prd.md").write_text(mark_superseded(PRD_A, "2026-11-19", "doc/spec/cobros.md"))
    assert find_prd_path(tmp_path, us_id="US-01") is None
    assert find_prd_path(tmp_path, us_id="US-01", include_superseded=True) == tmp_path / "doc/prd/cobros/prd.md"
    # La ruta local de run_acceptance_check: sin el superado y con el documento de comportamiento.
    (tmp_path / "doc/prd/avisos.md").write_text(PRD_B)
    (tmp_path / "doc/spec").mkdir()
    (tmp_path / "doc/spec/cobros.md").write_text(SPEC)
    assert [p.relative_to(tmp_path).as_posix() for p in _find_prd_files(tmp_path)] == ["doc/prd/avisos.md", "doc/spec/cobros.md"]
