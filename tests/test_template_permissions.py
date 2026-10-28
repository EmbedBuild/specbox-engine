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
    "Read(~/.specbox/*.json)",
    "Read(~/.specbox/credentials/**)",
    "Read(~/.specbox/backups/**)",
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


#: What SpecBox keeps in ~/.specbox that nobody should read: the credentials (macOS keeps them in the
#: Keychain, Linux in credentials.json, Windows in credentials/), the Supabase tokens and the backups.
CREDENTIAL_PATHS = [
    "~/.specbox/credentials.json",
    "~/.specbox/supabase_tokens.json",
    "~/.specbox/credentials/0a1b2c.dpapi",
    "~/.specbox/backups/claude-mcp-20261002T112028Z.json",
]

#: The managed engine clone: ~/.claude/skills links here, and /app-init reads its templates.
ENGINE_CLONE_PATHS = [
    "~/.specbox/specbox-engine/.claude/skills/design-review/SKILL.md",
    "~/.specbox/specbox-engine/templates/app_prd.md.template",
]


def _glob_regex(pattern: str) -> re.Pattern[str]:
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**", i):
            out, i = out + ".*", i + 2
        elif pattern[i] == "*":
            out, i = out + "[^/]*", i + 1
        else:
            out, i = out + re.escape(pattern[i]), i + 1
    return re.compile(out)


def _covers(pattern: str, path: str) -> bool:
    """Gitignore-style, as Claude Code applies Read/Edit rules: a rule that matches a folder covers what is inside."""
    regex = _glob_regex(pattern)
    parts = path.split("/")
    return any(regex.fullmatch("/".join(parts[:n])) for n in range(1, len(parts) + 1))


def _read_denials(path: str) -> list[str]:
    deny = _permissions(TEMPLATE.read_text(encoding="utf-8")).get("deny", [])
    return [rule for rule in deny if rule.startswith("Read(") and _covers(rule[5:-1], path)]


def test_ac01_the_template_does_not_allow_commands_or_the_web_without_asking():
    allow = _permissions(TEMPLATE.read_text(encoding="utf-8"))["allow"]
    assert not [r for r in allow if _unrestricted(r, "Bash") or _unrestricted(r, "WebFetch")], allow


def test_ac02_the_template_prohibits_credentials_env_and_downloads():
    deny = set(_permissions(TEMPLATE.read_text(encoding="utf-8")).get("deny", []))
    assert REQUIRED_DENY <= deny, sorted(REQUIRED_DENY - deny)


def test_the_credentials_in_specbox_cannot_be_read():
    assert not [p for p in CREDENTIAL_PATHS if not _read_denials(p)]


def test_uc11009_the_engine_clone_stays_readable():
    """UC-11009: 6.29.0 denied Read(~/.specbox/**) and with it every SpecBox skill (linked to the clone)."""
    assert not {p: _read_denials(p) for p in ENGINE_CLONE_PATHS if _read_denials(p)}


def test_the_path_check_catches_what_it_is_for():
    skill = ENGINE_CLONE_PATHS[0]
    assert _covers("~/.specbox/**", skill) and _covers("~/.specbox/*", skill)
    assert not _covers("~/.specbox/*.json", skill) and not _covers("~/.specbox/backups/**", skill)
    assert _covers("~/.specbox/*.json", "~/.specbox/credentials.json")
    assert not _covers("~/.specbox/*.json", "~/.specbox/specbox-engine/package.json")


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


# ── UC-11306: las tools de solo lectura del MCP de SpecBox, sin preguntar ──────────────────────
#
# Consultar el board, los planes o las skills no pide permiso en cada llamada (decisión del owner,
# 2026-10-28). Las reglas de Claude Code no admiten comodines dentro del nombre, así que la plantilla
# nombra cada tool. Lo que escribe sigue preguntando.

MCP_PREFIX = "mcp__SpecBox-MCP__"

#: Leen y no empiezan por get_/list_/read_. Una tool de lectura nueva con otro nombre se añade aquí y a
#: la plantilla.
READ_ONLY_EXTRA = {
    "whoami", "find_next_uc", "discover_skills", "estimate_from_ac", "check_audit_tools_status",
    "analyze_preflight_decisions", "detect_local_root_path", "detect_project_backend", "detect_project_stack",
    "detect_stitch_migration_case", "detect_v529_migration_case", "detect_v60_migration_case",
    "validate_ac_quality", "validate_discovery_completeness", "validate_skill_manifest", "validate_stitch_prompt",
    "verify_app_docs", "migrate_preview", "migrate_status", "build_execution_context", "aggregate_phase_outputs",
    "stitch_get_project", "stitch_get_screen", "stitch_list_projects", "stitch_list_screens",
    "stitch_list_design_systems", "stitch_fetch_screen_code", "stitch_fetch_screen_image",
    "claude_design_get_project", "claude_design_list_projects", "claude_design_status",
}

#: Escriben aunque el nombre parezca de lectura (auditoría del 2026-10-28): anotan en .quality/ del proyecto.
WRITES_DESPITE_NAME = {"detect_app_docs_drift", "app_docs_drift_for_heartbeat", "evaluate_autopilot_decision"}

#: Una tool que crea, cambia, borra, reserva, marca o informa: el verbo es el principio del nombre, tras
#: `stitch_` o `claude_design_` (en `get_delivery_report`, «report» es el nombre de lo que se lee).
WRITE_VERB = re.compile(
    r"^(stitch_|claude_design_)?(add|create|update|delete|set|mark|move|start|complete|claim|reserve|release|report|record|register"
    r"|import|upload|attach|apply|sync|upgrade|onboard|run|submit|enqueue|resolve|publish|revoke|take|write"
    r"|archive|reset|switch|declare|link|regenerate|generate|append|commit|enable|disable|setup|bulk|edit"
    r"|evaluate|migrate_(project|backend|to))(_|$)"
)


def _registered_tools() -> set[str]:
    import asyncio

    from server.server import mcp

    return {t.name for t in asyncio.run(mcp.list_tools())}


def _allowed_mcp_tools() -> set[str]:
    allow = _permissions(TEMPLATE.read_text(encoding="utf-8"))["allow"]
    return {r[len(MCP_PREFIX):] for r in allow if r.startswith(MCP_PREFIX)}


def _is_read_only(name: str) -> bool:
    return (re.match(r"(get|list|read)_", name) is not None or name in READ_ONLY_EXTRA) and name not in WRITES_DESPITE_NAME


def test_uc11306_ac01_the_template_lets_the_read_only_tools_run_without_asking():
    allowed = _allowed_mcp_tools()
    assert {"get_uc", "list_uc", "get_board_status", "read_plan"} <= allowed


def test_uc11306_ac02_no_tool_that_writes_runs_without_asking():
    registered = _registered_tools()
    allowed = _allowed_mcp_tools()
    assert not allowed - registered, sorted(allowed - registered)
    writers = sorted(t for t in allowed if WRITE_VERB.search(t) or t in WRITES_DESPITE_NAME)
    assert not writers, writers


def test_uc11306_every_read_only_tool_of_the_server_is_in_the_template():
    registered = _registered_tools()
    assert READ_ONLY_EXTRA <= registered, sorted(READ_ONLY_EXTRA - registered)
    assert _allowed_mcp_tools() == {t for t in registered if _is_read_only(t)}


def test_the_write_check_catches_what_it_is_for():
    for writer in ["add_uc", "mark_ac_batch", "report_heartbeat", "complete_uc", "set_auth_token", "migrate_project",
                   "stitch_generate_screen", "reserve_uc", "take_resolved_decisions", "evaluate_autopilot_decision"]:
        assert WRITE_VERB.search(writer), writer
    for reader in ["get_uc", "list_uc", "read_plan", "migrate_preview", "find_next_uc", "build_execution_context",
                   "stitch_list_projects", "validate_ac_quality", "get_delivery_report"]:
        assert not WRITE_VERB.search(reader), reader
