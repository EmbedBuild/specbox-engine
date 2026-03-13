# US-03: Registry de Skills Contribuidos — Implementation Plan

## Use Cases

### UC-007: Estructura de skill externo con manifiesto
- External skill = directory with SKILL.md + manifest.yaml + optional support files
- manifest.yaml required fields: name, version (semver), author, description, compatibility
- Optional fields: triggers, depends_on
- Directory pattern: ~/.claude/skills/{name}/ (global) or .claude/skills/{name}/ (project)
- Core skills have priority over external with same name + shadow_warning

### UC-008: Comando de instalacion y listado
- install.sh --skill <path|git-url> copies to ~/.claude/skills/ (or --local for .claude/skills/)
- install.sh --remove-skill <name> uninstalls external only (refuses core)
- Validates manifest.yaml required fields, fails if missing
- depends_on check warns but doesn't block

### UC-009: Auto-discovery en pipeline
- discover_skills_for_context scans all skills matching stack + keyword triggers
- Incompatible stack skills returned separately for logging
- Core skills without manifest are skipped in discovery

## Files Created/Modified

| File | Action | Purpose |
|------|--------|---------|
| server/skill_registry.py | Created | Core module: validate_manifest, list_all_skills, check_dependencies, discover_skills_for_context |
| server/tools/skill_registry.py | Created | MCP tools: list_skills_v2, discover_skills, validate_skill_manifest |
| server/server.py | Modified | Register skill_registry tools |
| install.sh | Modified | --skill, --local, --remove-skill flags with manifest validation |
| templates/skill-manifest.yaml.template | Created | Template for external skill authors |
| tests/test_skill_registry.py | Created | 23 tests covering all functions |

## Architecture Decisions

1. **home_override parameter**: list_all_skills and discover_skills_for_context accept optional home_override for test isolation
2. **Three source types**: core, external (global ~/.claude/skills/), external-local (project .claude/skills/)
3. **Symlink detection**: Global skills that are symlinks into the engine are classified as core, not external
4. **Shadow warning**: External skills with same directory name as core get shadow_warning=True
5. **list_skills_v2**: New tool name to avoid breaking existing list_skills in tools/skills.py
