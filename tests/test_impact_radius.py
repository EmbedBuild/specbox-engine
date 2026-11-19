"""UC-12606 (US-126) — el gobierno depende del radio de impacto del cambio real.

La parte del servidor; el hook impact-radius-guard tiene sus pruebas en
tests/hooks/impact-radius-guard.test.mjs.

- AC-02: la aprobación de un cambio de contrato o de migración es un skip_enforcement de una
  persona (un subagente no puede darlo), que el hook gasta una vez con use_enforcement_skip; el
  triaje de /implement la pide por adelantado (decision_key impact_radius_approval, siempre «ask»).
- La medida impact_radius está activa desde 6.47.0.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

from server.app_docs.autopilot import DECISION_KEYS
from server.app_docs.queue import INVIOLABLE_FOR_QUEUE
from server.coordination.enforcement import MEASURES
from server.impact_radius import classify_path, impact_decision, plan_impact
from server.tools.enforcement import skip_enforcement, use_enforcement_skip
from server.tools.preflight import analyze_preflight_decisions_impl
from tests._native_db import DSN, reachable

ROOT = Path(__file__).resolve().parent.parent
MOTIVO = "La persona revisó la migración y la aprueba para esta UC."
BLOCK = json.dumps({"schema": 1, "origin": "existing", "skips": [],
                    "measures": {"impact_radius": {"mode": "block", "block_since": "2026-11-19T00:00:00+00:00"}}})

PLAN = """# Plan UC-12606
### Fase 1: Esquema
**Criterios:** UC-12606 AC-01
**Ficheros:** server/db/migrations/0041_impacto.sql, server/drift.py
### Fase 2: Contrato
**Criterios:** UC-12606 AC-02
**Ficheros:** api/openapi.yaml
### Fase 3: Interno
**Criterios:** UC-12606 AC-03
**Ficheros:** server/impact_radius.py
"""


def test_impact_radius_is_active_since_6_47():
    assert MEASURES["impact_radius"].since == "6.47.0"


def test_the_plan_phases_with_contract_or_migration_are_found():
    found = plan_impact(PLAN)
    assert [(p["phase"], p["class"], p["files"]) for p in found] == [
        ("Fase 1: Esquema", "data_migration", ["server/db/migrations/0041_impacto.sql"]),
        ("Fase 2: Contrato", "api_contract", ["api/openapi.yaml"]),
    ]
    assert impact_decision("# Plan\n### Fase 1\n**Criterios:** AC-01\n**Ficheros:** server/a.py\n") is None


def test_the_path_rules_are_the_same_as_the_hook_defaults():
    """El triaje y el hook clasifican igual las rutas con las reglas por defecto."""
    if not shutil.which("node"):
        pytest.skip("sin node")
    paths = [
        "api/openapi.yaml", "docs/openapi-v2.json", "proto/cobros.proto", "web/schema.graphql",
        "web/api.graphql", "api/swagger.yml", "server/db/migrations/0041_x.sql", "supabase/migrations/2026_x.sql",
        "db/seed.sql", "prisma/schema.prisma", "apps/api/prisma/schema.prisma", "app/alembic/versions/0001_x.py",
        "db/migrate/20260101_x.rb", "docs/migrations/README.md", "server/a.py", "package.json", "README.md",
        "openapi.md", "db/esquema_señal.sql", "src/graphql/queries/getUser.graphql", "supabase/seed.sql",
        "tests/fixtures/data.sql", "db/migrations/seed_roles.sql", "apps/test/migrations/001.sql",
    ]
    script = (
        "import { classifyCommit } from './.claude/hooks/lib/impact-radius.mjs';"
        f"const paths = {json.dumps(paths)};"
        "console.log(JSON.stringify(paths.map((p) => { const c = classifyCommit([p]).class;"
        " return c === 'api_contract' || c === 'data_migration' ? c : null; })));"
    )
    out = subprocess.run(["node", "--input-type=module", "-e", script], cwd=ROOT, capture_output=True, text=True,
                         check=True)
    assert json.loads(out.stdout) == [classify_path(p) for p in paths]


def test_the_triage_asks_once_in_every_autopilot_level():
    for level in ("low", "conservador", "equilibrado", "agresivo"):
        out = analyze_preflight_decisions_impl(PLAN, autopilot_level=level)
        mine = [d for d in out["user_dependent_decisions"] if d["decision_key"] == "impact_radius_approval"]
        assert len(mine) == 1 and out["verdict"] == "needs_user_input", level
        assert "Fase 1: Esquema" in mine[0]["description"] and "skip_enforcement" in mine[0]["description"]
    key = DECISION_KEYS["impact_radius_approval"]
    assert set(key["tiers"].values()) == {"ask"} and key["inviolable"] is True
    assert "impact_radius_approval" in INVIOLABLE_FOR_QUEUE
    mjs = (ROOT / ".claude/hooks/lib/autopilot.mjs").read_text()
    line = mjs.split("impact_radius_approval:")[1].split("\n")[0]
    assert "agresivo: 'ask'" in line and "inviolable: true" in line
    assert "impact_radius_approval" in (ROOT / ".claude/skills/implement/SKILL.md").read_text()


# ── La aprobación (FreeForm por contenido) ───────────────────────────


async def test_a_subagent_cannot_approve_and_the_main_session_can():
    sub = await skip_enforcement(None, "impact_radius", "UC-7", MOTIVO, policy_content=BLOCK, actor="Ana",
                                 client_session_id="s1", client_agent_id="agent-1", client_agent_type="general")
    assert sub["code"] == "SUBAGENT_CANNOT_APPROVE"
    # Sin el contexto de Claude Code (lo pone el hook) no consta que sea una persona.
    anon = await skip_enforcement(None, "impact_radius", "UC-7", MOTIVO, policy_content=BLOCK, actor="Ana")
    assert anon["code"] == "PERSON_REQUIRED"
    ok = await skip_enforcement(None, "impact_radius", "UC-7", MOTIVO, policy_content=BLOCK, actor="Ana",
                                client_session_id="s1")
    assert ok["success"] and ok["skip"]["by"] == "Ana" and ok["skip"]["measure"] == "impact_radius"
    assert ok["skip"]["session_id"] == "s1"  # queda desde qué sesión se aprobó
    # Las demás medidas siguen como estaban: su salto no es la aprobación de una persona.
    other = json.dumps({"schema": 1, "origin": "existing", "skips": [],
                        "measures": {"spec_quality": {"mode": "block"}}})
    assert (await skip_enforcement(None, "spec_quality", "UC-7", MOTIVO, policy_content=other,
                                   client_agent_id="agent-1"))["success"]


HEAD = "a" * 40
FP1 = "1" * 64
FP2 = "2" * 64


async def test_the_approval_is_spent_on_one_attempt_and_reused_only_for_that_same_attempt():
    approved = await skip_enforcement(None, "impact_radius", "UC-7", MOTIVO, policy_content=BLOCK, actor="Ana",
                                      client_session_id="s1")
    first = await use_enforcement_skip(None, "impact_radius", "UC-7", HEAD, FP1, policy_content=approved["policy_content"])
    assert first["used"] is True and first["reused"] is False and first["skip"]["reason"] == MOTIVO
    stored = json.loads(first["policy_content"])
    assert stored["skips"] == [] and stored["used_skips"][0]["fingerprint"] == FP1
    # El commit falló y se repite igual: la misma aprobación, sin gastar otra.
    again = await use_enforcement_skip(None, "impact_radius", "UC-7", HEAD, FP1, policy_content=first["policy_content"])
    assert again["used"] is True and again["reused"] is True and "policy_content" not in again
    # Otro contenido (o otro commit) necesita otra aprobación.
    other = await use_enforcement_skip(None, "impact_radius", "UC-7", HEAD, FP2, policy_content=first["policy_content"])
    assert other["used"] is False
    other_uc = await use_enforcement_skip(None, "impact_radius", "UC-8", HEAD, FP1, policy_content=approved["policy_content"])
    assert other_uc["used"] is False
    # La lista de lo gastado sobrevive a otros cambios de la política.
    assert "used_skips" in __import__("server.coordination.enforcement", fromlist=["_stored"])._stored(stored)


async def test_use_enforcement_skip_rejects_bad_input_with_a_code():
    assert (await use_enforcement_skip(None, "spec_quality", "UC-7", HEAD, FP1, policy_content=BLOCK))["code"] == "NOT_CLIENT_SPENT"
    assert (await use_enforcement_skip(None, "x" * 100_000, "UC-7", HEAD, FP1, policy_content=BLOCK))["code"] == "NOT_CLIENT_SPENT"
    assert (await use_enforcement_skip(None, "impact_radius", "x", HEAD, FP1, policy_content=BLOCK))["code"] == "INVALID_UC_ID"
    assert (await use_enforcement_skip(None, "impact_radius", "UC-7", "zz", FP1, policy_content=BLOCK))["code"] == "INVALID_ATTEMPT"
    for bad in ("{roto", "[1, 2]", "[" * 200_000 + "]" * 200_000):
        out = await use_enforcement_skip(None, "impact_radius", "UC-7", HEAD, FP1, policy_content=bad)
        assert out.get("success") is False and out["code"] in ("INVALID_POLICY_CONTENT", "INVALID_POLICY"), out


def test_the_triage_follows_the_measure_mode_and_the_project_globs():
    warn = analyze_preflight_decisions_impl(PLAN, autopilot_level="agresivo", impact_radius_mode="warn")
    assert not [d for d in warn["decisions"] if d["decision_key"] == "impact_radius_approval"]
    tools_plan = "# Plan\n### Fase 1: Tool\n**Criterios:** UC-1 AC-01\n**Ficheros:** server/tools/enforcement.py\n"
    plain = analyze_preflight_decisions_impl(tools_plan, impact_radius_mode="block")
    assert not [d for d in plain["decisions"] if d["decision_key"] == "impact_radius_approval"]
    with_globs = analyze_preflight_decisions_impl(tools_plan, impact_radius_mode="block",
                                                  impact={"signature_globs": ["server/tools/*.py"]})
    [d] = [d for d in with_globs["user_dependent_decisions"] if d["decision_key"] == "impact_radius_approval"]
    assert "server/tools/enforcement.py (si cambia la firma" in d["description"]
    bad = analyze_preflight_decisions_impl(tools_plan, impact={"api_globs": ["*" * 30]})
    assert bad["code"] == "INVALID_IMPACT"


def test_the_template_sends_the_identity_and_registers_the_hook():
    for path in (".claude/settings.json", "templates/settings.json.template"):
        text = (ROOT / path).read_text()
        assert "approve_criteria|skip_enforcement)" in text, path
        assert "node .claude/hooks/impact-radius-guard.mjs" in text, path
    engine = json.loads((ROOT / ".claude/settings.json").read_text())
    assert engine["impact"]["signature_globs"] == ["server/tools/*.py"]


# ── native ───────────────────────────────────────────────────────────

PG_OK, PG_SKIP_REASON = reachable()
pg = pytest.mark.skipif(not PG_OK, reason=PG_SKIP_REASON)


@pg
async def test_native_spends_the_approval_once_and_only_for_members():
    from server.coordination.identity import add_project_member, register_developer, register_mcp_token
    from server.db.migrate import apply_migrations
    from server.db.pool import init_pool
    from server.tools.enforcement import set_enforcement_mode

    pool = await init_pool(dsn=DSN)
    await apply_migrations(pool)
    project_id = f"Acme/impact-{uuid.uuid4().hex[:8]}"
    people = []
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO projects (project_id, name) VALUES ($1, 'Impacto')", project_id)
        for role in ("project_admin", "member", None):
            developer_id = f"imp-dev-{uuid.uuid4().hex[:8]}"
            token = f"imp-tok-{uuid.uuid4().hex[:16]}"
            await register_developer(conn, developer_id=developer_id, display_name=developer_id)
            await register_mcp_token(conn, developer_id=developer_id, token=token)
            if role:
                await add_project_member(conn, project_id=project_id, developer_id=developer_id, role=role)
            people.append((developer_id, token))
    admin, member, stranger = people
    try:
        ask = await set_enforcement_mode(None, "impact_radius", "block", board_id=project_id, dev_token=admin[1])
        await set_enforcement_mode(None, "impact_radius", "block", board_id=project_id, dev_token=admin[1],
                                   confirm=ask["confirm"])
        sub = await skip_enforcement(None, "impact_radius", "UC-7", MOTIVO, board_id=project_id, dev_token=member[1],
                                     client_session_id="s1", client_agent_id="agent-1")
        assert sub["code"] == "SUBAGENT_CANNOT_APPROVE"
        anon = await skip_enforcement(None, "impact_radius", "UC-7", MOTIVO, board_id=project_id, dev_token=member[1])
        assert anon["code"] == "PERSON_REQUIRED"
        ok = await skip_enforcement(None, "impact_radius", "UC-7", MOTIVO, board_id=project_id, dev_token=member[1],
                                    client_session_id="s1")
        assert ok["success"]
        hidden = await use_enforcement_skip(None, "impact_radius", "UC-7", HEAD, FP1, board_id=project_id,
                                            dev_token=stranger[1])
        assert not hidden.get("success")
        used = await use_enforcement_skip(None, "impact_radius", "UC-7", HEAD, FP1, board_id=project_id, dev_token=member[1])
        assert used["used"] is True and used["skip"]["by"] == member[0] and used["reused"] is False
        again = await use_enforcement_skip(None, "impact_radius", "UC-7", HEAD, FP1, board_id=project_id, dev_token=member[1])
        assert again["used"] is True and again["reused"] is True
        other = await use_enforcement_skip(None, "impact_radius", "UC-7", HEAD, FP2, board_id=project_id, dev_token=member[1])
        assert other["used"] is False
        meta = await pool.fetchval(
            "SELECT metadata FROM audit_log WHERE project_id = $1 AND operation = 'enforcement_skip'", project_id
        )
        assert (json.loads(meta) if isinstance(meta, str) else meta)["session_id"] == "s1"
        row = await pool.fetchval(
            "SELECT count(*) FROM audit_log WHERE project_id = $1 AND operation = 'enforcement_skip'", project_id
        )
        assert row == 1  # la aprobación queda registrada con quién, cuándo y por qué
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM audit_log WHERE project_id = $1", project_id)
            await conn.execute("DELETE FROM projects WHERE project_id = $1", project_id)
            for developer_id, _ in people:
                await conn.execute("DELETE FROM developers WHERE developer_id = $1", developer_id)
