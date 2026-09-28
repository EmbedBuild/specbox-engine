"""Surface check of the database exposed through PostgREST (UC-4003, US-40).

Board, panel and portal share one Postgres, and PostgREST serves every schema in
``pgrst.db_schemas`` to whoever holds the project's public (anon) key. A single
careless migration — a view created without ``security_invoker``, a table
without row-level security, an RPC left executable by ``anon`` — reopens what
US-38/US-40 closed, and nothing would say so. This module says so:

* ``view_bypasses_rls`` — a view that runs with its owner's rights
  (``security_invoker`` off, the Postgres default and what ``CREATE OR REPLACE
  VIEW`` silently restores);
* ``table_without_rls`` — a table with row-level security disabled;
* ``function_executable_by_anon`` — a function or procedure ``anon`` may call.
  Trigger and event-trigger functions are left out (they cannot be called
  directly, so they are no surface) and so are extension members;
* ``table_writable_by_public_role`` — a table of ``public`` where ``anon`` or
  ``authenticated`` holds INSERT, UPDATE, DELETE or TRUNCATE (UC-4002). Panel
  and portal schemas are not held to this: their users write through RLS.

Anything found fails the check unless ``surface_allowlist.yaml`` approves it
with a reason; an entry without a reason fails the check on its own. Entries
that match nothing are reported but do not fail, so the same list serves the
engine's CI database (board only) and production (board + site + panel +
portal).

Usage::

    python -m server.db.surface_check [--dsn DSN] [--schemas public,panel,business]
                                      [--allowlist PATH]

Exit codes: 0 clean, 1 findings or an invalid allowlist, 2 usage or connection
error. The DSN defaults to ``SPECBOX_NATIVE_DSN`` and is never printed. Runbook:
``doc/runbooks/db-surface.md``.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import asyncpg
import yaml

DEFAULT_ALLOWLIST = Path(__file__).parent / "surface_allowlist.yaml"
WRITES_CLOSED_SCHEMAS = ("public",)
PUBLIC_ROLES = ("anon", "authenticated")

FINDING_TO_ENTRY_KIND = {
    "view_bypasses_rls": "view",
    "table_without_rls": "table",
    "table_writable_by_public_role": "table",
    "function_executable_by_anon": "function",
}
ENTRY_KINDS = frozenset(FINDING_TO_ENTRY_KIND.values())


@dataclass(frozen=True)
class Finding:
    kind: str
    name: str
    detail: str = ""


@dataclass(frozen=True)
class AllowedException:
    kind: str
    name: str
    reason: str


class AllowlistError(ValueError):
    """The allowlist is unreadable or has entries without kind, name or reason."""


def normalize_name(name: str) -> str:
    """Canonical form for matching: lower case, no blanks (``f(text, int)`` == ``F(text,int)``)."""
    return "".join(name.split()).lower()


def load_allowlist(path: Path | str = DEFAULT_ALLOWLIST) -> list[AllowedException]:
    """Parse and validate the allowlist; every problem is reported at once."""
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise AllowlistError(f"cannot read allowlist {path}: {exc}") from exc
    entries = data.get("exceptions") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        raise AllowlistError(f"{path}: expected a top-level 'exceptions' list")
    allowed: list[AllowedException] = []
    problems: list[str] = []
    for n, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            problems.append(f"entry {n}: not a mapping")
            continue
        kind = str(entry.get("kind") or "").strip()
        name = str(entry.get("name") or "").strip()
        reason = str(entry.get("reason") or "").strip()
        label = name or f"entry {n}"
        if kind not in ENTRY_KINDS:
            problems.append(f"{label}: kind must be one of {sorted(ENTRY_KINDS)}")
        if not name:
            problems.append(f"entry {n}: name is required")
        if not reason:
            problems.append(f"{label}: exception without a reason")
        if kind in ENTRY_KINDS and name and reason:
            allowed.append(AllowedException(kind, name, reason))
    if problems:
        raise AllowlistError("; ".join(problems))
    return allowed


def apply_allowlist(
    findings: Iterable[Finding], allowlist: Iterable[AllowedException]
) -> tuple[list[Finding], list[Finding], list[AllowedException]]:
    """Split findings into (violations, approved) and return the entries that matched nothing."""
    by_key = {(e.kind, normalize_name(e.name)): e for e in allowlist}
    used: set[tuple[str, str]] = set()
    violations: list[Finding] = []
    approved: list[Finding] = []
    for finding in findings:
        key = (FINDING_TO_ENTRY_KIND[finding.kind], normalize_name(finding.name))
        if key in by_key:
            used.add(key)
            approved.append(finding)
        else:
            violations.append(finding)
    unused = [e for key, e in by_key.items() if key not in used]
    return violations, approved, unused


_VIEWS_SQL = """
SELECT format('%s.%s', n.nspname, c.relname) AS name, coalesce(c.reloptions::text, '') AS detail
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE c.relkind = 'v' AND n.nspname = ANY($1::text[])
   AND NOT coalesce(c.reloptions && ARRAY['security_invoker=on', 'security_invoker=true',
                                          'security_invoker=1', 'security_invoker=yes'], false)
 ORDER BY 1
"""

_TABLES_WITHOUT_RLS_SQL = """
SELECT format('%s.%s', n.nspname, c.relname) AS name, '' AS detail
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE c.relkind IN ('r', 'p') AND n.nspname = ANY($1::text[]) AND NOT c.relrowsecurity
 ORDER BY 1
"""

_ANON_FUNCTIONS_SQL = """
SELECT format('%s.%s(%s)', n.nspname, p.proname, oidvectortypes(p.proargtypes)) AS name,
       CASE WHEN p.prosecdef THEN 'security definer' ELSE 'security invoker' END AS detail
  FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
 WHERE n.nspname = ANY($1::text[]) AND p.prokind IN ('f', 'p')
   AND p.prorettype NOT IN ('trigger'::regtype, 'event_trigger'::regtype)
   AND has_function_privilege('anon', p.oid, 'EXECUTE')
   AND NOT EXISTS (SELECT 1 FROM pg_depend d
                    WHERE d.classid = 'pg_proc'::regclass AND d.objid = p.oid AND d.deptype = 'e')
 ORDER BY 1
"""

_WRITABLE_TABLES_SQL = """
SELECT format('%s.%s', n.nspname, c.relname) AS name,
       string_agg(DISTINCT r.rolname || ':' || p.priv, ',' ORDER BY r.rolname || ':' || p.priv) AS detail
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 CROSS JOIN unnest($2::text[]) AS r(rolname)
 CROSS JOIN unnest(ARRAY['INSERT', 'UPDATE', 'DELETE', 'TRUNCATE']) AS p(priv)
 WHERE c.relkind IN ('r', 'p') AND n.nspname = ANY($1::text[])
   AND has_table_privilege(r.rolname, c.oid, p.priv)
 GROUP BY 1
 ORDER BY 1
"""


async def collect_findings(conn: asyncpg.Connection, schemas: Iterable[str]) -> list[Finding]:
    """Everything in ``schemas`` that widens the surface, before the allowlist."""
    schemas = list(schemas)
    findings: list[Finding] = []
    for kind, sql in (
        ("view_bypasses_rls", _VIEWS_SQL),
        ("table_without_rls", _TABLES_WITHOUT_RLS_SQL),
    ):
        findings += [Finding(kind, r["name"], r["detail"]) for r in await conn.fetch(sql, schemas)]
    roles = [r for r in PUBLIC_ROLES if await conn.fetchval("SELECT 1 FROM pg_roles WHERE rolname = $1", r)]
    if "anon" in roles:
        findings += [
            Finding("function_executable_by_anon", r["name"], r["detail"])
            for r in await conn.fetch(_ANON_FUNCTIONS_SQL, schemas)
        ]
    closed = [s for s in schemas if s in WRITES_CLOSED_SCHEMAS]
    if roles and closed:
        findings += [
            Finding("table_writable_by_public_role", r["name"], r["detail"])
            for r in await conn.fetch(_WRITABLE_TABLES_SQL, closed, roles)
        ]
    return findings


def render_report(
    schemas: list[str],
    violations: list[Finding],
    approved: list[Finding],
    unused: list[AllowedException],
) -> str:
    lines = [f"surface check — schemas: {', '.join(schemas)}"]
    for f in violations:
        lines.append(f"  FAIL  {f.kind:32s} {f.name}" + (f"  [{f.detail}]" if f.detail else ""))
    for f in approved:
        lines.append(f"  ok    {f.kind:32s} {f.name}  (approved exception)")
    for e in unused:
        lines.append(f"  info  unused exception           {e.kind} {e.name}")
    verdict = f"{len(violations)} finding(s) outside the approved list" if violations else "clean"
    lines.append(f"result: {verdict}; {len(approved)} approved exception(s) in use")
    return "\n".join(lines)


async def run_check(dsn: str, schemas: list[str], allowlist: list[AllowedException]) -> tuple[int, str]:
    from .pool import _resolve_ssl

    conn = await asyncpg.connect(dsn, ssl=_resolve_ssl(dsn))
    try:
        findings = await collect_findings(conn, schemas)
    finally:
        await conn.close()
    violations, approved, unused = apply_allowlist(findings, allowlist)
    return (1 if violations else 0), render_report(schemas, violations, approved, unused)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m server.db.surface_check",
        description="Fail when the database exposes more than the approved surface (UC-4003).",
    )
    p.add_argument(
        "--dsn", default=os.getenv("SPECBOX_NATIVE_DSN", ""), help="Postgres DSN (default: $SPECBOX_NATIVE_DSN)"
    )
    p.add_argument("--schemas", default="public", help="Comma-separated schemas to check (default: public)")
    p.add_argument("--allowlist", type=Path, default=DEFAULT_ALLOWLIST, help="Approved exceptions (YAML)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    schemas = [s.strip() for s in args.schemas.split(",") if s.strip()]
    if not args.dsn or not schemas:
        print("error: a DSN (--dsn or SPECBOX_NATIVE_DSN) and at least one schema are required", file=sys.stderr)
        return 2
    try:
        allowlist = load_allowlist(args.allowlist)
    except AllowlistError as exc:
        print(f"FAIL  invalid allowlist: {exc}", file=sys.stderr)
        return 1
    try:
        code, report = asyncio.run(run_check(args.dsn, schemas, allowlist))
    except (OSError, asyncpg.PostgresError, asyncio.TimeoutError) as exc:
        print(f"error: cannot run the check: {type(exc).__name__}", file=sys.stderr)
        return 2
    print(report)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
