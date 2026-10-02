"""One version per board migration (UC-6202, US-62).

``server/db/migrations`` is the source of the board schema: the runner
(``server/db/migrate.py``) applies it in the tests and in CI. ``supabase/migrations``
keeps a byte-for-byte copy of each one, named ``<version>_<name>.sql`` (a
14-digit version), and the migrations that only exist in Supabase (site tables,
history the local chain replaced), each declared with a reason in
``migration_twins.yaml``. Production is migrated with ``apply_migration`` from
the copy, so what runs there is what CI tested.

Until this check existed the two folders drifted: twelve copies differed from
their source (comments, an unguarded index, an error message) and three local
migrations had no copy at all. This module says so:

* ``missing_twin`` — a local migration with no copy of the same name;
* ``twin_differs`` — a copy that is not byte-for-byte its local migration;
* ``duplicate_twin`` — two copies of the same name;
* ``undeclared_supabase_only`` — a file of ``supabase/migrations`` with no local
  migration and no entry in ``migration_twins.yaml``;
* ``bad_name`` — a file whose name does not follow its folder's pattern.

A manifest entry without a reason fails on its own; entries that match no file
are reported as unused and do not fail.

Usage::

    python -m server.db.migration_twins [--fix] [--root PATH]

``--fix`` rewrites each copy that differs from its local migration and creates
each missing copy as ``supabase/migrations/<today, UTC>00<NNNN>_<name>.sql``.
Exit codes: 0 clean, 1 findings or an invalid manifest, 2 usage error.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml

ENGINE_ROOT = Path(__file__).resolve().parents[2]
LOCAL_DIR = Path("server/db/migrations")
SUPABASE_DIR = Path("supabase/migrations")
DEFAULT_MANIFEST = Path(__file__).parent / "migration_twins.yaml"

_LOCAL_NAME = re.compile(r"^(?P<number>\d{4})_(?P<name>.+)\.sql$")
_SUPABASE_NAME = re.compile(r"^(?P<version>\d{14})_(?P<name>.+)\.sql$")


@dataclass(frozen=True)
class Finding:
    kind: str
    file: str
    detail: str = ""


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)
    unused: list[str] = field(default_factory=list)
    pairs: int = 0


class ManifestError(ValueError):
    """The manifest is unreadable or has entries without file or reason."""


def load_manifest(path: Path) -> dict[str, str]:
    """``{file: reason}`` of the migrations declared as Supabase-only."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ManifestError(f"cannot read {path}: {exc}") from exc
    declared: dict[str, str] = {}
    for entry in data.get("supabase_only") or []:
        file = str((entry or {}).get("file") or "").strip()
        reason = str((entry or {}).get("reason") or "").strip()
        if not file or not reason:
            raise ManifestError(f"entry without file or reason in {path}: {entry!r}")
        declared[file] = reason
    return declared


def check(root: Path, declared: dict[str, str]) -> Report:
    """Compare ``server/db/migrations`` with ``supabase/migrations`` under ``root``."""
    report = Report()
    copies: dict[str, list[Path]] = {}
    supabase_files = sorted((root / SUPABASE_DIR).glob("*.sql"))
    for path in supabase_files:
        match = _SUPABASE_NAME.match(path.name)
        if not match:
            report.findings.append(Finding("bad_name", str(SUPABASE_DIR / path.name), "expected <14 digits>_<name>.sql"))
            continue
        copies.setdefault(match["name"], []).append(path)

    local_names: set[str] = set()
    for path in sorted((root / LOCAL_DIR).glob("*.sql")):
        match = _LOCAL_NAME.match(path.name)
        local = str(LOCAL_DIR / path.name)
        if not match:
            report.findings.append(Finding("bad_name", local, "expected <4 digits>_<name>.sql"))
            continue
        local_names.add(match["name"])
        twins = copies.get(match["name"], [])
        if not twins:
            report.findings.append(Finding("missing_twin", local, f"no {SUPABASE_DIR}/<version>_{match['name']}.sql"))
            continue
        if len(twins) > 1:
            names = ", ".join(t.name for t in twins)
            report.findings.append(Finding("duplicate_twin", local, names))
            continue
        report.pairs += 1
        if twins[0].read_bytes() != path.read_bytes():
            report.findings.append(Finding("twin_differs", local, str(SUPABASE_DIR / twins[0].name)))

    present = {path.name for path in supabase_files}
    for name, paths in sorted(copies.items()):
        if name in local_names:
            continue
        for path in paths:
            if path.name not in declared:
                report.findings.append(
                    Finding("undeclared_supabase_only", str(SUPABASE_DIR / path.name), "no local migration and no entry in the manifest")
                )
    report.unused = sorted(file for file in declared if file not in present)
    return report


def fix(root: Path, today: datetime | None = None) -> list[str]:
    """Rewrite drifting copies and create missing ones from the local migrations."""
    today = today or datetime.now(timezone.utc)
    copies = {}
    for path in (root / SUPABASE_DIR).glob("*.sql"):
        match = _SUPABASE_NAME.match(path.name)
        if match:
            copies.setdefault(match["name"], []).append(path)

    written: list[str] = []
    for path in sorted((root / LOCAL_DIR).glob("*.sql")):
        match = _LOCAL_NAME.match(path.name)
        if not match:
            continue
        twins = copies.get(match["name"], [])
        if len(twins) > 1:
            continue  # ambiguous: left for a person to resolve
        if twins:
            target = twins[0]
            if target.read_bytes() == path.read_bytes():
                continue
        else:
            version = f"{today:%Y%m%d}{int(match['number']):06d}"
            target = root / SUPABASE_DIR / f"{version}_{match['name']}.sql"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
        written.append(str(SUPABASE_DIR / target.name))
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m server.db.migration_twins", description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=ENGINE_ROOT, help="engine checkout (default: this one)")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--fix", action="store_true", help="copy local migrations over drifting or missing copies")
    args = parser.parse_args(argv)

    if not (args.root / LOCAL_DIR).is_dir():
        print(f"[migration-twins] no {LOCAL_DIR} under {args.root}", file=sys.stderr)
        return 2
    try:
        declared = load_manifest(args.manifest)
    except ManifestError as exc:
        print(f"[migration-twins] {exc}", file=sys.stderr)
        return 1

    if args.fix:
        for written in fix(args.root):
            print(f"[migration-twins] wrote {written}")

    report = check(args.root, declared)
    for entry in report.unused:
        print(f"[migration-twins] unused manifest entry: {entry}")
    for finding in report.findings:
        print(f"[migration-twins] {finding.kind}: {finding.file} — {finding.detail}")
    if report.findings:
        print(
            f"[migration-twins] {len(report.findings)} finding(s). server/db/migrations is the source: "
            "run `python -m server.db.migration_twins --fix`, or declare a Supabase-only migration "
            f"with its reason in {DEFAULT_MANIFEST.relative_to(ENGINE_ROOT)}."
        )
        return 1
    print(f"[migration-twins] OK — {report.pairs} migrations, each with its byte-for-byte copy; {len(declared)} Supabase-only declared.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
