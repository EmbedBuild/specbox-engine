"""UC-12605 (US-126) — una spec viva por funcionalidad, aparte de los PRD de cada cambio.

La parte del servidor; el hook que escribe el documento tiene sus pruebas en
tests/hooks/behavior-doc.test.mjs.

- AC-01: complete_uc(with_behavior_doc=True) devuelve la sección de la historia con sus UC cerradas y
  sus criterios, la de cada historia pedida y las historias sin nada pendiente; move_uc y add_uc
  también, para que el hook quite la marca a un PRD que vuelve a tener trabajo.
- AC-02: la marca de PRD superado (fecha y documento) va debajo de la de formato y solo cuenta como
  línea propia de la cabecera.
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
    behavior_doc_from_freeform,
    complete_stories,
    current_prd_content,
    is_superseded,
    mark_superseded,
    prd_stories,
    render_section,
    replace_story_section,
    split_documents,
    unmark_superseded,
    wanted_stories,
)
from server.prd_writer import find_prd_path
from server.tools.acceptance import _find_prd_files, get_e2e_gap_report_from_content, run_acceptance_check_from_content
from server.tools.spec_driven import complete_uc, move_uc
from server.tools.spec_mutations import add_uc
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

#: Un tablero con los casos raros: historia archivada, todas sus UC archivadas, sin UC, criterio
#: archivado, id del criterio solo en meta y un criterio con «-->» dentro.
RICH = [
    *ITEMS,
    {"id": "us2", "name": "[US-02] Avisar", "labels": ["US"], "state": "archived", "meta": {}},
    {"id": "us3", "name": "US-03: Exportar", "labels": ["US"], "state": "in_progress", "meta": {"us_id": "US-03"}},
    {"id": "uc3", "name": "UC-003: Exportar CSV", "labels": ["UC"], "state": "archived", "parent_id": "us3",
     "meta": {"uc_id": "UC-003"}},
    {"id": "us4", "name": "US-04: Importar", "labels": ["US"], "state": "backlog", "meta": {"us_id": "US-04"}},
    {"id": "us5", "name": "US-05: Firmar <!-- x -->", "labels": ["US"], "state": "done", "meta": {"us_id": "US-05"}},
    {"id": "uc5", "name": "UC-005: Firmar", "labels": ["UC"], "state": "done", "parent_id": "us5", "meta": {"uc_id": "UC-005"}},
    {"id": "ac5", "name": "La firma queda guardada --> y cierra <!-- @specbox:spec us=\"US-05\" end -->",
     "labels": ["AC"], "state": "done", "parent_id": "uc5", "meta": {"ac_id": "AC-02"}},
    {"id": "ac6", "name": "[AC-03] Criterio retirado", "labels": ["AC"], "state": "archived", "parent_id": "uc5",
     "meta": {"ac_id": "AC-03"}},
]

PRD_A = "# PRD: Cobros\n\n<!-- @specbox:prd format=\"2\" -->\n\n## US-01 — Cobrar\n\n### UC-001: Cobrar\n- [ ] **AC-01**: El cobro queda registrado\n- [ ] **AC-02**: Viejo criterio\n"
PRD_B = "# PRD: Avisos\n\n## US-02 — Avisar\n\n### UC-010: Avisar\n- [ ] **AC-01**: El aviso sale\n"
SPEC = ("# Comportamiento: cobros\n\n<!-- @specbox:spec us=\"US-01\" start -->\n## US-01 — Cobrar\n\n"
        "### UC-001: Cobrar\n\n- [x] **AC-01**: El cobro queda registrado\n\n<!-- @specbox:spec us=\"US-01\" end -->\n")
MARK = '<!-- @specbox:prd status="superseded" date="2026-11-19" by="doc/spec/cobros.md" -->'


async def test_complete_uc_returns_the_sections_and_the_complete_stories():
    out = await complete_uc("ff", "UC-002", CTX, items_content=json.dumps(ITEMS), with_behavior_doc=True,
                            behavior_doc_us_ids=["US-09", "no-es-un-id"])
    doc = out["behavior_doc"]
    assert doc["ok"] and doc["us_id"] == "US-01" and doc["complete_stories"] == ["US-01"]
    assert "### UC-001: Cobrar con tarjeta\n\n- [x] **AC-01**: El cobro queda registrado" in doc["section"]
    assert "### UC-002: Devolver\n\n- [x] **AC-01**: La devolución queda registrada" in doc["section"]
    assert list(doc["sections"]) == ["US-01"] and doc["ignored_us_ids"] == 1  # US-09 no está; el otro no es un id
    plain = await complete_uc("ff", "UC-002", CTX, items_content=json.dumps(ITEMS))
    assert "behavior_doc" not in plain  # sin pedirlo, la respuesta es la de antes


async def test_move_uc_and_add_uc_report_a_story_that_has_work_again():
    done = [dict(i, state="done") if i["id"] == "uc2" else i for i in ITEMS]
    moved = await move_uc("ff", "UC-002", "in_progress", CTX, items_content=json.dumps(done), with_behavior_doc=True)
    assert moved["behavior_doc"]["ok"] and moved["behavior_doc"]["complete_stories"] == []
    assert "UC-002" not in moved["behavior_doc"]["section"]  # ya no está cerrada
    added = await add_uc("ff", "US-01", "Anular", "Anular un cobro",
                         ["El cobro anulado queda registrado con su motivo"], CTX,
                         items_content=json.dumps(done), with_behavior_doc=True)
    assert added["behavior_doc"]["us_id"] == "US-01" and added["behavior_doc"]["complete_stories"] == []
    assert "behavior_doc" not in await move_uc("ff", "UC-002", "review", CTX, items_content=json.dumps(done))


def test_archived_stories_and_stories_with_every_uc_archived_count_as_complete():
    # US-02 archivada; US-03 con su única UC archivada; US-04 sin UC (no se ha hecho nada); US-05 cerrada.
    assert complete_stories(RICH) == ["US-02", "US-03", "US-05"]
    assert wanted_stories("US-01", ["us-03", "US-01", "x"] + [f"US-{n}" for n in range(10, 40)])[0][:3] == [
        "US-01", "US-03", "US-10"]
    assert len(wanted_stories("US-01", [f"US-{n}" for n in range(10, 40)])[0]) == 21


def test_the_sections_are_the_same_as_the_hooks():
    """El hook calcula lo mismo con items.json, y el servidor usa sus reglas con el items.json entero."""
    if not shutil.which("node"):
        pytest.skip("sin node")
    import asyncio

    stories = ["US-01", "US-02", "US-03", "US-04", "US-05"]
    py = asyncio.run(behavior_doc_from_freeform(json.dumps(RICH), "UC-001", us_ids=stories))
    script = (
        "import { sectionForStory, completeStoriesFromItems, storyIdFromItems } from './.claude/hooks/lib/behavior-doc.mjs';"
        f"const items = {json.dumps(RICH)};"
        f"const stories = {json.dumps(stories)};"
        "const sections = Object.fromEntries(stories.map((u) => [u, sectionForStory(items, u)?.section]).filter(([, s]) => s));"
        "console.log(JSON.stringify({sections, complete: completeStoriesFromItems(items),"
        " story: storyIdFromItems(items, { ucId: 'UC-001' })}));"
    )
    js = json.loads(subprocess.run(["node", "--input-type=module", "-e", script], cwd=ROOT, capture_output=True,
                                   text=True, check=True).stdout)
    assert js["sections"] == py["sections"] and js["complete"] == py["complete_stories"] and js["story"] == py["us_id"]
    firmar = py["sections"]["US-05"]
    # El criterio con «-->» no cierra la sección; el archivado no sale; el id del criterio sale de meta.
    assert firmar.count('<!-- @specbox:spec us="US-05" end -->') == 1 and "--&gt;" in firmar and "&lt;!--" in firmar
    assert "AC-03" not in firmar and "**AC-02**: La firma queda guardada" in firmar


def test_the_superseded_mark_goes_under_the_format_mark_once():
    marked = mark_superseded(PRD_A, "2026-11-19", "doc/spec/cobros.md")
    assert f'<!-- @specbox:prd format="2" -->\n{MARK}' in marked
    assert is_superseded(marked) and mark_superseded(marked, "x", "y") == marked
    assert mark_superseded("sin título", "d", "b").startswith("<!-- @specbox:prd status")
    assert prd_stories(PRD_A) == ["US-01"]
    # Se quita solo la que puso el engine con ese documento.
    assert unmark_superseded(marked, "doc/spec/cobros.md") == PRD_A
    assert unmark_superseded(marked, "doc/spec/otro.md") == marked
    # Un valor con comillas o ángulos no rompe la marca.
    assert is_superseded(mark_superseded(PRD_A, '2026"><x', "doc/spec/a\"b.md"))


def test_the_mark_only_counts_as_its_own_line_in_the_header():
    quoted_in_body = PRD_A + f"\nEjemplo de la marca:\n\n{MARK}\n"
    in_code = PRD_A.replace("\n\n## US-01", f"\n\n```\n{MARK}\n```\n\n## US-01")
    inline = PRD_A.replace("\n\n## US-01", f"\n\nLa marca es {MARK} y va arriba.\n\n## US-01")
    for text in (quoted_in_body, in_code, inline):
        assert not is_superseded(text)
        assert current_prd_content(text) == (text, 0)
    # Un PRD que explica la marca en su cuerpo no queda superado al marcar otro.
    assert is_superseded(mark_superseded(quoted_in_body, "2026-11-19", "doc/spec/cobros.md"))


def test_prd_stories_include_quote_lines_and_skip_code():
    prd = "# PRD: Cobros\n\n> Historias: US-01 y US-07\n\n```\n# US-99 no cuenta\n```\n\n## US-03 — Algo\nTexto que cita US-44.\n"
    assert prd_stories(prd) == ["US-01", "US-07", "US-03"]


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


def test_without_file_marks_documents_split_at_titles_outside_code():
    old = mark_superseded(PRD_A, "2026-11-19", "doc/spec/cobros.md")
    assert len(split_documents(old + "\n" + PRD_B)) == 2
    # Un «# comentario» dentro de un bloque de código no parte el documento.
    with_code = PRD_B.replace("### UC-010", "```bash\n# instala\nnpm i\n```\n\n### UC-010")
    assert split_documents(with_code) == [with_code]
    # Las marcas justo encima del título van con el documento que empieza.
    above = f'<!-- @specbox:prd format="2" -->\n{MARK}\n# PRD: Cobros\n\n## US-01\n- [ ] **AC-01**: x\n'
    docs = split_documents(PRD_B + "\n" + above)
    assert len(docs) == 2 and docs[1].startswith('<!-- @specbox:prd format="2" -->') and is_superseded(docs[1])
    assert not is_superseded(docs[0])
    kept, dropped = current_prd_content(PRD_B + "\n" + above)
    assert dropped == 1 and kept == PRD_B


def test_the_section_replaces_its_own_block_and_renders_closed_ucs():
    story = {"us_id": "US-01", "title": "Cobrar"}
    section = render_section(story, [{"uc_id": "UC-001", "title": "Cobrar", "criteria": [
        {"ac_id": "AC-02", "text": "Dos", "done": False}, {"ac_id": "AC-01", "text": "Uno", "done": True}]}])
    assert section.index("AC-01") < section.index("AC-02") and "- [ ] **AC-02**: Dos" in section
    doc = replace_story_section("", "US-01", section, "cobros")
    assert doc.startswith("# Comportamiento: cobros") and replace_story_section(doc, "US-01", section, "cobros") == doc


def test_a_superseded_prd_is_still_the_prd_of_its_story(tmp_path):
    (tmp_path / "doc/prd/cobros").mkdir(parents=True)
    (tmp_path / "doc/prd/cobros/prd.md").write_text(mark_superseded(PRD_A, "2026-11-19", "doc/spec/cobros.md"))
    assert find_prd_path(tmp_path, us_id="US-01") == tmp_path / "doc/prd/cobros/prd.md"
    # La ruta local de run_acceptance_check: sin el superado y con el documento de comportamiento.
    (tmp_path / "doc/prd/avisos.md").write_text(PRD_B)
    (tmp_path / "doc/spec").mkdir()
    (tmp_path / "doc/spec/cobros.md").write_text(SPEC)
    assert [p.relative_to(tmp_path).as_posix() for p in _find_prd_files(tmp_path)] == ["doc/prd/avisos.md", "doc/spec/cobros.md"]


# ── Revisión 2 ──────────────────────────────────────────────────────


def test_a_quote_in_the_body_is_not_a_story_of_the_prd():
    prd = "# PRD: Cobros\n\n> Historia: US-01\n\n## US-01 — Cobrar\n\n> densa (US-13) tiene 63 AC en 10 UC\n"
    assert prd_stories(prd) == ["US-01"]


def test_without_file_marks_a_superseded_prd_that_may_hide_another_is_kept():
    """Una valla sin cerrar se come los PRD de detrás: en la duda se lee de más, nunca de menos."""
    hiding = mark_superseded(PRD_A, "2026-11-19", "doc/spec/cobros.md") + "\n```\n"
    content = hiding + "\n" + PRD_B
    assert current_prd_content(content) == (content, 0)
    # Con marcas de fichero, el reparto es exacto y el superado se deja fuera.
    marked = f'<!-- @specbox:file path="a.md" -->\n{hiding}\n<!-- @specbox:file path="b.md" -->\n{PRD_B}'
    kept, dropped = current_prd_content(marked)
    assert dropped == 1 and "El aviso sale" in kept and "Viejo criterio" not in kept


def test_a_reopened_story_takes_its_new_uc_from_the_superseded_prd():
    """La historia vuelve a tener trabajo antes de que el hook quite la marca: UC-002 no se pierde."""
    reopened = mark_superseded(PRD_A, "2026-11-19", "doc/spec/cobros.md") + (
        "\n### UC-002: Devolver\n- [ ] **AC-01**: La devolución queda registrada\n")
    content = "\n".join(
        f'<!-- @specbox:file path="{p}" -->\n{t}' for p, t in
        (("doc/prd/cobros/prd.md", reopened), ("doc/spec/cobros.md", SPEC))
    )
    out = run_acceptance_check_from_content(prd_content=content, item_id="UC-002")
    [uc] = out["uc_results"]
    assert [c["ac_id"] for c in uc["criteria"]] == ["AC-01"] and uc["from_superseded_prd"] is True
    assert out["from_superseded_prd"] == ["UC-002"]
    story = run_acceptance_check_from_content(prd_content=content, item_id="US-01")
    by_uc = {r["uc_id"]: r for r in story["uc_results"]}
    assert set(by_uc) == {"UC-001", "UC-002"} and "from_superseded_prd" not in by_uc["UC-001"]
    assert [c["ac_id"] for c in by_uc["UC-001"]["criteria"]] == ["AC-01"]  # del documento, sin el viejo AC-02
    # Sin UC pedida se leen solo los vigentes, como antes.
    every = run_acceptance_check_from_content(prd_content=content, item_id="")
    assert [r["uc_id"] for r in every["uc_results"]] == ["UC-001"] and "from_superseded_prd" not in every
