"""US-56 / UC-5601 — el engine guarda la evidencia de cada AC con estructura.

- **AC-01**: `mark_ac` y `mark_ac_batch` aceptan una evidencia estructurada
  ({type, label, link?, detail?}) y el board native la guarda junto al AC con
  el developer de la sesión y la fecha.
- **AC-02**: la evidencia en texto libre se sigue aceptando: se guarda con el
  texto completo como etiqueta, tipo `url` y sin enlace; el comentario de la UC
  no cambia y ninguna llamada existente falla.
- **AC-03**: `get_uc` devuelve por cada AC sus evidencias (tipo, etiqueta,
  enlace, quién, cuándo) y quién lo aceptó y cuándo.
- **AC-04**: la migración 0028 convierte los comentarios «AC-XX: PASSED — …» en
  evidencias con su fecha y autor desconocido (nunca inventado).

Las pruebas native son Postgres-gated: SKIP limpio sin DB de desarrollo
(``docker compose -f docker-compose.dev.yml up -d``).
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from server.ac_evidence import (
    EvidenceError,
    accepted_from,
    evidence_comment_text,
    evidence_from_comments,
    normalize_evidence,
    verdicts_from_comments,
)
from server.spec_backend import CommentDTO
from tests._native_db import DSN, reachable

PG_OK, PG_SKIP_REASON = reachable()
pytestmark_pg = pytest.mark.skipif(not PG_OK, reason=PG_SKIP_REASON)

MIGRATION = Path(__file__).resolve().parent.parent / "server/db/migrations/0028_ac_evidence_backfill.sql"


# ═══════════════════════════════════════════════════════════════════════
# Unidad — la forma única de una evidencia
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("raw", [None, "", "   "])
def test_no_evidence_is_none(raw):
    assert normalize_evidence(raw) is None


def test_ac02_free_text_is_url_with_full_text_and_no_link():
    text = "pytest tests/test_x.py — 12 passed\nsegunda línea"
    assert normalize_evidence(text) == {"type": "url", "label": text, "link": None, "detail": None}


def test_ac01_structured_evidence_is_normalized():
    ev = normalize_evidence(
        {"type": "pr", "label": " engine#189 ", "link": "https://github.com/EmbedBuild/specbox-engine/pull/189"}
    )
    assert ev == {
        "type": "pr",
        "label": "engine#189",
        "link": "https://github.com/EmbedBuild/specbox-engine/pull/189",
        "detail": None,
    }


@pytest.mark.parametrize(
    ("raw", "fragment"),
    [
        ({"type": "video", "label": "x"}, "evidence.type"),
        ({"label": "x"}, "evidence.type"),
        ({"type": "test"}, "evidence.label"),
        ({"type": "test", "label": "  "}, "evidence.label"),
        ({"type": "url", "label": "x", "link": "ftp://host/file"}, "evidence.link"),
        ({"type": "url", "label": "x", "link": "github.com/a/b"}, "evidence.link"),
        ({"type": "test", "label": "x", "detail": 3}, "evidence.detail"),
        ({"type": "test", "label": "x", "url": "https://a.b"}, "campos desconocidos"),
        (42, "texto o un objeto"),
    ],
)
def test_ac01_invalid_structured_evidence_says_why(raw, fragment):
    with pytest.raises(EvidenceError, match=fragment):
        normalize_evidence(raw)


def test_ac02_free_text_comment_is_unchanged():
    assert evidence_comment_text(normalize_evidence("12 passed")) == "12 passed"


def test_structured_comment_names_type_link_and_detail():
    ev = normalize_evidence({"type": "test", "label": "test_x", "link": "https://ci/1", "detail": "8/8"})
    assert evidence_comment_text(ev) == "[test] test_x <https://ci/1> — 8/8"


# ═══════════════════════════════════════════════════════════════════════
# Unidad — lectura de los comentarios de siempre
# ═══════════════════════════════════════════════════════════════════════

_COMMENTS = [
    CommentDTO(id="1", text="AC-01: PASSED — 12 passed [2026-09-01 10:00 UTC]", created_at="2026-09-01T10:00:05+00:00"),
    CommentDTO(id="2", text="AC-02: FAILED [2026-09-01 10:01 UTC]", created_at=""),
    CommentDTO(
        id="3",
        text="Validacion AG-09b [2026-09-02 09:30 UTC]:\n  AC-02: PASSED\n  AC-03: PASSED — captura ok",
        created_at="2026-09-02T09:30:00+00:00",
    ),
    CommentDTO(id="4", text="Todos los criterios de aceptacion validados", created_at="2026-09-02T09:30:01+00:00"),
]


def test_evidence_from_comments_keeps_text_date_and_unknown_author():
    ev = evidence_from_comments(_COMMENTS)
    assert ev["AC-01"] == [
        {
            "type": "url",
            "label": "12 passed",
            "link": None,
            "detail": None,
            "by": None,
            "at": "2026-09-01T10:00:05+00:00",
            "passed": True,
        }
    ]
    assert "AC-02" not in ev  # sin texto de evidencia no hay recibo que enseñar
    assert ev["AC-03"][0]["label"] == "captura ok"


def test_verdicts_from_comments_take_the_last_one_and_bracket_dates():
    v = verdicts_from_comments(_COMMENTS)
    assert v["AC-01"] == {"passed": True, "by": None, "at": "2026-09-01T10:00:05+00:00"}
    assert v["AC-02"] == {"passed": True, "by": None, "at": "2026-09-02T09:30:00+00:00"}
    assert verdicts_from_comments([_COMMENTS[1]])["AC-02"]["at"] == "2026-09-01T10:01:00+00:00"


def test_accepted_only_when_done_and_the_verdict_accepted_it():
    verdict = {"passed": True, "by": "ana", "at": "2026-09-01T10:00:00+00:00"}
    assert accepted_from(True, verdict) == {"by": "ana", "at": "2026-09-01T10:00:00+00:00"}
    assert accepted_from(False, verdict) is None
    assert accepted_from(True, {"passed": False, "by": "ana", "at": "x"}) is None
    assert accepted_from(True, None) is None


# ═══════════════════════════════════════════════════════════════════════
# Tools — FreeForm en disco (sin almacén por AC: se lee de los comentarios)
# ═══════════════════════════════════════════════════════════════════════


class _FreeformCtx:
    def __init__(self, root: Path):
        self._s = {"spec_backend_config": {"backend_type": "freeform", "root_path": str(root)}}

    async def get_state(self, key):
        return self._s.get(key)

    async def set_state(self, key, value):
        self._s[key] = value


async def _freeform_board(tmp_path: Path, monkeypatch):
    from server.tools.spec_mutations import add_uc

    monkeypatch.delenv("SPECBOX_ENGINE_MCP_URL", raising=False)
    (tmp_path / "items.json").write_text(
        json.dumps(
            [
                {
                    "id": "item-us1",
                    "name": "US-01: Demo",
                    "description": "",
                    "state": "backlog",
                    "parent_id": None,
                    "labels": ["US"],
                    "priority": "none",
                    "meta": {"us_id": "US-01", "tipo": "US"},
                }
            ]
        )
    )
    ctx = _FreeformCtx(tmp_path)
    res = await add_uc(
        board_id="ff",
        us_id="US-01",
        name="UC con recibos",
        description="d",
        acceptance_criteria=["El primero debe pasar", "El segundo debe pasar", "El tercero debe pasar"],
        ctx=ctx,
    )
    assert "error" not in res, res
    return ctx


@pytest.mark.asyncio
async def test_ac01_ac02_ac03_tools_on_freeform(tmp_path, monkeypatch):
    from server.tools.spec_driven import get_uc, mark_ac, mark_ac_batch

    ctx = await _freeform_board(tmp_path, monkeypatch)

    r1 = await mark_ac(board_id="ff", uc_id="UC-001", ac_id="AC-01", passed=True, ctx=ctx, evidence="12 passed")
    assert r1["passed"] and r1["ac_done"] == 1
    r2 = await mark_ac(
        board_id="ff",
        uc_id="UC-001",
        ac_id="AC-02",
        passed=True,
        ctx=ctx,
        evidence={"type": "pr", "label": "engine#189", "link": "https://github.com/x/y/pull/189"},
    )
    assert r2["ac_done"] == 2
    r3 = await mark_ac_batch(
        board_id="ff",
        uc_id="UC-001",
        results=[{"ac_id": "AC-03", "passed": True, "evidence": {"type": "test", "label": "8 passed"}}],
        ctx=ctx,
    )
    assert r3["passed"] == 1 and r3["details"] == [{"ac_id": "AC-03", "passed": True}]

    uc = await get_uc(board_id="ff", uc_id="UC-001", ctx=ctx)
    acs = {a["id"]: a for a in uc["acceptance_criteria"]}
    assert acs["AC-01"]["evidence"][0]["label"] == "12 passed"
    assert acs["AC-01"]["evidence"][0]["type"] == "url"
    assert acs["AC-02"]["evidence"][0]["label"] == "[pr] engine#189 <https://github.com/x/y/pull/189>"
    assert acs["AC-03"]["evidence"][0]["label"] == "[test] 8 passed"
    for ac in acs.values():
        assert ac["done"] is True
        assert ac["accepted"]["by"] is None  # FreeForm no conoce al developer: nunca se inventa
        assert ac["accepted"]["at"]
        assert all(e["by"] is None and e["at"] for e in ac["evidence"])


@pytest.mark.asyncio
async def test_ac02_free_text_comment_is_byte_identical(tmp_path, monkeypatch):
    from server.backends.freeform_backend import FreeformBackend
    from server.tools.spec_driven import mark_ac

    ctx = await _freeform_board(tmp_path, monkeypatch)
    await mark_ac(board_id="ff", uc_id="UC-001", ac_id="AC-01", passed=True, ctx=ctx, evidence="12 passed")

    backend = FreeformBackend(str(tmp_path))
    uc_item = await backend.find_item_by_field("ff", "uc_id", "UC-001")
    texts = [c.text for c in await backend.get_comments("ff", uc_item.id)]
    assert any(t.startswith("AC-01: PASSED — 12 passed [") and t.endswith(" UTC]") for t in texts), texts


@pytest.mark.asyncio
async def test_ac01_invalid_evidence_marks_nothing(tmp_path, monkeypatch):
    from server.tools.spec_driven import get_ac_status, mark_ac, mark_ac_batch

    ctx = await _freeform_board(tmp_path, monkeypatch)

    bad = await mark_ac(
        board_id="ff", uc_id="UC-001", ac_id="AC-01", passed=True, ctx=ctx, evidence={"type": "video", "label": "x"}
    )
    assert bad["code"] == "INVALID_EVIDENCE"
    bad_batch = await mark_ac_batch(
        board_id="ff",
        uc_id="UC-001",
        results=[
            {"ac_id": "AC-01", "passed": True, "evidence": "ok"},
            {"ac_id": "AC-02", "passed": True, "evidence": {"type": "test"}},
        ],
        ctx=ctx,
    )
    assert bad_batch["code"] == "INVALID_EVIDENCE"
    status = await get_ac_status(board_id="ff", uc_id="UC-001", ctx=ctx)
    assert status["done"] == 0  # ni el AC-01 válido del lote: o todo o nada


# ═══════════════════════════════════════════════════════════════════════
# Native — almacén por AC y migración (Postgres-gated)
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _reset_shared_pool():
    """Pool global a None antes y después de cada test (ver test_ac_internal)."""
    import server.db.pool as poolmod

    poolmod._pool = None
    yield
    poolmod._pool = None


async def _pool():
    import server.db.pool as poolmod
    from server.db.migrate import apply_migrations
    from server.db.pool import init_pool

    poolmod._pool = None
    pool = await init_pool(dsn=DSN)
    await apply_migrations(pool)
    return pool


async def _seed(pool, *, comments: list[dict] | None = None, n_acs: int = 3, done: tuple[str, ...] = ()):
    from server.coordination.identity import add_project_member, register_developer, register_mcp_token

    project_id = f"Acme/ac-evidence-{uuid.uuid4().hex[:8]}"
    developer_id = f"ev-dev-{uuid.uuid4().hex[:8]}"
    token = f"ev-tok-{uuid.uuid4().hex[:16]}"
    async with pool.acquire() as conn:
        await register_developer(conn, developer_id=developer_id, display_name="Evidence Tester")
        await register_mcp_token(conn, developer_id=developer_id, token=token)
        await conn.execute("INSERT INTO projects (project_id, name) VALUES ($1, $2)", project_id, "Evidence")
        await add_project_member(conn, project_id=project_id, developer_id=developer_id, role="project_admin")
        await conn.execute(
            "INSERT INTO user_stories (id, project_id, name, state) VALUES ('US-01', $1, 'US', 'backlog')",
            project_id,
        )
        await conn.execute(
            "INSERT INTO use_cases (id, project_id, us_id, name, state, labels, meta) "
            "VALUES ('UC-001', $1, 'US-01', 'UC-001: UC', 'backlog', '[\"UC\"]'::jsonb, $2::jsonb)",
            project_id,
            json.dumps({"uc_id": "UC-001", "comments": comments or []}, ensure_ascii=False),
        )
        for n in range(1, n_acs + 1):
            ac_id = f"AC-{n:02d}"
            await conn.execute(
                "INSERT INTO acceptance_criteria (id, project_id, uc_id, ac_id, text, done) "
                "VALUES ($1, $2, 'UC-001', $3, $4, $5)",
                f"UC-001::{ac_id}",
                project_id,
                ac_id,
                f"Criterio {n}",
                ac_id in done,
            )
    return project_id, developer_id, token


async def _cleanup(pool, project_id: str, developer_id: str):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM projects WHERE project_id = $1", project_id)
        await conn.execute("DELETE FROM developers WHERE developer_id = $1", developer_id)


async def _meta(pool, project_id: str, ac_id: str) -> dict:
    async with pool.acquire() as conn:
        raw = await conn.fetchval(
            "SELECT meta FROM acceptance_criteria WHERE project_id = $1 AND uc_id = 'UC-001' AND ac_id = $2",
            project_id,
            ac_id,
        )
    return json.loads(raw) if isinstance(raw, str) else raw


@pytestmark_pg
@pytest.mark.asyncio
async def test_ac01_native_stores_receipt_with_session_developer_and_date():
    from server.backends.native_backend import NativeBackend

    pool = await _pool()
    project_id, developer_id, token = await _seed(pool)
    try:
        backend = NativeBackend(project_id=project_id, dev_token=token)
        receipt = normalize_evidence({"type": "test", "label": "8 passed", "link": "https://ci.example/run/1"})
        dto = await backend.mark_acceptance_criterion(project_id, "UC-001", "AC-01", True, evidence=receipt)
        assert dto.done is True
        assert len(dto.evidence) == 1
        ev = dto.evidence[0]
        assert {k: ev[k] for k in ("type", "label", "link", "detail")} == receipt
        assert ev["by"] == developer_id and ev["at"] and ev["passed"] is True
        assert dto.verdict["passed"] is True and dto.verdict["by"] == developer_id and dto.verdict["at"]

        # AC-02: texto libre → segunda evidencia, en orden, sin perder la primera.
        await backend.mark_acceptance_criterion(
            project_id, "UC-001", "AC-01", True, evidence=normalize_evidence("captura en doc/evidence")
        )
        # Desmarcar sin evidencia → cambia el veredicto, los recibos se conservan.
        dto3 = await backend.mark_acceptance_criterion(project_id, "UC-001", "AC-01", False)
        assert dto3.verdict["passed"] is False
        [ac1] = [a for a in await backend.get_acceptance_criteria(project_id, "UC-001") if a.id == "AC-01"]
        assert [e["label"] for e in ac1.evidence] == ["8 passed", "captura en doc/evidence"]
        assert ac1.evidence[1]["type"] == "url" and ac1.evidence[1]["link"] is None
        assert ac1.done is False and accepted_from(ac1.done, ac1.verdict) is None
    finally:
        await _cleanup(pool, project_id, developer_id)


@pytestmark_pg
@pytest.mark.asyncio
async def test_ac03_get_uc_on_native_returns_receipts_and_who_accepted(monkeypatch):
    from server.backends.native_backend import NativeBackend
    from server.tools import spec_driven

    pool = await _pool()
    project_id, developer_id, token = await _seed(pool)
    try:
        backend = NativeBackend(project_id=project_id, dev_token=token)

        async def _session_backend(ctx, items_content=None):
            return backend

        monkeypatch.setattr(spec_driven, "get_session_backend", _session_backend)
        await spec_driven.mark_ac(
            board_id=project_id,
            uc_id="UC-001",
            ac_id="AC-01",
            passed=True,
            ctx=None,
            evidence={"type": "pr", "label": "engine#190", "link": "https://github.com/x/y/pull/190"},
        )
        await spec_driven.mark_ac_batch(
            board_id=project_id,
            uc_id="UC-001",
            results=[{"ac_id": "AC-02", "passed": True, "evidence": "12 passed"}, {"ac_id": "AC-03", "passed": True}],
            ctx=None,
        )
        uc = await spec_driven.get_uc(board_id=project_id, uc_id="UC-001", ctx=None)
        acs = {a["id"]: a for a in uc["acceptance_criteria"]}

        ev1 = acs["AC-01"]["evidence"][0]
        assert (ev1["type"], ev1["label"], ev1["link"], ev1["by"]) == (
            "pr",
            "engine#190",
            "https://github.com/x/y/pull/190",
            developer_id,
        )
        assert ev1["at"]
        assert acs["AC-01"]["accepted"]["by"] == developer_id
        assert acs["AC-02"]["evidence"][0]["label"] == "12 passed"
        # AC hecho sin evidencia: lista vacía, pero se sabe quién lo aceptó y cuándo.
        assert acs["AC-03"]["evidence"] == []
        assert acs["AC-03"]["accepted"]["by"] == developer_id
    finally:
        await _cleanup(pool, project_id, developer_id)


_LEGACY = [
    {"text": "AC-01: PASSED — 12 passed\nen dos líneas [2026-09-01 10:00 UTC]", "created_at": "2026-09-01T10:00:05+00:00", "author": "native"},
    {"text": "AC-02: PASSED — captura [2026-09-01 10:05 UTC]", "created_at": "", "author": "native"},
    {"text": "AC-01: PASSED — re-verificado [2026-09-03 08:00 UTC]", "created_at": "2026-09-03T08:00:00+00:00", "author": "native"},
    {
        "text": "Validacion AG-09b [2026-09-04 12:00 UTC]:\n  AC-03: PASSED\n  AC-04: PASSED",
        "created_at": "2026-09-04T12:00:00+00:00",
        "author": "native",
    },
    {"text": "AC-99: PASSED — de un AC que ya no existe [2026-09-01 11:00 UTC]", "created_at": "", "author": "native"},
]


async def _apply_backfill(pool):
    async with pool.acquire() as conn:
        await conn.execute(MIGRATION.read_text())


@pytestmark_pg
@pytest.mark.asyncio
async def test_ac04_backfill_migrates_comments_with_date_and_unknown_author():
    pool = await _pool()  # apply_migrations ya pasó la 0028 sobre una DB sin este proyecto
    project_id, developer_id, _ = await _seed(
        pool, comments=_LEGACY, n_acs=4, done=("AC-01", "AC-02", "AC-03")
    )
    try:
        await _apply_backfill(pool)

        m1 = await _meta(pool, project_id, "AC-01")
        assert [e["label"] for e in m1["evidence"]] == ["12 passed\nen dos líneas", "re-verificado"]
        assert all(e["by"] is None and e["source"] == "migrated" and e["type"] == "url" for e in m1["evidence"])
        assert m1["evidence"][0]["at"].startswith("2026-09-01T10:00:05")
        assert m1["verdict"]["by"] is None and m1["verdict"]["at"].startswith("2026-09-03T08:00:00")

        m2 = await _meta(pool, project_id, "AC-02")
        assert m2["evidence"][0]["at"].startswith("2026-09-01T10:05:00")  # sin created_at: la fecha del texto

        m3 = await _meta(pool, project_id, "AC-03")
        assert "evidence" not in m3  # la línea del lote no trae texto: no hay recibo
        assert m3["verdict"]["passed"] is True and m3["verdict"]["at"].startswith("2026-09-04T12:00:00")

        m4 = await _meta(pool, project_id, "AC-04")
        assert "verdict" not in m4  # el comentario dice PASSED pero el AC no está hecho: no se atribuye

        # Idempotente: aplicarla otra vez no duplica nada.
        await _apply_backfill(pool)
        assert await _meta(pool, project_id, "AC-01") == m1
    finally:
        await _cleanup(pool, project_id, developer_id)


@pytestmark_pg
@pytest.mark.asyncio
async def test_ac04_backfill_keeps_receipts_written_before_it_and_their_verdict():
    from server.backends.native_backend import NativeBackend

    pool = await _pool()
    project_id, developer_id, token = await _seed(pool, comments=_LEGACY[:1], n_acs=1)
    try:
        backend = NativeBackend(project_id=project_id, dev_token=token)
        await backend.mark_acceptance_criterion(
            project_id, "UC-001", "AC-01", True, evidence=normalize_evidence({"type": "diff", "label": "d"})
        )
        await _apply_backfill(pool)

        m1 = await _meta(pool, project_id, "AC-01")
        assert [(e["label"], e["by"]) for e in m1["evidence"]] == [
            ("12 passed\nen dos líneas", None),
            ("d", developer_id),
        ]
        assert m1["verdict"]["by"] == developer_id  # el veredicto con autor gana
    finally:
        await _cleanup(pool, project_id, developer_id)
