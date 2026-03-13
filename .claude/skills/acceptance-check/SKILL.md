---
name: acceptance-check
description: "Standalone acceptance check — validates AC from PRD against code without full /implement pipeline"
triggers: ["acceptance check", "check acceptance", "validate AC", "verify acceptance", "acceptance gate"]
context: fork
mode: direct
tools: ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "Agent"]
---

# /acceptance-check (Standalone BDD Acceptance Gate)

Validates acceptance criteria from a PRD against the current codebase without requiring the full /implement pipeline. Designed for PR reviews, external contributions, and standalone verification.

## Usage

```
/acceptance-check UC-001
/acceptance-check US-01
/acceptance-check --pr 42
```

**Modes:**
- `UC-XXX` — Check a specific Use Case
- `US-XX` — Check all UCs under a User Story
- `--pr N` — Check PR, auto-detect affected UCs from changed files

---

## Paso 0: Parse Input and Detect Context

### 0.1 Determine item type

```
Input received?
├── UC-XXX → item_type = "uc", item_id = "UC-XXX"
├── US-XX  → item_type = "us", item_id = "US-XX"
├── --pr N → item_type = "pr", pr_number = N
└── nothing → ERROR: "Provide a UC-id, US-id, or --pr NUMBER"
```

### 0.2 Detect project root

```bash
# Find project root (where CLAUDE.md or pubspec.yaml or package.json lives)
pwd
```

### 0.3 Get current branch and commit

```bash
git branch --show-current
git rev-parse --short HEAD
```

---

## Paso 1: Locate PRD and Extract AC

### 1.1 Find PRD file

Search in order:
```
doc/prd/*.md
doc/prds/*.md
*.prd.md
PRD*.md
```

```bash
find doc/prd doc/prds -name "*.md" -type f 2>/dev/null
find . -maxdepth 2 -name "*.prd.md" -o -name "PRD*.md" 2>/dev/null
```

### 1.2 Extract AC for the item

For **UC-XXX**: Find the section `### UC-XXX:` in the PRD, extract all `- AC-XX:` lines.

For **US-XX**: Find `### US-XX:` section, identify all UC-XXX under it, then extract AC for each UC.

For **--pr N**: Use git diff to find changed files, then match them to UCs via plan files in `doc/plans/`.

```bash
# For PR mode: get changed files
git diff main...HEAD --name-only
```

### 1.3 Validate AC found

```
AC found?
├── Yes → Continue with list of AC-XX items
└── No  → ERROR: "No acceptance criteria found for {item_id}. Ensure PRD exists with AC-XX definitions."
```

Report to user:
```
Found N acceptance criteria for {item_id}:
  AC-XX: [description]
  AC-YY: [description]
  ...
```

---

## Paso 2: Generate Gherkin .feature Files

### 2.1 Create output directory

```bash
mkdir -p .quality/acceptance-check/{uc_id}/
```

### 2.2 Generate .feature file for each AC

For each AC-XX, generate a Gherkin feature file:

```gherkin
# language: es
@acceptance @{uc_id} @{ac_id}
Caracteristica: {ac_description}

  Como validacion automatica del criterio {ac_id}
  Necesito verificar que el codigo cumple: {ac_description}

  Escenario: {ac_description}
    Dado que el sistema esta en estado inicial
    Cuando se ejecuta la funcionalidad descrita en {ac_id}
    Entonces {ac_expected_result}
```

Adapt the scenario steps based on the AC description — use the PRD context to make them specific and meaningful.

Save to: `.quality/acceptance-check/{uc_id}/{ac_id}.feature`

### 2.3 Generate index file

Create `.quality/acceptance-check/{uc_id}/README.md` listing all generated features.

---

## Paso 3: Validate AC Against Code

### 3.1 For each AC, check implementation evidence

Use Grep and Glob to search the codebase for evidence that each AC is implemented:

1. **Search for AC references**: `grep -r "AC-XX" --include="*.dart" --include="*.ts" --include="*.py" --include="*.tsx" --include="*.jsx"`
2. **Search for keywords from AC description**: Extract key terms and search
3. **Check test files**: Look for tests that exercise the AC behavior
4. **Check for existing acceptance evidence**: `.quality/evidence/*/acceptance-*.json`

### 3.2 Determine verdict per AC

For each AC-XX:
```
Evidence found?
├── Code + Tests exist      → ACCEPTED
├── Code exists, no tests   → CONDITIONAL (reason: "Missing test coverage")
├── Partial implementation   → CONDITIONAL (reason: "Partial implementation detected")
├── No evidence found       → REJECTED (reason: "No implementation evidence found")
└── Cannot determine        → CONDITIONAL (reason: "Manual verification needed")
```

### 3.3 Determine overall verdict

```
All AC ACCEPTED?           → Overall: ACCEPTED
Any AC REJECTED?           → Overall: REJECTED
Some CONDITIONAL, no REJECTED? → Overall: CONDITIONAL
```

---

## Paso 4: Generate Report

### 4.1 Save JSON report

File: `.quality/acceptance-check/{uc_id}/report.json`

```json
{
  "uc_id": "UC-XXX",
  "timestamp": "ISO-8601",
  "branch": "feature/xxx",
  "commit": "abc1234",
  "verdict": "ACCEPTED|CONDITIONAL|REJECTED",
  "criteria": [
    {
      "ac_id": "AC-XX",
      "description": "...",
      "verdict": "ACCEPTED|CONDITIONAL|REJECTED",
      "reason": "...",
      "evidence": ["file1.py:42", "test_file.py:15"]
    }
  ],
  "features_generated": [
    ".quality/acceptance-check/UC-XXX/AC-XX.feature"
  ]
}
```

### 4.2 Save Markdown report (PR-comment-ready)

File: `.quality/acceptance-check/{uc_id}/report.md`

Format:
```markdown
## Acceptance Check: {uc_id}

**Branch**: {branch}
**Commit**: {commit}
**Date**: {timestamp}
**Verdict**: {verdict_emoji} **{verdict}**

### Criteria Results

| AC | Description | Verdict | Evidence |
|----|-------------|---------|----------|
| AC-XX | ... | ACCEPTED | `file.py:42` |
| AC-YY | ... | REJECTED | No evidence |

### Details

#### AC-XX: {description}
**Verdict**: ACCEPTED
**Evidence**:
- Implementation: `src/feature.py:42-58`
- Test: `tests/test_feature.py:15`

#### AC-YY: {description}
**Verdict**: REJECTED
**Reason**: No implementation evidence found

---
*Generated by SpecBox Engine `/acceptance-check`*
```

### 4.3 Log execution

Append to `.quality/logs/acceptance-check.jsonl`:
```json
{"timestamp": "ISO", "uc_id": "UC-XXX", "verdict": "ACCEPTED", "branch": "...", "commit": "..."}
```

---

## Paso 5: PR-Focused Mode (--pr N)

When invoked with `--pr N`:

### 5.1 Get changed files from PR

```bash
git diff main...HEAD --name-only
```

### 5.2 Match files to UCs

Search plan files for file references:
```bash
grep -l "changed_file" doc/plans/*.md
```

Extract UC-XXX references from matched plans.

### 5.3 Filter AC to relevant ones

Only validate AC that relate to modified code areas. Skip AC for untouched code.

### 5.4 Enhanced evidence check

Use `git diff main...HEAD` to verify that relevant code changes exist for each AC.

---

## Output Final

```
## Acceptance Check Complete

**Item**: {item_id}
**Verdict**: {verdict_emoji} {verdict}
**Criteria**: {passed}/{total} passed

### Summary
| AC | Verdict | Details |
|----|---------|---------|
| AC-XX | ACCEPTED | Implementation + tests found |
| AC-YY | REJECTED | No evidence |

### Files Generated
- .quality/acceptance-check/{uc_id}/report.json
- .quality/acceptance-check/{uc_id}/report.md
- .quality/acceptance-check/{uc_id}/AC-XX.feature
- .quality/acceptance-check/{uc_id}/AC-YY.feature

### PR Comment
The Markdown report is ready to paste as a PR comment:
`.quality/acceptance-check/{uc_id}/report.md`
```

---

## Checklist

- [ ] Input parsed (UC-id, US-id, or PR reference)
- [ ] PRD located and AC extracted
- [ ] Gherkin .feature files generated in .quality/acceptance-check/{uc_id}/
- [ ] Each AC validated against codebase
- [ ] Verdict determined per AC and overall
- [ ] JSON report saved
- [ ] Markdown report saved (PR-comment-ready)
- [ ] Execution logged to .quality/logs/
- [ ] If PR mode: git diff used to focus validation
