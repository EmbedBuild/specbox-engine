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
> Backend (v6.0.1): el cliente ejecuta los analizadores localmente y envía el `QualityReport` al MCP con `submit_quality_audit` + `attach_audit_evidence`.
>
> **Cambio v6.0.1 (MCP Path Contract)**: el viejo `run_quality_audit` orquestaba los 8 analizadores ISO/IEC 25010 en el host del MCP, lo que rompía en MCP remoto (los analizadores escaneaban el filesystem del VPS, no el del cliente). v6.0.1 mueve la orquestación al cliente: el skill ejecuta los scripts de `.quality/scripts/audit/` (ver README en ese directorio), construye el `QualityReport` dict en memoria y lo envía vía `submit_quality_audit(project, report)`. El nuevo `check_audit_tools_status(stack)` recibe el stack del cliente como parámetro en vez de escanear el filesystem. `run_quality_audit` queda como shim deprecado que retorna un error explicativo si lo llamas sin `report`.

## Uso

```
/audit [project]
```

- Sin argumento: audita el proyecto actual (resuelto desde cwd o registro).
- Con nombre: audita un proyecto onboarded (busca en `STATE_PATH/projects/`).

## Qué hace

1. **Detecta stack localmente** (lee `pubspec.yaml` / `package.json` / `go.mod` / `pyproject.toml`) y llama a `check_audit_tools_status(stack=<detected>)` para ver qué herramientas
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
3. **Ejecuta los analizadores localmente** desde `.quality/scripts/audit/` (en v6.0.1 este directorio contiene un README descriptivo; el porting de los 8 scripts está planeado para v6.0.2). Cada analizador produce un fragmento JSON del `QualityReport`. El skill consolida los fragmentos en un único dict y lo envía con `submit_quality_audit(project, report=<dict>)`. El backend valida el dict y devuelve el report canónico que pasa a AG-10. **No uses `run_quality_audit` salvo como fallback** — está deprecado y devuelve error si lo invocas sin `report`.

   El report cubre los 8 analizadores SQuaRE en orden:
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
  ├─ 1. detectar stack localmente + check_audit_tools_status(stack)
  │     ↓
  │   Si faltan tools → mostrar lista + preguntar (install / continue / cancel)
  │     ├─ install → .quality/scripts/install-audit-tools.sh --yes
  │     ├─ continue → seguir con degradación
  │     └─ cancel → abortar
  │
  ├─ 2. load_skill("embed-build-brand")   (opcional; si falta → warning)
  ├─ 3. ejecutar .quality/scripts/audit/ localmente + submit_quality_audit("mcprofit", report=<dict>)
  │     ↓
  │   QualityReport canónico (validado) con 8 CharacteristicResult + audit_tools_status
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
