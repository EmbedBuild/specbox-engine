# Tokens del sistema de diseño

Cuando un proyecto tiene **tokens del sistema** (`design-system.tokens.json`), las herramientas de
diseño del engine los usan como **única fuente**: no leen un Brand Kit aparte ni rellenan con los
valores de un arquetipo. Si el proyecto no los tiene, el resultado de la generación incluye un aviso
con el enlace a esta guía.

## Qué cambia cuando existen

| Pieza | Sin tokens del sistema | Con tokens del sistema |
|---|---|---|
| `generate_design_md_tool` (DESIGN.md) | Brand Kit + VEG; lo que falte, del arquetipo | Colores, tipografía, tamaños, pesos, radios, espaciado, estados y sombras de los tokens, y nada más |
| Comprobación | — | `values_outside_system`: cada valor del documento que ningún token define (vacío = conforme) |
| Stitch | Recibe un DESIGN.md con valores de arquetipo | Recibe el DESIGN.md hecho de tokens (vista Material 3 incluida) |
| Claude Design | Sincroniza el design system compilado | Igual; la respuesta nombra lo que recibe (`system_input`) |
| Pantallas de Stitch o Claude Design | Candidatas | Candidatas |

Las pantallas que generan Stitch y Claude Design son siempre **candidatas** (`design_role:
"candidate"` en la respuesta y un comentario al principio del HTML guardado): sirven para decidir
disposición, jerarquía y flujo. Nunca son fuente de producción; el código toma los valores de los
tokens, no del diseño. `/plan` lo escribe en la sección «Fuente de diseño» de cada plan.

## El formato

Es el formato de tokens de un Design System: el que publica `@specbox/tokens` y el que consume un
Artifact de tipo Design System en claude.ai. Lo mínimo que el engine necesita:

```json
{
  "name": "Mi sistema",
  "version": 1,
  "color": {
    "themes": [{ "id": "light" }, { "id": "dark" }],
    "tokens": [
      { "name": "primary", "value": { "light": "#1A1B1E", "dark": "#F2F1EE" } },
      { "name": "background", "value": { "light": "#F7F6F4", "dark": "#121315" } },
      { "name": "text", "value": { "light": "{primary}", "dark": "{primary}" } }
    ]
  },
  "type": {
    "families": { "sans": "\"IBM Plex Sans\", system-ui, sans-serif" },
    "groups": [
      {
        "name": "Texto",
        "family": "sans",
        "styles": [
          { "name": "h1", "fontSize": "30px", "lineHeight": "36px", "fontWeight": 600 },
          { "name": "h2", "fontSize": "24px", "lineHeight": "30px", "fontWeight": 600 },
          { "name": "body", "fontSize": "14px", "lineHeight": "20px", "fontWeight": 400 }
        ]
      }
    ]
  },
  "radius": { "tokens": [{ "name": "radius-md", "value": "6px" }] },
  "spacing": { "tokens": [{ "name": "space-4", "value": "16px" }] }
}
```

- Un color puede tener un valor por tema o uno solo para todos. `"{nombre}"` es un alias a otro
  color del mismo tema.
- `shadow` admite valores por tema. Cualquier otra sección con `tokens` (densidad, layout, capas,
  duraciones…) se lee tal cual y sus valores también cuentan como del sistema.

### Nombres que el engine reconoce

El engine busca cada papel por estos nombres, en este orden. Son obligatorios los marcados.

| Papel | Nombres aceptados |
|---|---|
| Color principal (obligatorio) | `accent`, `primary`, `brand` |
| Fondo (obligatorio) | `paper-000`, `background`, `bg` |
| Texto (obligatorio) | `ink-900`, `text-primary`, `text`, `foreground` |
| Superficie | `paper-100`, `surface` |
| Texto secundario | `ink-700`, `text-secondary`, `muted` |
| Borde | `line-200`, `border` |
| Sobre el principal | `on-accent`, `on-primary` |
| Error · éxito · aviso | `danger-text` · `success-text` · `warning-text` (o `error`, `success`, `warning`) |
| Estados | todos los `status-*` |
| Título 1 (obligatorio) · 2 (obligatorio) · 3 | `display-xl`/`h1` · `display-lg`/`h2` · `display-md`/`h3` |
| Texto (obligatorio) · pie · etiqueta | `body-md`/`body`/`body-lg` · `caption` · `label` |
| Radios | `radius-sm`, `radius-md`, `radius-lg`, `radius-pill` |
| Espaciado | `space-1`, `space-2`, `space-4`, `space-6`, `space-8`, `space-12` |

Si falta un papel obligatorio, un alias apunta a un color que no existe o el fichero no es JSON, la
generación falla con `SYSTEM_TOKENS_INVALID` y dice qué falta. No se genera nada desde el Brand
Kit: un sistema roto no se sustituye en silencio.

## Dónde lo busca el engine

Primera coincidencia, desde la raíz del repositorio:

1. `doc/design/design-system.tokens.json`
2. `src/styles/tokens/design-system.tokens.json`
3. `apps/web/src/styles/tokens/design-system.tokens.json`
4. `web/src/styles/tokens/design-system.tokens.json`
5. `packages/tokens/dist/design-system.tokens.json`
6. `design-system.tokens.json`

Con el MCP remoto el servidor no ve tu disco: las skills (`/visual-setup`, `/plan`) buscan el
fichero y lo envían en `system_tokens_content`, junto a su ruta en `system_tokens_path`. Si llamas a
la tool con `project_root` contra el servidor remoto, responde `DESIGN_MD_CONTENT_REQUIRED` y explica
qué enviar.

## Cómo adoptarlos

**En el ecosistema SpecBox** (cloud, site, portal de proyectos): los tokens viven en
`packages/tokens` del orquestador. `npm run build:sync` los genera y deja
`design-system.tokens.json` en la carpeta de tokens de cada app (rutas 2 a 4 de la lista).

**En cualquier otro proyecto**:

1. Exporta tus tokens a este formato en `doc/design/design-system.tokens.json`. Si ya tienes un
   Artifact de tipo Design System en claude.ai, su `tokens.json` tiene esta forma.
2. Vuelve a generar el DESIGN.md (`/visual-setup` o `/plan`, que llaman a `generate_design_md_tool`).
3. Revisa que `values_outside_system` viene vacío y que no hay `warnings`. Un aviso típico: Stitch no
   ofrece tu fuente; entonces usa Inter y la comprobación lo lista como valor fuera del sistema.

Desde ese momento, cambiar el diseño es cambiar los tokens y volver a generar; el DESIGN.md no se
edita a mano.
