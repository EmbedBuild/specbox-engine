# Claude Design como proveedor visual del VEG

> US-29 · Engine ≥ v6.12. Cómo activar **Claude Design** como proveedor de
> generación visual del VEG, y en qué se diferencia de Stitch.
> ADR: `doc/decisions/veg_visual_provider.md`.

## TL;DR

El VEG puede diseñar con **dos proveedores**, elegibles por proyecto en
`.claude/settings.local.json` → `veg.providers`:

- **`stitch`** (default) — text-to-mockup. Útil en fase temprana, sin código.
- **`claude_design`** — diseña con los **componentes reales compilados** de tu
  design-system (1:1 a código). Vía la tool `DesignSync` del harness.

Un proyecto **sin** `veg.providers` se comporta **exactamente como hoy** (solo
Stitch). No se rompe nada.

## Diferencias Stitch vs Claude Design

| Eje | Stitch | Claude Design |
|---|---|---|
| **Input** | Prompt de texto (text-to-design) | Componentes reales compilados del design-system |
| **Output** | HTML de mockup → design-to-code | Diseños con tus componentes reales, **mapeo 1:1 a código** |
| **Cuándo aplica** | Fase temprana, sin código | Solo cuando existe **design-system compilado** (`dist/`, Storybook) |
| **Granularidad** | Una pantalla por prompt | Sincroniza la **biblioteca completa**; luego se construyen pantallas con ella |
| **Auth** | API key de Google (se guarda obfuscada) | **Login de claude.ai de tu máquina** — sin API key |
| **Coste** | Stitch MCP gratis | **Tu suscripción de claude.ai** (la del usuario logueado) |

Claude Design **no reemplaza** a Stitch: es un proveedor **complementario** con
precondiciones propias. Cuando hay design-system compilado, Claude Design es el
**preferido**; Stitch queda como fallback.

## Activar Claude Design

### Opción A — vía `/visual-setup` (recomendado)

`/visual-setup` incluye el **Paso 2.9 — Seleccionar proveedor visual**: detecta
si hay design-system compilado y te ofrece *Claude Design / Stitch / Ambos*. Si
hay design-system, recomienda Claude Design por defecto y, si lo eliges, crea y
ancla el `projectId` (con tu confirmación en el prompt de DesignSync).

### Opción B — editar la config a mano

```jsonc
// .claude/settings.local.json
{
  "veg": {
    "providers": ["claude_design"],          // o ["stitch","claude_design"]
    "claude_design": {
      "projectId": null,                       // el engine lo crea y lo ancla la 1ª vez
      "syncRepo": "salacal-web"                // repo cuyo dist/ es el design-system
    }
  }
}
```

Valores admitidos de `providers`: `["stitch"]`, `["claude_design"]`,
`["stitch","claude_design"]`. Cualquier otro valor produce un error de
validación que nombra el valor inválido.

El bloque `veg.claude_design` ancla `projectId` (opcional — el engine lo crea y
lo persiste la primera vez) y `syncRepo` (el repo cuyo `dist/` es el
design-system). **No** contiene ninguna credencial.

## Precondición: design-system compilado (gate por topología)

Claude Design solo aplica si existe un **design-system compilado**
(`package.json` + `dist/`, o Storybook). **Dónde** debe vivir depende de la
topología del proyecto:

- **Multirepo orquestador/satélite**: el design-system vive **una sola vez en el
  orquestador**. El `projectId` se ancla ahí y su `dist/` se sincroniza una vez;
  los satélites de UI (web, mobile, …) **consumen** esa misma biblioteca.
- **Monorepo**: el design-system vive en el **propio repo**.

Si **aún no** hay design-system compilado, el VEG marca Claude Design como
**`pending`** con el motivo (p. ej. "missing dist/") y **`/plan` continúa sin
fallar**. En cuanto compiles el design-system, deja de estar pending.

Consulta el estado con:

```
mcp__SpecBox-MCP__claude_design_status(project, project_root)
→ providers, projectId, role, site, gate_ready, gate_reason, login_active
```

## Suscripción y autenticación

- Claude Design usa el **login de claude.ai activo en tu máquina** (vía
  `DesignSync`). **No** se pide ni se guarda ninguna API key ni cuenta de
  servicio.
- El consumo se factura a la **suscripción del usuario logueado en esa máquina**.
- Si no hay login activo, la capacidad queda `pending`
  (`requires active claude.ai login on this machine`) — inicia sesión en
  claude.ai y reintenta.
- **Multi-cuenta**: si el `projectId` lo creó otra cuenta del equipo pero tu
  sesión tiene acceso de escritura, el sync **procede con tu sesión** (tu
  suscripción) y te avisa. Si no tienes acceso, queda `pending`.

## Prompts de permiso (no se auto-aprueban)

DesignSync pide permiso para `create_project`, `finalize_plan` y `write_files`.
Las skills **respetan** esos prompts en sesiones interactivas: no se asume
auto-aprobación. El orden siempre es `list/read → finalize_plan → write/delete`.

## Borrado de proyectos

**No hay borrado programático.** DesignSync no expone `delete_project`. Para
eliminar un proyecto de Claude Design, hazlo **manualmente en claude.ai**.

## Idempotencia del sync

El sync usa el ancla `_ds_sync.json` para no re-subir componentes sin cambios.
Si el `dist/` no cambió desde el último sync, un nuevo sync no emite escrituras
(`status="skip"`).

## Referencia rápida de tools

| Tool | Uso |
|---|---|
| `claude_design_status` | Estado: providers, projectId, gate, login activo |
| `claude_design_list_projects` | Lista tus proyectos Claude Design (read) |
| `claude_design_get_project` | Metadatos de un proyecto (read) |
| `claude_design_create_project` | Crea y ancla un proyecto (prompt de permiso) |
| `claude_design_sync_design_system` | Planifica/guía el sync del design-system |

> No existe `claude_design_delete_project` — ver "Borrado de proyectos".
