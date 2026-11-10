"""US-117 / UC-11702 — cada justificante registra el commit con el que se comprobó.

El servidor no ve el git de quien marca (MCP remoto): el commit lo manda el recibo.

- **AC-01**: ``mark_ac`` y ``mark_ac_batch`` aceptan un commit y ``get_uc`` lo enseña junto al tipo,
  quién y cuándo.
- **AC-02**: un commit que no tiene entre 7 y 40 hexadecimales se rechaza y no se marca nada.
- **AC-03 / AC-04**: ``/implement`` pone en el recibo el commit comprobado y enlaza a él, no a main.
- **AC-05**: en Trello, Plane y FreeForm el commit va en el comentario y ``get_uc`` lo recupera.
- **AC-06**: un recibo anterior sale sin commit; nunca se deduce uno.

Las de Postgres hacen SKIP limpio sin base de datos de desarrollo.
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

import pytest

from server.ac_evidence import EvidenceError, evidence_comment_text, evidence_from_comments, normalize_evidence
from server.spec_backend import CommentDTO
from tests._native_db import DSN, reachable

PG_OK, PG_SKIP_REASON = reachable()
pytestmark_pg = pytest.mark.skipif(not PG_OK, reason=PG_SKIP_REASON)

ROOT = Path(__file__).resolve().parents[1]
SHA = "61bd6c0e3a9f4b7d2c1e8f5a6b9c0d1e2f3a4b5c"
REPO = "EmbedBuild/specbox-engine"


# ── Unidad ────────────────────────────────────────────────────────────


def test_ac01_commit_and_repo_are_kept_in_lowercase_hex():
    ev = normalize_evidence({"type": "test", "label": "t", "commit": "61BD6C0", "repo": REPO})
    assert (ev["commit"], ev["repo"]) == ("61bd6c0", REPO)
    assert normalize_evidence({"type": "test", "label": "t", "commit": SHA})["commit"] == SHA


@pytest.mark.parametrize(
    ("raw", "fragment"),
    [
        ({"type": "test", "label": "t", "commit": "61bd6c"}, "evidence.commit"),  # 6
        ({"type": "test", "label": "t", "commit": SHA + "a"}, "evidence.commit"),  # 41
        ({"type": "test", "label": "t", "commit": "61bd6cz"}, "evidence.commit"),
        ({"type": "test", "label": "t", "commit": "main"}, "evidence.commit"),
        ({"type": "test", "label": "t", "commit": 1234567}, "evidence.commit"),
        ({"type": "test", "label": "t", "commit": SHA, "repo": "specbox-engine"}, "evidence.repo"),
        ({"type": "test", "label": "t", "commit": SHA, "repo": "a/b/c"}, "evidence.repo"),
    ],
)
def test_ac02_an_invalid_commit_or_repo_is_rejected(raw, fragment):
    with pytest.raises(EvidenceError, match=fragment):
        normalize_evidence(raw)


def test_ac05_the_comment_carries_the_commit_and_is_read_back():
    ev = normalize_evidence(
        {"type": "test", "label": "test_x", "link": "https://ci/1", "detail": "8/8", "commit": SHA, "repo": REPO}
    )
    text = evidence_comment_text(ev)
    assert text == f"[test] test_x <https://ci/1> — 8/8 · commit {REPO}@{SHA}"

    comments = [CommentDTO(id="1", text=f"AC-01: PASSED — {text} [2026-11-10 01:00 UTC]", created_at="")]
    [read] = evidence_from_comments(comments)["AC-01"]
    assert {k: read[k] for k in ("type", "label", "link", "detail", "commit", "repo")} == ev


def test_ac05_a_commit_without_repo_and_a_batch_line():
    ev = normalize_evidence({"type": "screenshot", "label": "Captura", "commit": "abc1234"})
    text = evidence_comment_text(ev)
    assert text == "[screenshot] Captura · commit abc1234"
    batch = CommentDTO(id="1", text=f"Validacion AG-09b [2026-11-10 01:00 UTC]:\n  AC-02: PASSED — {text}", created_at="")
    [read] = evidence_from_comments([batch])["AC-02"]
    assert (read["type"], read["label"], read["commit"], read["repo"]) == ("screenshot", "Captura", "abc1234", None)


def test_ac06_old_comments_have_no_commit_and_none_is_guessed():
    comments = [
        CommentDTO(id="1", text="AC-01: PASSED — 12 passed en 61bd6c0 [2026-09-01 10:00 UTC]", created_at=""),
        CommentDTO(id="2", text="AC-02: PASSED — [pr] engine#189 <https://github.com/x/y/pull/189> [2026-09-01 10:00 UTC]", created_at=""),
    ]
    ev = evidence_from_comments(comments)
    assert ev["AC-01"][0]["commit"] is None and ev["AC-01"][0]["label"] == "12 passed en 61bd6c0"
    assert ev["AC-02"][0]["commit"] is None and ev["AC-02"][0]["type"] == "pr"


def test_free_text_without_commit_keeps_the_comment_byte_identical():
    assert evidence_comment_text(normalize_evidence("12 passed")) == "12 passed"


# ── AC-03 / AC-04 · /implement ────────────────────────────────────────


def test_ac03_ac04_implement_records_the_tested_commit_and_links_to_it():
    skill = (ROOT / ".claude/skills/implement/SKILL.md").read_text(encoding="utf-8")
    assert not re.search(r"github\.com/\S*/blob/main/", skill), "un justificante no enlaza a main: main se mueve"
    assert "TESTED_COMMIT=$(git rev-parse HEAD)" in skill
    assert "tested_commit.json" in skill
    assert re.search(r'"commit": "\{tested_commit\}"', skill), "el recibo de la verificación lleva el commit"
    assert "blob/{tested_commit}/" in skill
    # El commit se apunta en la rama, antes de volver a main en 8.5.3.
    assert skill.index("### 7.5.11") < skill.index("### 8.5.3")
    validator = (ROOT / "agents/acceptance-validator.md").read_text(encoding="utf-8")
    assert '"commit": "<tested_commit>"' in validator


# ── AC-01 y AC-06 en el board native ─────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_shared_pool():
    import server.db.pool as poolmod

    poolmod._pool = None
    yield
    poolmod._pool = None


async def _seed():
    from server.coordination.identity import add_project_member, register_developer, register_mcp_token
    from server.db.migrate import apply_migrations
    from server.db.pool import init_pool

    pool = await init_pool(dsn=DSN)
    await apply_migrations(pool)
    project_id = f"Acme/ac-commit-{uuid.uuid4().hex[:8]}"
    developer_id = f"cm-dev-{uuid.uuid4().hex[:8]}"
    token = f"cm-tok-{uuid.uuid4().hex[:16]}"
    old = {"evidence": [{"type": "test", "label": "antiguo", "link": None, "detail": None,
                        "by": developer_id, "at": "2026-10-01T10:00:00+00:00", "passed": True}],
           "verdict": {"passed": True, "by": developer_id, "at": "2026-10-01T10:00:00+00:00"}}
    async with pool.acquire() as conn:
        await register_developer(conn, developer_id=developer_id, display_name="Commit Tester")
        await register_mcp_token(conn, developer_id=developer_id, token=token)
        await conn.execute("INSERT INTO projects (project_id, name) VALUES ($1, 'Commit')", project_id)
        await add_project_member(conn, project_id=project_id, developer_id=developer_id, role="project_admin")
        await conn.execute("INSERT INTO user_stories (id, project_id, name, state) VALUES ('US-01', $1, 'US', 'backlog')", project_id)
        await conn.execute(
            "INSERT INTO use_cases (id, project_id, us_id, name, state, labels, meta) "
            "VALUES ('UC-001', $1, 'US-01', 'UC-001: UC', 'backlog', '[\"UC\"]'::jsonb, '{\"uc_id\": \"UC-001\"}'::jsonb)",
            project_id,
        )
        for ac_id, meta, done in (("AC-01", {}, False), ("AC-02", {}, False), ("AC-03", old, True)):
            await conn.execute(
                "INSERT INTO acceptance_criteria (id, project_id, uc_id, ac_id, text, done, meta) "
                "VALUES ($1, $2, 'UC-001', $3, 'Criterio', $4, $5::jsonb)",
                f"UC-001::{ac_id}", project_id, ac_id, done, json.dumps(meta),
            )
    return pool, project_id, developer_id, token


@pytestmark_pg
@pytest.mark.asyncio
async def test_ac01_ac02_ac06_native(monkeypatch):
    from server.backends.native_backend import NativeBackend
    from server.tools import spec_driven

    pool, project_id, developer_id, token = await _seed()
    try:
        backend = NativeBackend(project_id=project_id, dev_token=token)

        async def _session_backend(ctx, items_content=None):
            return backend

        monkeypatch.setattr(spec_driven, "get_session_backend", _session_backend)
        await spec_driven.mark_ac(
            board_id=project_id, uc_id="UC-001", ac_id="AC-01", passed=True, ctx=None,
            evidence={"type": "test", "label": "test_x", "commit": SHA, "repo": REPO},
        )
        await spec_driven.mark_ac_batch(
            board_id=project_id, uc_id="UC-001", ctx=None,
            results=[{"ac_id": "AC-02", "passed": True, "evidence": {"type": "pr", "label": "#338", "commit": "61bd6c0"}}],
        )
        bad = await spec_driven.mark_ac(
            board_id=project_id, uc_id="UC-001", ac_id="AC-02", passed=False, ctx=None,
            evidence={"type": "test", "label": "x", "commit": "no-es-un-sha"},
        )
        assert bad["code"] == "INVALID_EVIDENCE"  # AC-02

        uc = await spec_driven.get_uc(board_id=project_id, uc_id="UC-001", ctx=None)
        acs = {a["id"]: a for a in uc["acceptance_criteria"]}
        ev1 = acs["AC-01"]["evidence"][0]
        assert (ev1["type"], ev1["commit"], ev1["repo"], ev1["by"]) == ("test", SHA, REPO, developer_id) and ev1["at"]
        assert acs["AC-02"]["done"] is True, "el rechazo no desmarca nada"
        assert acs["AC-02"]["evidence"][0]["commit"] == "61bd6c0" and acs["AC-02"]["evidence"][0]["repo"] is None
        old = acs["AC-03"]["evidence"][0]
        assert (old["label"], old["commit"], old["repo"]) == ("antiguo", None, None)  # AC-06
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM projects WHERE project_id = $1", project_id)
            await conn.execute("DELETE FROM developers WHERE developer_id = $1", developer_id)
