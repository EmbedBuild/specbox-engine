"""Tests for server/skill_registry.py — manifest validation, listing, deps, discovery."""

import textwrap
from pathlib import Path

import pytest
import yaml

from src.skill_registry import (
    check_dependencies,
    discover_skills_for_context,
    list_all_skills,
    validate_manifest,
)


@pytest.fixture
def fake_home(tmp_path: Path) -> Path:
    """Isolated home directory so real ~/.claude/skills/ is not scanned."""
    home = tmp_path / "fakehome"
    home.mkdir()
    return home


@pytest.fixture
def tmp_engine(tmp_path: Path) -> Path:
    """Create a minimal engine directory with core skills."""
    engine = tmp_path / "engine"
    skills_dir = engine / ".claude" / "skills"

    # Core skill: prd (no manifest — core skills don't need one)
    prd_dir = skills_dir / "prd"
    prd_dir.mkdir(parents=True)
    (prd_dir / "SKILL.md").write_text(textwrap.dedent("""\
        ---
        name: prd-generator
        description: Generate PRDs from feature descriptions.
        context: fork
        agent: Plan
        ---
        # /prd
        Content here.
    """))

    # Core skill: implement
    impl_dir = skills_dir / "implement"
    impl_dir.mkdir(parents=True)
    (impl_dir / "SKILL.md").write_text(textwrap.dedent("""\
        ---
        name: implement
        description: Execute implementation plans.
        context: direct
        ---
        # /implement
        Content here.
    """))

    return engine


@pytest.fixture
def valid_manifest_data() -> dict:
    return {
        "name": "stripe-payments",
        "version": "1.0.0",
        "author": "Test Author",
        "description": "Stripe payment integration patterns",
        "compatibility": ["flutter", "react"],
        "triggers": ["payments", "stripe", "billing"],
        "depends_on": ["plan"],
    }


@pytest.fixture
def external_skill(tmp_path: Path, valid_manifest_data: dict) -> Path:
    """Create an external skill directory with manifest."""
    skill_dir = tmp_path / "ext-skills" / "stripe-payments"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(textwrap.dedent("""\
        ---
        name: stripe-payments
        description: Stripe payment integration patterns.
        context: fork
        agent: Plan
        ---
        # Stripe Payments Skill
        Content here.
    """))
    (skill_dir / "manifest.yaml").write_text(yaml.dump(valid_manifest_data))
    return skill_dir


# -----------------------------------------------------------------------
# validate_manifest
# -----------------------------------------------------------------------


class TestValidateManifest:
    def test_valid_manifest(self, external_skill: Path):
        valid, errors = validate_manifest(external_skill / "manifest.yaml")
        assert valid is True
        assert errors == []

    def test_missing_file(self, tmp_path: Path):
        valid, errors = validate_manifest(tmp_path / "nonexistent.yaml")
        assert valid is False
        assert "manifest.yaml not found" in errors[0]

    def test_missing_required_fields(self, tmp_path: Path):
        manifest = tmp_path / "manifest.yaml"
        manifest.write_text(yaml.dump({"name": "test", "version": "1.0.0"}))
        valid, errors = validate_manifest(manifest)
        assert valid is False
        missing_fields = {e.split(": ")[1] for e in errors}
        assert "author" in missing_fields
        assert "description" in missing_fields
        assert "compatibility" in missing_fields

    def test_invalid_semver(self, tmp_path: Path):
        data = {
            "name": "test",
            "version": "not-a-version",
            "author": "A",
            "description": "D",
            "compatibility": ["flutter"],
        }
        manifest = tmp_path / "manifest.yaml"
        manifest.write_text(yaml.dump(data))
        valid, errors = validate_manifest(manifest)
        assert valid is False
        assert any("semver" in e for e in errors)

    def test_valid_semver_with_prerelease(self, tmp_path: Path):
        data = {
            "name": "test",
            "version": "1.0.0-beta.1",
            "author": "A",
            "description": "D",
            "compatibility": ["flutter"],
        }
        manifest = tmp_path / "manifest.yaml"
        manifest.write_text(yaml.dump(data))
        valid, errors = validate_manifest(manifest)
        assert valid is True

    def test_compatibility_must_be_list(self, tmp_path: Path):
        data = {
            "name": "test",
            "version": "1.0.0",
            "author": "A",
            "description": "D",
            "compatibility": "flutter",
        }
        manifest = tmp_path / "manifest.yaml"
        manifest.write_text(yaml.dump(data))
        valid, errors = validate_manifest(manifest)
        assert valid is False
        assert any("list" in e for e in errors)

    def test_triggers_must_be_list(self, tmp_path: Path):
        data = {
            "name": "test",
            "version": "1.0.0",
            "author": "A",
            "description": "D",
            "compatibility": ["flutter"],
            "triggers": "payments",
        }
        manifest = tmp_path / "manifest.yaml"
        manifest.write_text(yaml.dump(data))
        valid, errors = validate_manifest(manifest)
        assert valid is False
        assert any("triggers" in e for e in errors)

    def test_optional_fields_not_required(self, tmp_path: Path):
        """triggers and depends_on are optional."""
        data = {
            "name": "test",
            "version": "1.0.0",
            "author": "A",
            "description": "D",
            "compatibility": ["react"],
        }
        manifest = tmp_path / "manifest.yaml"
        manifest.write_text(yaml.dump(data))
        valid, errors = validate_manifest(manifest)
        assert valid is True
        assert errors == []

    def test_invalid_yaml(self, tmp_path: Path):
        manifest = tmp_path / "manifest.yaml"
        manifest.write_text(": : invalid yaml {{[")
        valid, errors = validate_manifest(manifest)
        assert valid is False


# -----------------------------------------------------------------------
# list_all_skills
# -----------------------------------------------------------------------


class TestListAllSkills:
    def test_lists_core_skills(self, tmp_engine: Path, fake_home: Path):
        skills = list_all_skills(tmp_engine, home_override=fake_home)
        names = {s["name"] for s in skills}
        assert "prd-generator" in names
        assert "implement" in names
        for s in skills:
            assert s["source"] == "core"

    def test_empty_engine(self, tmp_path: Path, fake_home: Path):
        empty = tmp_path / "empty_engine"
        empty.mkdir()
        skills = list_all_skills(empty, home_override=fake_home)
        assert skills == []

    def test_includes_project_local_skills(
        self, tmp_engine: Path, fake_home: Path, valid_manifest_data: dict
    ):
        proj = tmp_engine / "myproject"
        local_skill = proj / ".claude" / "skills" / "local-skill"
        local_skill.mkdir(parents=True)
        (local_skill / "SKILL.md").write_text("---\nname: local-skill\n---\nContent")
        manifest_data = {**valid_manifest_data, "name": "local-skill"}
        (local_skill / "manifest.yaml").write_text(yaml.dump(manifest_data))

        skills = list_all_skills(
            tmp_engine, project_path=str(proj), home_override=fake_home
        )
        sources = {s["name"]: s["source"] for s in skills}
        assert sources.get("local-skill") == "external-local"

    def test_shadow_warning_on_name_collision(
        self, tmp_engine: Path, fake_home: Path
    ):
        """If an external skill has the same dir name as a core skill, warn."""
        proj = tmp_engine / "proj"
        local_prd = proj / ".claude" / "skills" / "prd"
        local_prd.mkdir(parents=True)
        (local_prd / "SKILL.md").write_text("---\nname: prd-ext\n---\nExt")

        skills = list_all_skills(
            tmp_engine, project_path=str(proj), home_override=fake_home
        )
        shadowed = [s for s in skills if s.get("shadow_warning")]
        assert len(shadowed) == 1
        assert shadowed[0]["source"] == "external-local"

    def test_manifest_fields_included(
        self, tmp_engine: Path, fake_home: Path, valid_manifest_data: dict
    ):
        """External skills with manifest have version, author, etc."""
        proj = tmp_engine / "proj2"
        ext_skill = proj / ".claude" / "skills" / "stripe-payments"
        ext_skill.mkdir(parents=True)
        (ext_skill / "SKILL.md").write_text(
            "---\nname: stripe-payments\n---\nContent"
        )
        (ext_skill / "manifest.yaml").write_text(yaml.dump(valid_manifest_data))

        skills = list_all_skills(
            tmp_engine, project_path=str(proj), home_override=fake_home
        )
        stripe = next(s for s in skills if s["name"] == "stripe-payments")
        assert stripe["version"] == "1.0.0"
        assert stripe["author"] == "Test Author"
        assert stripe["compatibility"] == ["flutter", "react"]
        assert stripe["triggers"] == ["payments", "stripe", "billing"]


# -----------------------------------------------------------------------
# check_dependencies
# -----------------------------------------------------------------------


class TestCheckDependencies:
    def test_all_satisfied(self):
        manifest = {"depends_on": ["plan", "implement"]}
        missing = check_dependencies(manifest, ["plan", "implement", "prd"])
        assert missing == []

    def test_some_missing(self):
        manifest = {"depends_on": ["plan", "stripe-payments"]}
        missing = check_dependencies(manifest, ["plan", "implement"])
        assert missing == ["stripe-payments"]

    def test_no_depends_on(self):
        manifest = {"name": "test"}
        missing = check_dependencies(manifest, ["plan"])
        assert missing == []

    def test_empty_available(self):
        manifest = {"depends_on": ["plan"]}
        missing = check_dependencies(manifest, [])
        assert missing == ["plan"]


# -----------------------------------------------------------------------
# discover_skills_for_context
# -----------------------------------------------------------------------


class TestDiscoverSkills:
    def _setup_external(
        self, tmp_engine: Path, name: str, compat: list, triggers: list
    ) -> None:
        proj = tmp_engine / "proj"
        skill_dir = proj / ".claude" / "skills" / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(f"---\nname: {name}\n---\nContent")
        manifest = {
            "name": name,
            "version": "1.0.0",
            "author": "Test",
            "description": "Test skill",
            "compatibility": compat,
            "triggers": triggers,
        }
        (skill_dir / "manifest.yaml").write_text(yaml.dump(manifest))

    def test_matches_by_stack_and_trigger(
        self, tmp_engine: Path, fake_home: Path
    ):
        self._setup_external(
            tmp_engine,
            "stripe-skill",
            ["flutter", "react"],
            ["payments", "stripe"],
        )
        results = discover_skills_for_context(
            tmp_engine,
            str(tmp_engine / "proj"),
            stack="flutter",
            keywords=["payments"],
            home_override=fake_home,
        )
        activated = [r for r in results if r.get("activated")]
        assert len(activated) == 1
        assert activated[0]["name"] == "stripe-skill"

    def test_incompatible_stack(self, tmp_engine: Path, fake_home: Path):
        self._setup_external(tmp_engine, "react-only", ["react"], ["payments"])
        results = discover_skills_for_context(
            tmp_engine,
            str(tmp_engine / "proj"),
            stack="flutter",
            keywords=["payments"],
            home_override=fake_home,
        )
        incompatible = [r for r in results if r.get("incompatible")]
        assert len(incompatible) == 1
        assert incompatible[0]["name"] == "react-only"

    def test_no_trigger_match(self, tmp_engine: Path, fake_home: Path):
        self._setup_external(
            tmp_engine, "auth-skill", ["flutter"], ["authentication", "oauth"]
        )
        results = discover_skills_for_context(
            tmp_engine,
            str(tmp_engine / "proj"),
            stack="flutter",
            keywords=["payments"],
            home_override=fake_home,
        )
        assert len(results) == 0

    def test_core_skills_without_manifest_skipped(
        self, tmp_engine: Path, fake_home: Path
    ):
        """Core skills without manifest data are not returned by discover."""
        results = discover_skills_for_context(
            tmp_engine,
            None,
            stack="flutter",
            keywords=["prd"],
            home_override=fake_home,
        )
        assert len(results) == 0

    def test_substring_trigger_match(self, tmp_engine: Path, fake_home: Path):
        """Trigger matching works with substring containment."""
        self._setup_external(
            tmp_engine, "pay-skill", ["flutter"], ["payment-processing"]
        )
        results = discover_skills_for_context(
            tmp_engine,
            str(tmp_engine / "proj"),
            stack="flutter",
            keywords=["payment"],
            home_override=fake_home,
        )
        activated = [r for r in results if r.get("activated")]
        assert len(activated) == 1
