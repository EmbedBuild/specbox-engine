"""The project template asks before running commands or opening the web — US-108 · UC-10808.

Audit of 2026-10-27 (ENG-D-03): ``templates/settings.json.template`` allowed ``Bash`` and
``WebFetch(domain:*)`` without asking, and ``onboard_project`` / ``upgrade_project`` wrote it to
the versioned ``.claude/settings.json`` of every project, so a prompt injection could run any
command. The owner chose option A: ask by default, prohibit the credentials, and leave the mode
without questions to each machine's ``.claude/settings.local.json`` (doc/guides/permisos.md).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from server.tools.onboarding import _generate_onboarding_files

ENGINE = Path(__file__).resolve().parent.parent
TEMPLATE = ENGINE / "templates" / "settings.json.template"

REQUIRED_DENY = {
    "Read(~/.ssh/**)",
    "Edit(~/.ssh/**)",
    "Read(~/.specbox/**)",
    "Edit(~/.specbox/**)",
    "Read(./.env)",
    "Read(./.env.*)",
    "Bash(curl:*)",
    "Bash(wget:*)",
}


def _permissions(settings_text: str) -> dict:
    return json.loads(settings_text)["permissions"]


def _unrestricted(rule: str, tool: str) -> bool:
    """``Bash``, ``Bash(*)`` or ``Bash(*:*)`` — the tool with no real limit."""
    return re.fullmatch(rf"{tool}(\((\*|\*:\*|domain:\*)\))?", rule) is not None


def test_ac01_the_template_does_not_allow_commands_or_the_web_without_asking():
    allow = _permissions(TEMPLATE.read_text(encoding="utf-8"))["allow"]
    assert not [r for r in allow if _unrestricted(r, "Bash") or _unrestricted(r, "WebFetch")], allow


def test_ac02_the_template_prohibits_credentials_env_and_downloads():
    deny = set(_permissions(TEMPLATE.read_text(encoding="utf-8")).get("deny", []))
    assert REQUIRED_DENY <= deny, sorted(REQUIRED_DENY - deny)


def test_onboard_and_upgrade_write_the_template_permissions():
    files, _, _ = _generate_onboarding_files(ENGINE, "demo", "python", [], "dev")
    assert _permissions(files[".claude/settings.json"]) == _permissions(TEMPLATE.read_text(encoding="utf-8"))


def test_ac03_upgrade_project_never_writes_settings_local():
    """The mode without questions lives in settings.local.json; an upgrade must not overwrite it."""
    source = (ENGINE / "server" / "tools" / "onboarding.py").read_text(encoding="utf-8")
    start = source.index("def _upgrade_project_impl(")
    end = source.index("\n    def ", start + 1)
    writes_local = re.search(r"""files\[\s*["']\.claude/settings\.local\.json["']\s*\]\s*=""", source[start:end])
    assert writes_local is None
    # and the check sees a write when there is one
    assert re.search(r"""files\[\s*["']\.claude/settings\.local\.json["']\s*\]\s*=""", source[:start])


def test_the_rule_check_catches_what_it_is_for():
    assert _unrestricted("Bash", "Bash") and _unrestricted("Bash(*)", "Bash") and _unrestricted("Bash(*:*)", "Bash")
    assert _unrestricted("WebFetch(domain:*)", "WebFetch") and _unrestricted("WebFetch", "WebFetch")
    assert not _unrestricted("Bash(npm test:*)", "Bash") and not _unrestricted("WebFetch(domain:docs.github.com)", "WebFetch")
