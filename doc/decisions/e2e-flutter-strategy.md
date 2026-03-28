# ADR: Estrategia E2E para Flutter — Hybrid Pipeline

> **Estado:** Aprobado | **Fecha:** 2026-03-28 | **Versión Engine:** v5.12.0+

---

## Contexto

Flutter Web renderiza todo en `<canvas>` (CanvasKit/Skwasm). El renderer HTML fue eliminado por el equipo de Flutter. Esto hace que los selectores DOM estándar no funcionen y que Playwright necesite el accessibility/semantics tree para interactuar con la app.

SpecBox Engine requiere **HTML Evidence Reports self-contained** con screenshots base64 como evidencia obligatoria de acceptance testing (AG-09a/AG-09b). Playwright genera estos reports de serie. Patrol v4 (LeanCode) no los genera.

Al mismo tiempo, Patrol v4 es el único framework que ofrece **native automation real** para Flutter mobile (permisos, notificaciones, WebViews, biometría) — algo imposible con Playwright.

---

## Decisión

**Hybrid Pipeline**: usar la herramienta correcta para cada plataforma.

| Plataforma | Framework E2E | Reporting |
|-----------|--------------|-----------|
| **Flutter Web** | Playwright (via semantics tree) | HTML Report nativo de Playwright |
| **Flutter Mobile** | Patrol v4 (native automation) | `patrol-evidence-generator.js` (post-procesador custom) |

### Fuente única de verdad BDD

Los archivos `.feature` (Gherkin en español) son compartidos. Las step definitions son específicas por plataforma:

```
test/acceptance/features/
  UC-001_crear_propiedad.feature     <-- Gherkin compartido

e2e/steps/                           <-- Playwright (web)
  UC-001_steps.ts

test/acceptance/steps/               <-- Patrol (mobile)
  UC-001_steps.dart
```

---

## Alternativas evaluadas

### 1. Solo Playwright (via semantics tree)

- **Pro:** Report HTML nativo, pipeline idéntico a React, madurez (6 años, 70K stars)
- **Contra:** No puede testear permisos, notificaciones, cámara, biometría en mobile
- **Veredicto:** Suficiente para web-only. Insuficiente para mobile.

### 2. Solo Patrol v4

- **Pro:** Write-once multiplatforma, acceso directo al widget tree, native automation
- **Contra:** No genera HTML Evidence Reports. Screenshots manuales. Web support tiene 4 meses. Reporting solo JUnit XML.
- **Veredicto:** Superior para mobile. Inferior en reporting para el pipeline SpecBox.

### 3. Patrol + Allure Framework

- **Pro:** Allure genera reports detallados con screenshots
- **Contra:** Allure produce multi-file HTML (no self-contained). Android-only (`AllurePatrolJUnitRunner`). No hay adapter iOS. Setup complejo.
- **Veredicto:** Complementario, pero no resuelve el requisito de HTML self-contained.

### 4. flutter_gherkin + cucumber-html-reporter

- **Pro:** Pipeline 100% Dart. Genera Cucumber JSON con screenshots.
- **Contra:** Incompatible directo con `patrol test` como runner. Madurez baja.
- **Veredicto:** Viable como experimento futuro, no para producción actual.

### 5. Patrol Web con Playwright reporter (pass-through)

- **Pro:** Patrol Web usa Playwright internamente — podría heredar el HTML reporter
- **Contra:** Solo web. 4 meses de madurez. Flags de reporter no documentados oficialmente.
- **Veredicto:** Promisorio pero inmaduro. Revisitar en 6 meses.

---

## Decisión sobre el gap de reporting en Patrol

Para tests mobile con Patrol, se crea `patrol-evidence-generator.js`: un post-procesador que:

1. Lee JUnit XML de Patrol (`build/app/outputs/androidTest-results/`)
2. Recoge screenshots de `takeScreenshot()` (nombrados `AC-XX_step_N_desc`)
3. Los convierte a base64
4. Genera HTML **con el template idéntico** al de AG-09a para Playwright

Esto produce el mismo output que AG-09b espera — el pipeline no distingue el origen.

---

## Requisitos técnicos

### Flutter Web (Playwright)

1. **Semantics obligatorio** en `main.dart`:
   ```dart
   if (kIsWeb) SemanticsBinding.instance.ensureSemantics();
   ```
2. Build: `flutter build web --wasm` (o `--web-renderer canvaskit`)
3. Servidor: `npx serve build/web -s -l 4200` (flag `-s` para SPA fallback)
4. Input: `click()` + `keyboard.type({ delay: 10 })` — nunca `fill()`
5. Navegación: `window.location.hash` — nunca `page.goto('/route')`
6. Flutter >= 3.31 requerido (fix de click leak #163576)

### Flutter Mobile (Patrol)

1. Patrol v4.5.0+ con `patrol_cli` v4.3.0+
2. Screenshots con naming convention: `AC-XX_step_N_descripcion`
3. Post-test: ejecutar `patrol-evidence-generator.js`
4. Config nativa: `MainActivityTest.java` (Android) + XCTest scheme (iOS)

---

## Consecuencias

### Positivas

- HTML Evidence Report idéntico en ambos paths — AG-09b no distingue el origen
- Cada herramienta se usa donde es superior (Playwright: web/reporting, Patrol: mobile/native)
- Los `.feature` son la fuente única de verdad BDD — sin duplicación de specs
- El `e2e-report` hook funciona igual en ambos paths
- Sin vendor lock-in — si Patrol mejora su reporting, el post-procesador se elimina

### Negativas

- Dos conjuntos de step definitions (TypeScript + Dart)
- AG-09a necesita detectar la plataforma target para elegir el path correcto
- `patrol-evidence-generator.js` es tooling custom que hay que mantener

### Riesgos

- Patrol Web es nuevo (4 meses) — puede haber breaking changes
- El semantics tree de Flutter puede cambiar entre versiones
- `excludeSemantics: true` en widgets rompe aria-labels (Flutter bug #172206)

---

## Referencias

- [Playwright Flutter Web issue #26587](https://github.com/microsoft/playwright/issues/26587) — cerrado, no habrá soporte nativo
- [Flutter HTML renderer eliminado #145954](https://github.com/flutter/flutter/issues/145954)
- [Patrol v4.0 release](https://leancode.co/blog/patrol-4-0-release)
- [Patrol Web support](https://leancode.co/blog/patrol-web-support)
- [Patrol HTML report discussion #1526](https://github.com/leancodepl/patrol/discussions/1526)
- [ensureSemantics click leak fix #163576](https://github.com/flutter/flutter/issues/163576)
- [excludeSemantics breaks aria-label #172206](https://github.com/flutter/flutter/issues/172206)
- SpecBox Engine `architecture/flutter/e2e-testing.md`
- SpecBox Engine `agents/acceptance-tester.md`
