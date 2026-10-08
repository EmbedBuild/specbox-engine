# GitHub Branch Protection — Setup Guide

> Enforcement remoto que complementa los hooks locales de Claude Code.
> Los hooks locales previenen errores del agente. Branch protection previene bypasses.
> Sin esto, `git push --force` o `git commit --no-verify` fuera de Claude Code lo saltan todo.
>
> **La CI de GitHub no corre en cada PR.** Las pruebas se pasan en local antes de la PR (hooks,
> `/quality-gate`, `/acceptance-check`); la CI de GitHub se lanza a mano (`workflow_dispatch`) al
> cerrar un bloque grande. Por eso la protección no exige status checks: un check que solo se lanza
> a mano nunca llega a una PR y la dejaría bloqueada. En un repo privado, cada ejecución gasta
> minutos del plan de GitHub.

---

## Configuración recomendada para main/master

### Via GitHub CLI (gh)

```bash
gh api repos/{owner}/{repo}/branches/main/protection -X PUT \
  --input - <<'EOF'
{
  "required_status_checks": null,
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
| `required_status_checks: null` | Nada: ningún check obligatorio, porque la CI se lanza a mano (ver arriba) |
| `enforce_admins` | Ni admins pueden saltarse las reglas |
| `required_pull_request_reviews` | Merge directo sin review |
| `required_linear_history` | Merge commits que oscurecen el historial |
| `allow_force_pushes: false` | Force push que borra historial |
| `allow_deletions: false` | Borrar la branch main |

### Comprobaciones y dónde corren

| Check | Antes de la PR (local) | Al cerrar un bloque grande (a mano) | Qué valida |
|-------|------------------------|-------------------------------------|-----------|
| `lint` | Pre-commit / GGA | — | Zero-tolerance lint |
| `test` | pytest / flutter test / jest | El workflow de CI del proyecto, con `workflow_dispatch` | Unit + integration tests |
| `e2e-evidence` | Hook `e2e-gate.mjs` al hacer commit | `e2e-evidence-check.yml` | results.json válido + HTML report existe |
| acceptance | `/acceptance-check` | `acceptance-gate.yml` | Los AC del PRD contra los cambios de la rama |

---

## GitHub Action: e2e-evidence check

```yaml
# .github/workflows/e2e-evidence-check.yml
name: E2E Evidence Check

on:
  workflow_dispatch:  # solo a mano, al cerrar un bloque grande

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

`onboard_project` y `upgrade_project` no copian estas plantillas: se copian a mano si el proyecto
las quiere. Cuando se onboardea un proyecto con SpecBox Engine:

1. El proyecto debería tener branch protection en main, sin status checks obligatorios (en una
   organización con el plan Free, la protección de ramas solo está disponible en repos públicos)
2. `acceptance-gate.yml` puede estar en `.github/workflows/`; solo corre a mano
3. `e2e-evidence-check.yml` puede estar en `.github/workflows/`; solo corre a mano

Si una copia anterior trae `pull_request:` o `push:` en su `on:`, se cambia por
`workflow_dispatch:`. Una tarea programada (`schedule:`), como mucho una vez al día.

### Verificación

```bash
# Verificar que branch protection está activa (y que no exige status checks: null)
gh api repos/{owner}/{repo}/branches/main/protection --jq '.required_status_checks'

# Lanzar a mano un workflow al cerrar un bloque grande
gh workflow run e2e-evidence-check.yml --ref main
```

---

*SpecBox Engine v5.19.0 — GitHub Branch Protection Setup*
