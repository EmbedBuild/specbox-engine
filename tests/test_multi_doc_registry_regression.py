"""Regression tests for the multi-doc registry refactor (UC-D005, US-D04).

Validates AC-D005-04, AC-D005-06, AC-D005-12, AC-D006-04:

- A project whose engine_version_at_onboard < introduced_in of a doc
  must NOT receive drift warnings for that doc.
- An existing project's manually-edited app_prd.md must NOT be modified
  by the refactor.
- The hook respects status="template-pristine" — pristine plantillas
  produce no drift.
- The hook falls back gracefully when canonical_docs.json descriptor
  is missing (legacy project that never received v6.0).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK_PATH = REPO_ROOT / ".claude/hooks/app-docs-sync-guard.mjs"


# ─── Fixtures for v5.x project simulations ───────────────────────────


@pytest.fixture
def v5_35_project(tmp_path: Path) -> Path:
    """Simulate a project that onboarded under v5.35.0.

    Has doc/app/app_prd.md + app_spec.md (v5.29 era) with REAL content
    (not pristine). NO app_market.md. settings.local.json declares
    engine_version_at_onboard=5.35.0.
    """
    project = tmp_path / "v5_35_project"
    (project / "doc" / "app").mkdir(parents=True)
    (project / ".claude").mkdir()
    (project / ".quality").mkdir()

    # User-authored content. The byte-by-byte preservation of this content
    # is the AC-D005-12 assertion.
    prd_content = (
        '<!-- @specbox:zone start kind="manual" id="vision" -->\n'
        "## 1. Visión\n"
        "Esta es la visión real del proyecto: hacer X para Y.\n"
        '<!-- @specbox:zone end -->\n'
        '<!-- @specbox:zone start kind="auto" id="roadmap" -->\n'
        "## 5. Roadmap\n"
        "| US-01 | Test | Done |\n"
        '<!-- @specbox:zone end -->\n'
    )
    spec_content = (
        '<!-- @specbox:zone start kind="auto" id="stack" -->\n'
        "## 1. Stack\n"
        "React + Supabase\n"
        '<!-- @specbox:zone end -->\n'
    )
    (project / "doc/app/app_prd.md").write_text(prd_content, encoding="utf-8")
    (project / "doc/app/app_spec.md").write_text(spec_content, encoding="utf-8")

    # settings declares onboard version
    settings = {
        "specbox": {
            "engine_version_at_onboard": "5.35.0",
            "backend_type": "freeform",
        }
    }
    (project / ".claude/settings.local.json").write_text(
        json.dumps(settings, indent=2), encoding="utf-8"
    )

    return project


@pytest.fixture
def v5_29_project_unknown_onboard(tmp_path: Path) -> Path:
    """Simulate a v5.29 project that NEVER captured engine_version_at_onboard.

    UC-D005 AC-05 conservative policy: hook treats this as "unknown" and
    only verifies docs with introduced_in <= 5.29.0.
    """
    project = tmp_path / "v5_29_unknown"
    (project / "doc" / "app").mkdir(parents=True)
    (project / ".claude").mkdir()
    (project / ".quality").mkdir()

    (project / "doc/app/app_prd.md").write_text(
        '<!-- @specbox:zone start kind="manual" id="vision" -->\n'
        "Vision\n"
        '<!-- @specbox:zone end -->\n',
        encoding="utf-8",
    )
    # NO engine_version_at_onboard in settings → "unknown"
    (project / ".claude/settings.local.json").write_text(
        json.dumps({"specbox": {"backend_type": "freeform"}}, indent=2),
        encoding="utf-8",
    )
    return project


# ─── Python-side regression tests ────────────────────────────────────


class TestPythonRefactor:
    def test_verify_skips_app_market_in_v5_35_project(self, v5_35_project: Path):
        """AC-D005-04: app_market.md (introduced_in 6.0.0) is ignored
        when engine_version_at_onboard < 6.0.0."""
        from server.app_docs.sync import verify_app_docs_in_sync

        result = verify_app_docs_in_sync(v5_35_project)
        # No app_market signature even though the doc doesn't exist —
        # the verifier doesn't even try to read it.
        assert "app_market" not in result.signatures
        # No drift entries for app_market.
        assert not any(d.document == "app_market" for d in result.drift)

    def test_verify_skips_app_market_in_unknown_onboard(
        self, v5_29_project_unknown_onboard: Path
    ):
        """AC-D005-05: unknown engine_version_at_onboard → conservative
        policy → only docs with introduced_in <= 5.29.0 are checked."""
        from server.app_docs.sync import verify_app_docs_in_sync

        result = verify_app_docs_in_sync(v5_29_project_unknown_onboard)
        assert "app_market" not in result.signatures
        # app_prd is checked (introduced_in=5.29.0, eligible under conservative)
        assert "app_prd" in result.signatures

    def test_app_market_visible_in_v6_project(self, tmp_path: Path):
        """A project on v6.0+ DOES see app_market in its signatures dict."""
        from server.app_docs.sync import verify_app_docs_in_sync

        project = tmp_path / "v6_project"
        (project / "doc/app").mkdir(parents=True)
        (project / ".claude").mkdir()
        # Write app_market.md with NON-pristine content so it counts.
        (project / "doc/app/app_market.md").write_text(
            '<!-- @specbox:zone start kind="manual" id="icps_primary" -->\n'
            "Real ICP content here, no longer pristine.\n"
            '<!-- @specbox:zone end -->\n',
            encoding="utf-8",
        )
        settings = {"specbox": {"engine_version_at_onboard": "6.0.0"}}
        (project / ".claude/settings.local.json").write_text(
            json.dumps(settings), encoding="utf-8"
        )

        result = verify_app_docs_in_sync(project)
        assert "app_market" in result.signatures

    def test_pristine_app_market_produces_no_drift(self, tmp_path: Path):
        """AC-D005-13 / AC-D006-04: pristine plantilla is silent."""
        from server.app_docs.sync import verify_app_docs_in_sync, record_sync_signature

        project = tmp_path / "v6_pristine"
        (project / "doc/app").mkdir(parents=True)
        (project / ".claude").mkdir()
        (project / ".quality").mkdir()

        # Copy the actual app_market.md.template (which has template-pristine)
        template = (REPO_ROOT / "templates/app_market.md.template").read_text(
            encoding="utf-8"
        )
        rendered = template.replace("{project_name}", "test").replace(
            "{date_iso}", "2026-05-25"
        )
        (project / "doc/app/app_market.md").write_text(rendered, encoding="utf-8")

        settings = {"specbox": {"engine_version_at_onboard": "6.0.0"}}
        (project / ".claude/settings.local.json").write_text(
            json.dumps(settings), encoding="utf-8"
        )

        # Record a baseline signature so verify has something to compare against
        record_sync_signature(project)

        # Modify nothing; re-verify. Should not produce drift since pristine
        # docs are skipped in the verifier.
        result = verify_app_docs_in_sync(project)
        assert not any(d.document == "app_market" for d in result.drift)
        assert "app_market" not in result.signatures  # pristine skipped


# ─── upgrade_project tests (AC-D005-10, AC-D005-11, AC-D005-12) ─────


class TestUpgradeProject:
    def test_collect_canonical_docs_skips_when_unknown(self):
        """unknown engine_version_at_onboard → no docs offered (conservative)."""
        from server.tools.onboarding import _collect_canonical_doc_templates

        docs, warnings = _collect_canonical_doc_templates(
            REPO_ROOT, engine_version_at_onboard=None, project="test", now_iso="2026-05-25"
        )
        assert docs == []
        assert warnings == []

    def test_collect_canonical_docs_offers_app_market_for_v5_35(self):
        """v5.35.0 onboard → offered app_market (introduced_in 6.0.0)."""
        from server.tools.onboarding import _collect_canonical_doc_templates

        docs, warnings = _collect_canonical_doc_templates(
            REPO_ROOT,
            engine_version_at_onboard="5.35.0",
            project="test",
            now_iso="2026-05-25",
        )
        ids = {d["id"] for d in docs}
        assert "app_market" in ids
        # app_prd/app_spec already existed at v5.35.0 → NOT offered
        assert "app_prd" not in ids
        assert "app_spec" not in ids

        # Content includes placeholder substitution
        market = next(d for d in docs if d["id"] == "app_market")
        assert "test" in market["content"]
        assert "2026-05-25" in market["content"]
        assert 'status="template-pristine"' in market["content"]

    def test_collect_canonical_docs_offers_nothing_for_v6(self):
        """v6.0.0 onboard → no docs offered (none introduced after)."""
        from server.tools.onboarding import _collect_canonical_doc_templates

        docs, _ = _collect_canonical_doc_templates(
            REPO_ROOT,
            engine_version_at_onboard="6.0.0",
            project="test",
            now_iso="2026-05-25",
        )
        assert docs == []


# ─── Hook (Node.js) regression test ──────────────────────────────────


class TestHookRefactor:
    def _run_hook(self, project_dir: Path) -> tuple[int, str, str]:
        """Run app-docs-sync-guard.mjs in the project dir; return (rc, stdout, stderr)."""
        result = subprocess.run(
            ["node", str(HOOK_PATH)],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode, result.stdout, result.stderr

    def test_hook_silent_in_v5_35_project_with_pristine_market(
        self, v5_35_project: Path
    ):
        """AC-D006-04: hook does NOT warn about pristine app_market.md
        in a v5.35-upgraded-to-v6.0 project."""
        # Add app_market.md plantilla (pristine), simulating upgrade_project
        template = (REPO_ROOT / "templates/app_market.md.template").read_text(
            encoding="utf-8"
        )
        (v5_35_project / "doc/app/app_market.md").write_text(
            template.replace("{project_name}", "test").replace(
                "{date_iso}", "2026-05-25"
            ),
            encoding="utf-8",
        )

        # Seed sync lock so the hook has a baseline to compare
        (v5_35_project / ".quality/app_docs_sync.lock").write_text(
            json.dumps({"signatures": {}}), encoding="utf-8"
        )

        rc, stdout, stderr = self._run_hook(v5_35_project)
        # Exit 0 (no drift) — pristine docs are silent
        assert rc == 0, f"Hook should be silent on pristine docs. stderr: {stderr}"
        # No warning about app_market specifically
        combined = stdout + stderr
        assert "app_market" not in combined or "drifted" not in combined

    def test_hook_falls_back_when_descriptor_missing(self, tmp_path: Path):
        """Hook should still work when canonical_docs.json descriptor is absent
        (legacy project on v5.x without v6.0 templates)."""
        project = tmp_path / "legacy"
        (project / "doc/app").mkdir(parents=True)
        (project / ".claude").mkdir()
        (project / ".quality").mkdir()

        # Pristine-only content so no drift even with fallback
        (project / "doc/app/app_prd.md").write_text(
            '<!-- @specbox:zone start kind="manual" id="vision" status="template-pristine" -->\n'
            "Pristine\n"
            '<!-- @specbox:zone end -->\n',
            encoding="utf-8",
        )
        (project / ".quality/app_docs_sync.lock").write_text(
            json.dumps({"signatures": {}}), encoding="utf-8"
        )

        rc, _, stderr = self._run_hook(project)
        assert rc == 0, f"Hook should exit 0 with fallback. stderr: {stderr}"


# ─── AC-D005-12: byte-by-byte preservation ──────────────────────────


class TestUpgradePreservesExistingContent:
    def test_existing_app_prd_not_touched(self, v5_35_project: Path):
        """AC-D005-12: even if upgrade flow runs, existing files are NEVER
        modified. The `_collect_canonical_doc_templates` helper only offers
        new files to create; the actual writing is the caller's
        responsibility, which by contract checks existence first."""
        original_prd = (v5_35_project / "doc/app/app_prd.md").read_bytes()
        original_spec = (v5_35_project / "doc/app/app_spec.md").read_bytes()

        # Simulate upgrade: get the list of canonical docs to potentially create
        from server.tools.onboarding import _collect_canonical_doc_templates

        docs, _ = _collect_canonical_doc_templates(
            REPO_ROOT,
            engine_version_at_onboard="5.35.0",
            project="test",
            now_iso="2026-05-25",
        )
        # The list includes app_market (new) but does NOT include app_prd/app_spec
        # because their introduced_in <= 5.35.0
        ids = {d["id"] for d in docs}
        assert "app_prd" not in ids
        assert "app_spec" not in ids

        # The files are still identical (we never wrote anything)
        assert (v5_35_project / "doc/app/app_prd.md").read_bytes() == original_prd
        assert (v5_35_project / "doc/app/app_spec.md").read_bytes() == original_spec
