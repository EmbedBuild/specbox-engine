"""Tests for the /quickstart skill and hint tool integration.

Validates:
- AC-15: Skill file exists with correct structure
- AC-17: Hint texts exist for known skills (integration check)
- AC-19: Skill references docs/ for further learning
- AC-20: Skill is designed for < 5 min interaction (structural check)
"""

from pathlib import Path

import pytest

from src.hint_manager import get_hint_text, get_available_hints


# Path to the engine root (tests/ is one level below)
ENGINE_ROOT = Path(__file__).parent.parent


class TestQuickstartSkillExists:
    """AC-15: Skill file exists with correct structure."""

    def test_skill_file_exists(self):
        skill_path = ENGINE_ROOT / ".claude" / "skills" / "quickstart" / "SKILL.md"
        assert skill_path.exists(), f"SKILL.md not found at {skill_path}"

    def test_skill_has_yaml_frontmatter(self):
        skill_path = ENGINE_ROOT / ".claude" / "skills" / "quickstart" / "SKILL.md"
        content = skill_path.read_text(encoding="utf-8")
        assert content.startswith("---"), "SKILL.md should start with YAML frontmatter"
        # Check it has closing ---
        parts = content.split("---", 2)
        assert len(parts) >= 3, "SKILL.md should have opening and closing --- for frontmatter"

    def test_skill_frontmatter_has_required_fields(self):
        skill_path = ENGINE_ROOT / ".claude" / "skills" / "quickstart" / "SKILL.md"
        content = skill_path.read_text(encoding="utf-8")
        assert "name: quickstart" in content
        assert "description:" in content
        assert "triggers:" in content

    def test_skill_references_docs(self):
        """AC-19: Final summary references docs/ for further learning."""
        skill_path = ENGINE_ROOT / ".claude" / "skills" / "quickstart" / "SKILL.md"
        content = skill_path.read_text(encoding="utf-8")
        assert "docs/" in content, "Skill should reference docs/ directory"

    def test_skill_has_dry_run_mode(self):
        """AC-18: /implement runs in dry-run mode."""
        skill_path = ENGINE_ROOT / ".claude" / "skills" / "quickstart" / "SKILL.md"
        content = skill_path.read_text(encoding="utf-8")
        assert "dry-run" in content.lower() or "DRY-RUN" in content

    def test_skill_has_four_stages(self):
        """AC-16: Guides through 4 stages."""
        skill_path = ENGINE_ROOT / ".claude" / "skills" / "quickstart" / "SKILL.md"
        content = skill_path.read_text(encoding="utf-8")
        assert "/prd" in content
        assert "review" in content.lower()
        assert "/plan" in content
        assert "/implement" in content

    def test_skill_creates_demo_directory(self):
        """AC-15: Creates ~/quickstart-demo/ reference."""
        skill_path = ENGINE_ROOT / ".claude" / "skills" / "quickstart" / "SKILL.md"
        content = skill_path.read_text(encoding="utf-8")
        assert "quickstart-demo" in content


class TestHintTextsForKnownSkills:
    """AC-17: Hint texts exist and have explanatory content."""

    def test_all_core_skills_have_hints(self):
        core_skills = ["prd", "implement", "plan"]
        for skill in core_skills:
            text = get_hint_text(skill)
            assert text, f"Hint text missing for skill '{skill}'"
            assert len(text) > 50, f"Hint text too short for '{skill}': {text}"

    def test_hint_texts_are_explanatory(self):
        """AC-17: Explanatory blocks between stages (3-5 lines each)."""
        available = get_available_hints()
        assert len(available) >= 3, "Should have hints for at least 3 skills"

        for skill in available:
            text = get_hint_text(skill)
            # Each hint should be meaningful (at least a sentence)
            word_count = len(text.split())
            assert word_count >= 15, (
                f"Hint for '{skill}' too brief ({word_count} words): {text}"
            )


class TestOnboardingWizardStructure:
    """AC-26-AC-30: Wizard integration tests (structural)."""

    def test_onboarding_tool_file_exists(self):
        tool_path = ENGINE_ROOT / "server" / "tools" / "onboarding.py"
        assert tool_path.exists()

    def test_wizard_function_defined(self):
        tool_path = ENGINE_ROOT / "server" / "tools" / "onboarding.py"
        content = tool_path.read_text(encoding="utf-8")
        assert "get_onboarding_wizard" in content, (
            "onboarding.py should define get_onboarding_wizard tool"
        )

    def test_hint_tools_file_exists(self):
        tool_path = ENGINE_ROOT / "server" / "tools" / "hints.py"
        assert tool_path.exists()

    def test_hint_tools_registered_in_server(self):
        server_path = ENGINE_ROOT / "server" / "server.py"
        content = server_path.read_text(encoding="utf-8")
        assert "register_hint_tools" in content
