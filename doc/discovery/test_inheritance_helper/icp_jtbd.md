# Discovery: test_inheritance_helper

**Discovery ID**: disc-9d5fc89aa5a7
**Created**: 2026-05-24T23:45:50.257408+00:00
**Status**: DISCOVERY_INCOMPLETE
**Mode**: bootstrap
**Source of inheritance**: doc/app/app_market.md @ created during this discovery flow (sealed 2026-05-25T23:48:22Z)

## ICPs involucrados

- **ICP-1: Owner-operator del engine (JPS, dogfooding)** — canónico, definido en `doc/app/app_market.md` §1. Es el único usuario del engine en v1 que escribe tests sobre la base del propio engine: mantiene tools MCP, refactoriza fixtures de la suite `tests/test_native_*.py` y escribe nuevas test classes que extienden bases existentes. Sanity check 3 personas concretas: ✅ heredado del producto (single-tenant por diseño en v1).

Sin ICPs nuevos para esta feature. ICP-2 e ICP-3 quedan fuera por construcción: no escriben tests del engine — lo consumen como caja.

## JTBDs racionales

- **JR-Ftest_inheritance_helper.1 [ICP-1]**: Cuando escribo una nueva test class que extiende un setUp base existente (ej. `TestNativeBackendBase`), quiero que el helper de inheritance herede automáticamente los fixtures y mocks declarados en el parent, para no duplicar 20+ líneas de setup en cada subclass.

- **JR-Ftest_inheritance_helper.2 [ICP-1]**: Cuando refactorizo una clase base de tests (ej. cambio el shape de un fixture compartido por 8 subclasses), quiero que los tests hijos hereden el cambio sin tocarlos uno por uno, para que el refactor cueste minutos en vez de horas y la suite siga verde.

- **JR-Ftest_inheritance_helper.3 [ICP-1]**: Cuando un test hijo necesita override puntual de un mock heredado (ej. cambia un valor de fixture solo en ese test), quiero declararlo en una línea explícita y trazable, para que el siguiente lector entienda qué se está pisando sin necesidad de grep recursivo.

## JTBDs emocionales

- **JE-Ftest_inheritance_helper.1 [ICP-1]**: Sentir que añadir tests no es un peaje aburrido sino un acto barato. La fricción "tengo que copiar todo el setup otra vez" desaparece y escribir tests vuelve a ser placentero — al abrir un test file nuevo, lo primero que se ve es la lógica del caso, no 30 líneas de boilerplate. Sensación observable: el revisor puede mirar el diff de un test file nuevo y comprobar si las primeras N líneas son lógica o boilerplate.

## Validation evidence

- **Tipo**: waiver explícito.
- **Justificación**: feature interna del engine, sin necesidad de validación con usuarios externos. El único usuario actual del engine que escribe tests sobre su base es el propio owner (ICP-1), que también es quien identifica la fricción en primera persona durante el desarrollo diario de tools MCP y refactors de fixtures compartidos en `tests/test_native_*.py`, `tests/coordination/`, y los nuevos módulos `server/app_docs/`. La señal de mercado es la experiencia repetida del owner sobre la base de código existente: cada vez que se añade una test class que extiende un setUp existente, se duplica boilerplate del parent. No procede entrevista con usuarios externos porque (a) no existen en v1 — producto single-tenant declarado en `app_prd.md §3` y `app_market.md §1`, y (b) la fricción es observable directamente en el diff de cualquier test class que reescribe setUp manualmente.

## Drift from app_market

- **Nuevos ICPs introducidos**: ninguno. Sólo participa ICP-1, ya canónico en `app_market.md` §1.
- **Nuevos JTBDs introducidos**: 3 racionales + 1 emocional a nivel feature. No constituyen drift: son refinamientos verticales de los JTBDs globales del producto.
  - JR-Ftest_inheritance_helper.{1,2} ⊆ **JR-G.4** ("refactor con suite verde como gate de merge").
  - JR-Ftest_inheritance_helper.3 ⊆ **JR-G.1** ("trazabilidad — cada línea justifica su existencia").
  - JE-Ftest_inheritance_helper.1 alineado con **JE-G.2** ("agente con disciplina, no improvisando").
- **Resolución**: no drift detected. No se modifica `app_market.md`.

## Verdict

Pending re-evaluation by `validate_discovery_completeness` after this rewrite.

---

> Este artefacto se completa interactivamente via el skill `/discovery`.
> Tras completarlo, `validate_discovery_completeness` actualizará el verdict
> a `READY_FOR_PRD` cuando todas las secciones estén llenas.
