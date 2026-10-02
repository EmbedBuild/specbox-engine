"""One version per board migration (UC-6202, US-62).

server/db/migrations is the source; supabase/migrations keeps a byte-for-byte copy
of each migration plus the Supabase-only ones declared in migration_twins.yaml.
"""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from server.db.migration_twins import (
    DEFAULT_MANIFEST,
    ENGINE_ROOT,
    ManifestError,
    check,
    fix,
    load_manifest,
    main,
)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    local = tmp_path / "server" / "db" / "migrations"
    supabase = tmp_path / "supabase" / "migrations"
    local.mkdir(parents=True)
    supabase.mkdir(parents=True)
    (local / "0001_schema.sql").write_text("CREATE TABLE a (id int);\n", encoding="utf-8")
    (supabase / "20260522000001_schema.sql").write_text("CREATE TABLE a (id int);\n", encoding="utf-8")
    return tmp_path


def kinds(report):
    return [(f.kind, Path(f.file).name) for f in report.findings]


def test_identical_copies_are_clean(repo):
    report = check(repo, {})
    assert report.findings == []
    assert report.pairs == 1


def test_a_copy_that_differs_even_in_a_comment_fails(repo):
    (repo / "supabase/migrations/20260522000001_schema.sql").write_text(
        "-- mirror\nCREATE TABLE a (id int);\n", encoding="utf-8"
    )
    assert kinds(check(repo, {})) == [("twin_differs", "0001_schema.sql")]


def test_a_new_migration_without_copy_fails(repo):
    (repo / "server/db/migrations/0002_more.sql").write_text("SELECT 1;\n", encoding="utf-8")
    assert kinds(check(repo, {})) == [("missing_twin", "0002_more.sql")]


def test_two_copies_of_the_same_migration_fail(repo):
    (repo / "supabase/migrations/20260601000001_schema.sql").write_text("CREATE TABLE a (id int);\n", encoding="utf-8")
    assert kinds(check(repo, {})) == [("duplicate_twin", "0001_schema.sql")]


def test_supabase_only_migration_must_be_declared(repo):
    (repo / "supabase/migrations/20260618000020_site_tables.sql").write_text("SELECT 1;\n", encoding="utf-8")
    assert kinds(check(repo, {})) == [("undeclared_supabase_only", "20260618000020_site_tables.sql")]
    assert check(repo, {"20260618000020_site_tables.sql": "site tables"}).findings == []


def test_badly_named_files_fail(repo):
    (repo / "server/db/migrations/schema_v2.sql").write_text("SELECT 1;\n", encoding="utf-8")
    (repo / "supabase/migrations/2026_schema.sql").write_text("SELECT 1;\n", encoding="utf-8")
    assert sorted(kinds(check(repo, {}))) == [("bad_name", "2026_schema.sql"), ("bad_name", "schema_v2.sql")]


def test_unused_manifest_entries_are_reported_without_failing(repo):
    report = check(repo, {"20250101000001_gone.sql": "removed"})
    assert report.findings == []
    assert report.unused == ["20250101000001_gone.sql"]


def test_manifest_entry_without_reason_is_rejected(tmp_path):
    manifest = tmp_path / "twins.yaml"
    manifest.write_text("supabase_only:\n  - file: 20260618000020_site_tables.sql\n", encoding="utf-8")
    with pytest.raises(ManifestError, match="without file or reason"):
        load_manifest(manifest)


def test_fix_rewrites_drift_and_creates_missing_copies(repo):
    (repo / "supabase/migrations/20260522000001_schema.sql").write_text("-- old\n", encoding="utf-8")
    (repo / "server/db/migrations/0029_new.sql").write_text("SELECT 29;\n", encoding="utf-8")

    written = fix(repo, today=datetime(2026, 10, 2, tzinfo=timezone.utc))

    assert written == [
        "supabase/migrations/20260522000001_schema.sql",
        "supabase/migrations/20261002000029_new.sql",
    ]
    assert (repo / "supabase/migrations/20261002000029_new.sql").read_text(encoding="utf-8") == "SELECT 29;\n"
    assert check(repo, {}).findings == []
    assert fix(repo) == []  # nothing left to write


def test_main_exit_codes(repo, capsys, tmp_path):
    manifest = tmp_path / "empty.yaml"
    manifest.write_text("supabase_only: []\n", encoding="utf-8")
    assert main(["--root", str(repo), "--manifest", str(manifest)]) == 0

    (repo / "server/db/migrations/0002_more.sql").write_text("SELECT 1;\n", encoding="utf-8")
    assert main(["--root", str(repo), "--manifest", str(manifest)]) == 1
    assert "missing_twin" in capsys.readouterr().out

    assert main(["--root", str(tmp_path / "nowhere"), "--manifest", str(manifest)]) == 2


def test_the_engine_has_one_version_per_migration():
    """The real repository: every board migration has its byte-for-byte copy."""
    report = check(ENGINE_ROOT, load_manifest(DEFAULT_MANIFEST))
    assert report.findings == [], "\n".join(f"{f.kind}: {f.file} — {f.detail}" for f in report.findings)
    assert report.unused == []
    assert report.pairs >= 28
