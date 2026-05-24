"""Verify `templates/canonical_docs.json` stays in sync with `registry.py`.

UC-D005 AC-03: the Node.js hook `app-docs-sync-guard.mjs` reads the JSON
descriptor because it can't import Python. The descriptor is regenerated
from `server/app_docs/registry.py` by a build script. If a developer adds
a new CanonicalDoc to the registry without regenerating the JSON, this
test fails and CI blocks the PR.

Risk PL-04 / R-12 from the plan: merge conflicts on `canonical_docs.json`
when two PRs touch the registry. Regenerating is idempotent and trivial;
the test ensures the discipline.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / ".quality/scripts/regenerate-canonical-docs-json.py"


def test_canonical_docs_json_in_sync_with_registry():
    """`templates/canonical_docs.json` must equal `serialize(CANONICAL_DOCS)`.

    Run `python3 .quality/scripts/regenerate-canonical-docs-json.py` to
    fix any drift before re-running.
    """
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--check"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"canonical_docs.json out of sync with registry.py.\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}\n"
        f"Fix: python3 {SCRIPT.relative_to(REPO_ROOT)}"
    )


def test_canonical_docs_json_schema_is_v1():
    """Descriptor schema_version field is present and equal to 1.

    Bumping this version is a breaking change for the hook reader and
    must be coordinated with `.claude/hooks/app-docs-sync-guard.mjs`.
    """
    import json

    target = REPO_ROOT / "templates" / "canonical_docs.json"
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1, (
        "schema_version changed from 1 — also update the Node.js hook reader."
    )
    assert "docs" in data
    assert isinstance(data["docs"], list)
    for d in data["docs"]:
        assert {"id", "path", "introduced_in", "template_path"}.issubset(d.keys())


def test_app_market_entry_present():
    """v6.0: registry includes `app_market` with introduced_in=6.0.0."""
    import json

    target = REPO_ROOT / "templates" / "canonical_docs.json"
    data = json.loads(target.read_text(encoding="utf-8"))
    ids = {d["id"]: d for d in data["docs"]}
    assert "app_market" in ids, "app_market missing from canonical docs (v6.0 regression)"
    assert ids["app_market"]["introduced_in"] == "6.0.0"
    assert ids["app_market"]["path"] == "doc/app/app_market.md"
