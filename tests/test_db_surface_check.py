"""UC-4003 (US-40) — the database surface is checked on every schema change.

- AC-01: the check fails when a view skips row-level security, a table has it
  disabled, a function is executable by anon, or a table of public is writable
  by a public role — unless the approved list says otherwise.
- AC-02: next to the check lives the approved list (site event ingestion, the
  site's public views, the portal's read gate) with a reason per entry; an entry
  without a reason fails the check, and so does a public function outside it.

Unit tests need no database; the rest are Postgres-gated like the native suite.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import uuid
from pathlib import Path

import asyncpg
import pytest

from server.db import surface_check as sc
from server.db.pool import _resolve_ssl
from tests._native_db import DSN, reachable

REPO = Path(__file__).resolve().parent.parent


async def _connect() -> asyncpg.Connection:
    return await asyncpg.connect(DSN, ssl=_resolve_ssl(DSN))


# ── Allowlist (AC-02) ────────────────────────────────────────────────


def test_ac02_the_shipped_allowlist_covers_the_known_exceptions_with_reasons():
    allowed = sc.load_allowlist()
    names = {(e.kind, sc.normalize_name(e.name)) for e in allowed}
    assert ("function", sc.normalize_name("public.ingest_site_event(text, text, text, text, text, jsonb)")) in names
    assert ("view", "public.site_activity") in names and ("view", "public.site_stats") in names
    assert ("view", "business.project_specs") in names
    assert all(len(e.reason) >= 40 for e in allowed), "every exception explains itself"


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "allowlist.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_ac02_an_exception_without_a_reason_is_rejected(tmp_path):
    path = _write(
        tmp_path,
        "exceptions:\n"
        "  - kind: function\n    name: public.f(text)\n    reason: '  '\n"
        "  - kind: view\n    name: public.v\n",
    )
    with pytest.raises(sc.AllowlistError) as exc:
        sc.load_allowlist(path)
    assert "public.f(text): exception without a reason" in str(exc.value)
    assert "public.v: exception without a reason" in str(exc.value)


@pytest.mark.parametrize(
    "text",
    [
        "exceptions:\n  - kind: schema\n    name: public\n    reason: because it is fine and documented\n",
        "exceptions:\n  - kind: view\n    reason: a view without a name cannot be matched\n",
        "not_exceptions: []\n",
        "exceptions: [\n",
    ],
)
def test_ac02_malformed_allowlists_are_rejected(tmp_path, text):
    with pytest.raises(sc.AllowlistError):
        sc.load_allowlist(_write(tmp_path, text))


def test_apply_allowlist_matches_ignoring_blanks_and_case():
    findings = [
        sc.Finding("function_executable_by_anon", "public.f(text, integer)"),
        sc.Finding("view_bypasses_rls", "public.v"),
        sc.Finding("table_without_rls", "public.t"),
    ]
    allowlist = [
        sc.AllowedException("function", "PUBLIC.f(text,integer)", "reviewed and documented reason"),
        sc.AllowedException("table", "public.gone", "an entry that matches nothing"),
    ]
    violations, approved, unused = sc.apply_allowlist(findings, allowlist)
    assert [f.name for f in approved] == ["public.f(text, integer)"]
    assert [f.name for f in violations] == ["public.v", "public.t"]
    assert [e.name for e in unused] == ["public.gone"]


def test_an_entry_of_another_kind_does_not_approve_a_finding():
    violations, approved, _ = sc.apply_allowlist(
        [sc.Finding("view_bypasses_rls", "public.x")],
        [sc.AllowedException("table", "public.x", "same name, different kind of object")],
    )
    assert approved == [] and len(violations) == 1


def test_cli_fails_on_an_invalid_allowlist_before_touching_the_database(tmp_path, capsys):
    path = _write(tmp_path, "exceptions:\n  - kind: view\n    name: public.v\n")
    assert sc.main(["--dsn", "postgresql://nobody@127.0.0.1:1/none", "--allowlist", str(path)]) == 1
    assert "exception without a reason" in capsys.readouterr().err


def test_cli_needs_a_dsn(monkeypatch, capsys):
    monkeypatch.delenv("SPECBOX_NATIVE_DSN", raising=False)
    assert sc.main(["--dsn", ""]) == 2


def test_the_check_connects_without_a_statement_cache(monkeypatch):
    """Production goes through the Supabase pooler in transaction mode, which rejects
    asyncpg's named prepared statements (DuplicatePreparedStatementError on the first
    run of 2026-09-28): the check connects like the engine pool, with no cache."""
    seen: dict = {}

    class _Conn:
        async def close(self) -> None:
            seen["closed"] = True

    async def fake_connect(dsn, **kwargs):
        seen.update(kwargs)
        return _Conn()

    async def no_findings(conn, schemas):
        return []

    monkeypatch.delenv("SPECBOX_NATIVE_SSL", raising=False)
    monkeypatch.setattr(sc.asyncpg, "connect", fake_connect)
    monkeypatch.setattr(sc, "collect_findings", no_findings)
    code, report = asyncio.run(sc.run_check("postgresql://u@db.example.supabase.co:6543/postgres", ["public"], []))
    assert code == 0 and "result: clean" in report
    assert seen["statement_cache_size"] == 0 and seen["ssl"] == "require" and seen["closed"]


# ── Against Postgres (AC-01) ─────────────────────────────────────────

_PG_OK, _PG_SKIP_REASON = reachable()
pg = pytest.mark.skipif(not _PG_OK, reason=_PG_SKIP_REASON)


async def _supabase_like_database() -> None:
    """Roles and default privileges as Supabase ships them, then the engine migrations."""
    from server.db.migrate import apply_migrations

    conn = await _connect()
    try:
        for role, options in (("anon", ""), ("authenticated", ""), ("service_role", " BYPASSRLS")):
            if not await conn.fetchval("SELECT 1 FROM pg_roles WHERE rolname = $1", role):
                await conn.execute(f"CREATE ROLE {role} NOLOGIN{options}")
        await conn.execute(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO anon, authenticated, service_role"
        )
        await apply_migrations(conn)
    finally:
        await conn.close()


@pg
async def test_ac01_the_engine_schema_is_clean():
    await _supabase_like_database()
    conn = await _connect()
    try:
        findings = await sc.collect_findings(conn, ["public"])
    finally:
        await conn.close()
    violations, _, _ = sc.apply_allowlist(findings, sc.load_allowlist())
    assert violations == []


@pg
async def test_ac01_each_kind_of_exposure_is_reported():
    await _supabase_like_database()
    probe = f"uc4003_{uuid.uuid4().hex[:8]}"
    conn = await _connect()
    try:
        tr = conn.transaction()
        await tr.start()
        try:
            await conn.execute(f"CREATE SCHEMA {probe}")
            await conn.execute(f"CREATE TABLE {probe}.open_table (id int)")
            await conn.execute(f"CREATE TABLE {probe}.closed_table (id int)")
            await conn.execute(f"ALTER TABLE {probe}.closed_table ENABLE ROW LEVEL SECURITY")
            await conn.execute(f"CREATE VIEW {probe}.owner_view AS SELECT id FROM {probe}.closed_table")
            await conn.execute(
                f"CREATE VIEW {probe}.invoker_view WITH (security_invoker = on) AS SELECT id FROM {probe}.closed_table"
            )
            await conn.execute(f"CREATE FUNCTION {probe}.rpc(p text) RETURNS int LANGUAGE sql AS 'select 1'")
            await conn.execute(f"GRANT EXECUTE ON FUNCTION {probe}.rpc(text) TO anon")
            await conn.execute(f"CREATE FUNCTION {probe}.closed_rpc() RETURNS int LANGUAGE sql AS 'select 2'")
            await conn.execute(f"REVOKE ALL ON FUNCTION {probe}.closed_rpc() FROM PUBLIC, anon")
            await conn.execute(
                f"CREATE FUNCTION {probe}.trg() RETURNS trigger LANGUAGE plpgsql AS 'begin return new; end'"
            )
            await conn.execute("CREATE TABLE public.uc4003_writable (id int)")
            await conn.execute("ALTER TABLE public.uc4003_writable ENABLE ROW LEVEL SECURITY")
            await conn.execute("GRANT INSERT ON public.uc4003_writable TO anon")

            findings = await sc.collect_findings(conn, [probe, "public"])
            got = {(f.kind, f.name) for f in findings}
            assert ("table_without_rls", f"{probe}.open_table") in got
            assert ("view_bypasses_rls", f"{probe}.owner_view") in got
            assert ("function_executable_by_anon", f"{probe}.rpc(text)") in got
            assert ("table_writable_by_public_role", "public.uc4003_writable") in got
            assert ("table_without_rls", f"{probe}.closed_table") not in got
            assert ("view_bypasses_rls", f"{probe}.invoker_view") not in got
            assert not any(name.startswith(f"{probe}.closed_rpc") or name.startswith(f"{probe}.trg") for _, name in got)

            reason = "approved in this test with a written reason"
            violations, approved, _ = sc.apply_allowlist(
                findings, [sc.AllowedException("function", f"{probe}.rpc(text)", reason)]
            )
            assert [f.name for f in approved] == [f"{probe}.rpc(text)"]
            assert all(f.name != f"{probe}.rpc(text)" for f in violations)
        finally:
            await tr.rollback()
    finally:
        await conn.close()


async def _with_probe_schema(sql: list[str]) -> None:
    conn = await _connect()
    try:
        for statement in sql:
            await conn.execute(statement)
    finally:
        await conn.close()


def _cli(*args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, SPECBOX_NATIVE_DSN=DSN)
    return subprocess.run(
        [sys.executable, "-m", "server.db.surface_check", *args],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


@pg
def test_ac01_ac02_the_cli_fails_on_a_public_function_outside_the_list(tmp_path):
    probe = f"uc4003_cli_{uuid.uuid4().hex[:8]}"
    asyncio.run(_supabase_like_database())
    asyncio.run(
        _with_probe_schema(
            [
                f"CREATE SCHEMA {probe}",
                f"CREATE FUNCTION {probe}.rpc(p text) RETURNS int LANGUAGE sql AS 'select 1'",
                f"GRANT EXECUTE ON FUNCTION {probe}.rpc(text) TO anon",
            ]
        )
    )
    try:
        outside = _cli("--schemas", probe)
        assert outside.returncode == 1, outside.stdout + outside.stderr
        assert "FAIL  function_executable_by_anon" in outside.stdout and f"{probe}.rpc(text)" in outside.stdout

        approved = _write(
            tmp_path,
            (
                f"exceptions:\n  - kind: function\n    name: {probe}.rpc(text)\n"
                "    reason: approved for this test, with a reason that says why\n"
            ),
        )
        inside = _cli("--schemas", probe, "--allowlist", str(approved))
        assert inside.returncode == 0, inside.stdout + inside.stderr
        assert "result: clean; 1 approved exception(s) in use" in inside.stdout

        no_reason = tmp_path / "no_reason.yaml"
        no_reason.write_text(f"exceptions:\n  - kind: function\n    name: {probe}.rpc(text)\n", encoding="utf-8")
        invalid = _cli("--schemas", probe, "--allowlist", str(no_reason))
        assert invalid.returncode == 1 and "exception without a reason" in invalid.stderr
    finally:
        asyncio.run(_with_probe_schema([f"DROP SCHEMA {probe} CASCADE"]))
