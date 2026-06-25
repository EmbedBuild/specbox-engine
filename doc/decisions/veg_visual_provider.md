# ADR: Capa `visual_provider` del VEG — Claude Design como segundo proveedor

> Estado: **Accepted** · Fecha: 2026-06-25 · US-29 (satélite `engine`)
> Discovery: `disc-52cbe4033fae` (`doc/discovery/claude-design-veg-provider/icp_jtbd.md`
> en el orquestador `EmbedBuild/specbox-manager`)

## Contexto

El VEG (Visual Engine Generation) generaba UI con un único proveedor: **Stitch**
(text-to-design → HTML mockup → design-to-code). Stitch da problemas en operación y
SpecBox es un sistema agéntico **para Claude**, por lo que la plataforma de diseño
debería poder ser la misma que la de ejecución.

**Claude Design** (`claude.ai/design`, operado vía la tool nativa del harness
`DesignSync`) ofrece un modelo distinto: diseña con los **componentes reales compilados**
del design-system del cliente, con mapeo 1:1 a código. No es un generador text-to-mockup
como Stitch; por eso **no es un reemplazo, sino un proveedor complementario** con
precondiciones propias.

| Eje | Stitch | Claude Design |
|---|---|---|
| Input | Prompt de texto | Componentes reales compilados del design-system |
| Output | HTML mockup → design-to-code | Diseños con componentes reales, 1:1 a código |
| Cuándo aplica | Fase temprana, sin código | Solo con design-system compilado (`dist/`, Storybook) |
| Granularidad | Una pantalla por prompt | Sincroniza la biblioteca; luego construye pantallas |

## Decisión

1. **Capa `visual_provider`.** Se introduce el concepto de proveedor visual
   ∈ `{stitch, claude_design}`, seleccionable **por proyecto** vía
   `.claude/settings.local.json` → `veg.providers`. Valores admitidos: `["stitch"]`,
   `["claude_design"]`, `["stitch","claude_design"]`. Implementado en
   `server/veg/visual_provider.py` (puro, sin red).

2. **Default sin ruptura.** Un proyecto **sin** `veg.providers` resuelve a `["stitch"]`
   — comportamiento byte-a-byte idéntico al actual. No se rompe ningún proyecto existente
   (no-objetivo "no romper Stitch").

3. **Claude Design preferido cuando aplica.** Si `claude_design` está activo **y** el gate
   de precondición resuelve `ready` (existe design-system compilado), el proveedor
   **efectivo preferido es `claude_design`**, con Stitch como *fallback*. Si el gate no
   está `ready`, `claude_design` queda **`pending`** con motivo y la generación continúa
   con Stitch (o se omite) — **nunca lanza excepción**.

4. **Esquema de config `veg.claude_design`.** Bloque opcional con `projectId` (UUID
   opcional, auto-creado y persistido en el primer `create_project`) y `syncRepo` (sitio
   del design-system). **Sin credenciales**: Claude Design usa el login de claude.ai de la
   sesión de la máquina (vía `DesignSync`), no una API key ni cuenta de servicio. El
   consumo se factura a la **suscripción del usuario logueado**. No hay borrado
   programático de proyectos (DesignSync no expone `delete_project`).

5. **Regla de anclaje por topología.** El design-system vive una sola vez:
   - **Multirepo orquestador/satélite** → en el **orquestador** (el `projectId` se ancla
     ahí, su `dist/` se sincroniza una vez; los satélites de UI —web, mobile— lo
     **consumen**).
   - **Monorepo** → en el **repo único**.

   La precondición real es `package.json` + `dist/` (o Storybook) en el sitio resuelto.
   El gate (`server/veg/design_system_gate.py`, UC-2903) implementa esta resolución.

## Consecuencias

- **Positivas**: diseño nativo de Claude (1:1 a código) cuando hay design-system; elección
  por proyecto; lenguaje visual único en multirepo; alineación plataforma diseño/ejecución;
  el consumo recae en la suscripción del usuario, sin claves compartidas.
- **Coste/limitaciones**: Claude Design requiere login claude.ai activo en la máquina (en
  headless/CI degrada a `pending`); los prompts de permiso de `DesignSync`
  (`create_project`, `finalize_plan`, `write_files`) no se auto-aprueban; el borrado de
  proyectos es manual en claude.ai.

## Alternativas descartadas

- **Reemplazar Stitch por Claude Design**: rompería proyectos en fase temprana sin código
  y los que ya usan Stitch. Descartado por el no-objetivo "no romper Stitch".
- **Claude Design opt-in puro (Stitch siempre default)**: no refleja la decisión de
  producto de preferir Claude Design cuando aplica. Se adopta el modelo "preferido cuando
  hay design-system, Stitch fallback".
- **Reimplementar el pipeline de bundle en el engine**: `/design-sync` y
  `package-build.mjs`/`resync.mjs` viven en el harness; el engine **delega**, no duplica
  (UC-2905).

## Trazabilidad

US-29 · UC-2901 (esta capa + config + ADR) · UC-2902 (tools) · UC-2903 (gate) ·
UC-2904 (skills) · UC-2905 (motor sync) · UC-2906 (doc). JTBDs: JR-CD.1..6, JE-CD.1..2.
