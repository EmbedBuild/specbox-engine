# GitHub Branch Protection — Setup Guide

> Enforcement remoto que complementa los hooks locales de Claude Code.
> Los hooks locales previenen errores del agente. Branch protection previene bypasses.
> Sin esto, `git push --force` o `git commit --no-verify` fuera de Claude Code lo saltan todo.

---

## Configuración recomendada para main/master

### Via GitHub CLI (gh)

```bash
gh api repos/{owner}/{repo}/branches/main/protection -X PUT \
  --input - <<'EOF'
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["lint", "test", "e2e-evidence"]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1,
    "dismiss_stale_reviews": true
  },
  "restrictions": null,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false
}
EOF
```

### Qué protege

| Regla | Qué previene |
|-------|-------------|
| `required_status_checks` | Merge sin CI verde (lint + tests + evidence) |
| `enforce_admins` | Ni admins pueden saltarse las reglas |
| `required_pull_request_reviews` | Merge directo sin review |
| `required_linear_history` | Merge commits que oscurecen el historial |
| `allow_force_pushes: false` | Force push que borra historial |
| `allow_deletions: false` | Borrar la branch main |

### Status checks recomendados

| Check | Fuente | Qué valida |
|-------|--------|-----------|
| `lint` | Pre-commit / GGA | Zero-tolerance lint |
| `test` | CI (pytest / flutter test / jest) | Unit + integration tests |
| `e2e-evidence` | `acceptance-gate.yml` | results.json válido + HTML report existe |

---

## GitHub Action: e2e-evidence check

```yaml
# .github/workflows/e2e-evidence-check.yml
name: E2E Evidence Check

on:
  pull_request:
    branches: [main]
    paths:
      - '.quality/evidence/**'
      - 'test/acceptance/**'
      - 'tests/acceptance/**'
      - 'e2e/**'

jobs:
  validate-evidence:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Find and validate results.json files
        run: |
          FOUND=0
          VALID=0
          INVALID=0

          for f in $(find .quality/evidence -name "results.json" -path "*/acceptance/*" 2>/dev/null); do
            FOUND=$((FOUND + 1))
            if node .quality/scripts/validate-results-json.js "$f" --check-evidence; then
              VALID=$((VALID + 1))
            else
              INVALID=$((INVALID + 1))
            fi
          done

          echo "Found: $FOUND | Valid: $VALID | Invalid: $INVALID"

          if [ "$INVALID" -gt 0 ]; then
            echo "::error::$INVALID results.json file(s) failed validation"
            exit 1
          fi

          if [ "$FOUND" -eq 0 ]; then
            echo "::warning::No results.json files found in .quality/evidence/"
          fi

      - name: Check HTML Evidence Reports exist
        run: |
          MISSING=0
          for f in $(find .quality/evidence -name "results.json" -path "*/acceptance/*" 2>/dev/null); do
            DIR=$(dirname "$f")
            if [ ! -f "$DIR/e2e-evidence-report.html" ]; then
              echo "::error::Missing HTML report alongside $f"
              MISSING=$((MISSING + 1))
            fi
          done

          if [ "$MISSING" -gt 0 ]; then
            exit 1
          fi
```

---

## Integración con SpecBox Engine

### Durante onboard_project

Cuando se onboardea un proyecto con SpecBox Engine:

1. El proyecto debe tener branch protection en main
2. `acceptance-gate.yml` debe estar en `.github/workflows/`
3. `e2e-evidence-check.yml` debe estar en `.github/workflows/`

### Verificación

```bash
# Verificar que branch protection está activa
gh api repos/{owner}/{repo}/branches/main/protection --jq '.required_status_checks'
```

---

*SpecBox Engine v5.19.0 — GitHub Branch Protection Setup*
