# Plan: US-04 BDD como Modulo Exportable

## Overview

Export the BDD acceptance testing pipeline (AG-09a/b) as a standalone module that can validate acceptance criteria from a PRD against any codebase, without requiring the full /implement pipeline.

## Use Cases

### UC-010: Skill /acceptance-check standalone
- New Skill at `.claude/skills/acceptance-check/SKILL.md`
- Accepts UC-id, US-id, or PR reference
- Locates PRD automatically, extracts AC
- Generates Gherkin .feature files in `.quality/acceptance-check/{uc-id}/`
- Produces verdict (ACCEPTED/CONDITIONAL/REJECTED) with evidence
- Outputs PR-comment-ready Markdown

### UC-011: MCP Tools para acceptance check remoto
- New tool module at `server/tools/acceptance.py`
- `run_acceptance_check(project_path, item_id, branch)` — full check pipeline
- `get_acceptance_report(project_path, uc_id)` — retrieve last report
- Logs executions to `.quality/logs/acceptance-check.jsonl`
- Registered in `server/server.py`

### UC-012: GitHub Action template
- Template at `templates/github-actions/acceptance-gate.yml`
- Detects affected UCs from PR changed files
- Supports local and remote MCP execution modes
- Posts results as PR comment
- Configurable: `SDD_ENGINE_URL`, `SDD_PROJECT_PATH`, `SDD_FAIL_ON_CONDITIONAL`

## Files Created

| File | Purpose |
|------|---------|
| `.claude/skills/acceptance-check/SKILL.md` | Agent Skill definition |
| `server/tools/acceptance.py` | MCP tools (run_acceptance_check, get_acceptance_report) |
| `templates/github-actions/acceptance-gate.yml` | GitHub Action workflow template |
| `tests/test_acceptance_check.py` | 21 tests covering all AC |
| `doc/plans/us04_bdd_exportable_plan.md` | This plan |

## Files Modified

| File | Change |
|------|--------|
| `server/server.py` | Import + register acceptance tools |

## AC Coverage

| AC | Description | Implementation |
|----|-------------|----------------|
| AC-44 | Accepts UC-id, US-id, or PR reference | `run_acceptance_check` item_id parsing |
| AC-45 | Locates PRD automatically, extracts AC | `_find_prd_files` + `_extract_ac_from_prd` |
| AC-46 | .feature files generated | `_generate_gherkin` + output to .quality/acceptance-check/ |
| AC-47 | Verdict with evidence per AC | `_determine_verdict` + `_search_evidence` |
| AC-48 | PR-comment-ready Markdown | report.md generation in run_acceptance_check |
| AC-49 | PR git diff focus | `_get_pr_changed_files` + branch parameter |
| AC-50 | run_acceptance_check tool | Registered MCP tool |
| AC-51 | get_acceptance_report tool | Registered MCP tool |
| AC-52 | Logs execution | `_log_execution` to .quality/logs/ |
| AC-53 | Descriptive error if no AC | Error dict with hint message |
| AC-54 | GitHub Action template | templates/github-actions/acceptance-gate.yml |
| AC-55 | Action determines affected UCs | detect-ucs step with git diff + grep |
| AC-56 | REJECTED = exit 1 | "Fail if REJECTED" step |
| AC-57 | Configurable env vars | SDD_ENGINE_URL, SDD_PROJECT_PATH, SDD_FAIL_ON_CONDITIONAL |
| AC-58 | Template in templates/github-actions/ | File location confirmed |

## Test Results

21/21 tests passing. Coverage of all AC for UC-010 and UC-011.
