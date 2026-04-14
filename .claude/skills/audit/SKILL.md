---
name: quality-audit
description: >
  ISO/IEC 25010 (SQuaRE) quality audit on-demand for onboarded projects.
  Use when the user says "audit project", "quality audit", "ISO 25010",
  "SQuaRE audit", "audita el proyecto", or wants a comprehensive quality
  report across 8 characteristics with PDF + JSON evidence.
context: direct
---

# /audit — ISO/IEC 25010 Quality Audit (on-demand)

> v5.21+ — Módulo Quality Audit v1
> Agente responsable: AG-10 Quality Auditor
> Backend: `run_quality_audit` + `attach_audit_evidence` (MCP tools)

## Uso

```
/audit [project]
```

- Sin argumento: audita el proyecto actual (resuelto desde cwd o registro).
- Con nombre: audita un proyecto onboarded (busca en `STATE_PATH/projects/`).

## Qué hace

1. Llama a `check_audit_tools_status(project_path)` para ver qué herramientas
   externas están instaladas (semgrep, gitleaks, pip-audit, lizard, jscpd,
   checkov, npm). Si falta alguna, muestra al usuario la lista + comandos de
   instalación y pregunta:
   - **¿Instalar ahora?** → ejecuta `.quality/scripts/install-audit-tools.sh --yes`
   - **¿Continuar sin ellas?** → sigue con degradación (findings incompletos)
   - **¿Cancelar?** → aborta

   Nunca se instalan herramientas sin consentimiento. La instalación es
   perezosa: sólo ocurre cuando el usuario lanza `/audit`, nunca durante
   `install.sh` o `upgrade_project`.

2. Carga el skill `embed-build-brand` para aplicar paleta negro + cyan `#29F3E3`
   al PDF final. Si el skill no está disponible, degrada a defaults y lo
   reporta en `meta.warnings` (la auditoría continúa).
3. Invoca `run_quality_audit(project, scope="full")` → el MCP tool ejecuta
   los 8 analizadores SQuaRE en orden:
   1. Functional Suitability
   2. Performance Efficiency
   3. Compatibility
   4. Usability
   5. Reliability
   6. Security (semgrep + gitleaks + pip-audit/npm audit + checkov si IaC)
   7. Maintainability (mix 60% clásico + 40% SpecBox — documentado en `breakdown`)
   8. Portability
4. Delega al agente **AG-10 Quality Auditor** la síntesis de justificaciones
   y recomendaciones priorizadas. AG-10 jamás modifica código.
5. Invoca `attach_audit_evidence(project, report=<enriched>)` → persiste:
   - `STATE_PATH/projects/<project>/evidence/audits/audit_<ts>.json`
   - `STATE_PATH/projects/<project>/evidence/audits/audit_<ts>.pdf`
   - Actualiza `project_meta.last_audit` (visible en Sala de Máquinas).
6. Muestra un resumen con score global, semáforo por bloque y rutas de
   evidencia.

## Scope parcial

```
/audit <project> security
/audit <project> maintainability
```

Útil para re-correr un único bloque tras arreglar findings concretos.

## Degradación elegante

Las herramientas externas son opcionales — si falta alguna, se reporta en
`tools_used` con `status: "missing"` y la auditoría continúa:

- `semgrep` — SAST multi-lenguaje (OWASP Top 10)
- `gitleaks` — detección de secretos
- `pip-audit` / `npm audit` — vulnerabilidades de dependencias
- `checkov` — IaC (solo si se detectan Dockerfile/Terraform/k8s)
- `lizard` — complejidad ciclomática
- `jscpd` — duplicación de código

## Qué NO hace (v1, explícito)

- NO modifica archivos del proyecto auditado.
- NO introduce hooks automáticos.
- NO bloquea merges ni impone gates de score mínimo.
- NO compara con auditorías anteriores (sin histórico en v1).
- NO se integra con CI/CD externo.

## Flujo del agente

```
/audit mcprofit
  │
  ├─ 1. check_audit_tools_status(project_path)
  │     ↓
  │   Si faltan tools → mostrar lista + preguntar (install / continue / cancel)
  │     ├─ install → .quality/scripts/install-audit-tools.sh --yes
  │     ├─ continue → seguir con degradación
  │     └─ cancel → abortar
  │
  ├─ 2. load_skill("embed-build-brand")   (opcional; si falta → warning)
  ├─ 3. run_quality_audit("mcprofit", scope="full")
  │     ↓
  │   QualityReport bruto con 8 CharacteristicResult + audit_tools_status
  │     ↓
  ├─ 4. AG-10 Quality Auditor sintetiza:
  │     - justification por bloque (cita raw_metrics)
  │     - recommendations priorizadas (con finding_ref)
  │     - desglose 60/40 verbalizado en maintainability
  │     ↓
  ├─ 5. attach_audit_evidence("mcprofit", report=<enriched>)
  │     ↓
  │   PDF + JSON bajo evidence/audits/, project_meta.last_audit actualizado
  │
  └─ 6. Resumen final al usuario
```

## Dogfooding

```
/audit specbox-engine
```

Debe funcionar sobre el propio repo como caso de prueba.

## Criterios de aceptación

- Genera PDF + JSON válidos en `evidence/audits/`.
- Los 8 bloques SQuaRE aparecen con scores justificados.
- Security detecta al menos una vulnerabilidad en un proyecto con CVE conocido.
- Maintainability muestra el breakdown 60/40 explícitamente.
- El PDF respeta el brand embed.build (fallback si el skill falta).
- Herramientas ausentes se reportan sin abortar.
- La auditoría no modifica nada del proyecto auditado.
