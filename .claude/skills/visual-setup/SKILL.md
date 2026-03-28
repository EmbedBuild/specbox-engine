---
name: visual-setup
description: >
  Configure complete visual identity for a project before development.
  Use when the user says "visual setup", "setup design", "configure brand",
  "design system", "visual identity", "brand kit", or wants to set up
  Stitch + VEG + brand tokens before running /plan.
context: fork
agent: Plan
---

# /visual-setup (Global)

Configura la identidad visual completa de un proyecto ANTES de empezar a desarrollar: Brand Kit + Google Stitch Design System + VEG base + Multi-Form-Factor + Prompt Template. Tras ejecutar este skill, `/plan` y `/implement` generan disenos consistentes con la marca sin intervencion adicional.

## Uso

```
/visual-setup                          # Modo interactivo completo
/visual-setup calm-enterprise          # Preset de estetica
/visual-setup --from doc/brand/        # Parsear brand kit existente
```

## Posicion en el pipeline

```
/prd → PRD + Trello/Plane
  ↓
/visual-setup → Brand Kit + Stitch DS + VEG + Multi-FF  ← ESTE SKILL
  ↓
/plan → Plan tecnico + Disenos Stitch (ya con brand)
  ↓
/implement → Codigo con design-to-code fiel a la marca
```

---

## Paso 0: Detectar Estado Actual

### 0.1 Verificar artefactos existentes

```
¿Que existe ya?
├── doc/brand/brand_kit/SKILL.md     → Brand Kit completo
├── doc/brand/brand_kit/variables.css → Tokens CSS
├── doc/brand/brand_briefing.md      → Briefing parcial
├── doc/veg/base/                    → VEG base existente
├── doc/design/stitch-prompt-template.md → Prompt template
└── .claude/settings.local.json      → Config Stitch/VEG
```

```bash
# Detectar brand kit
ls doc/brand/brand_kit/SKILL.md 2>/dev/null
ls doc/brand/brand_kit/variables.css 2>/dev/null
ls doc/brand/brand_briefing.md 2>/dev/null

# Detectar VEG base
ls doc/veg/base/ 2>/dev/null

# Detectar Stitch config
cat .claude/settings.local.json 2>/dev/null | grep -E "stitch|projectId|designSystem"

# Detectar prompt template
ls doc/design/stitch-prompt-template.md 2>/dev/null
```

### 0.2 Evaluar estado

```
Estado detectado:
├── COMPLETO → Todo existe (brand kit + stitch + VEG + template)
│   └── INFO: "El proyecto ya tiene identidad visual configurada."
│       └── Preguntar: "¿Quieres actualizar algo o empezar de cero?"
│
├── PARCIAL → Algunos artefactos existen
│   └── INFO: "Se encontraron artefactos parciales. Se completara lo que falta."
│   └── Listar que existe y que falta
│   └── Continuar desde el paso que corresponda
│
└── VACIO → Nada existe
    └── INFO: "Proyecto sin identidad visual. Iniciando configuracion completa."
    └── Continuar con Paso 1
```

### 0.3 Detectar proyecto Stitch existente

Si hay `stitch.projectId` en `.claude/settings.local.json`:
1. Llamar `mcp__stitch__get_project` con ese projectId
2. Si responde OK → reusar proyecto existente
3. Si falla → crear nuevo en Paso 3

---

## Paso 1: Recopilar Identidad Visual

### 1.1 Arbol de decision de fuentes de datos

```
¿De donde vienen los tokens?
├── doc/brand/brand_kit/SKILL.md existe
│   └── Parsear SKILL.md y extraer:
│       ├── Nombre del producto
│       ├── Dominio/sector
│       ├── Colores (primary, secondary, accent, neutral)
│       ├── Tipografia (heading, body, mono)
│       ├── Roundness
│       ├── Shadows
│       └── Dispositivo principal
│   └── Confirmar con usuario: "He extraido estos tokens del brand kit existente: [tabla]. ¿Correcto?"
│
├── doc/brand/brand_briefing.md existe
│   └── Parsear briefing y extraer tokens parciales
│   └── Completar datos faltantes con preguntas al usuario
│
└── No hay fuentes → Modo interactivo completo (1.2)
```

### 1.2 Modo interactivo

Preguntar al usuario en este orden. Mostrar las opciones como tabla para facilitar la eleccion.

**Pregunta 1: Nombre y dominio**

```
¿Cual es el nombre del producto y su dominio?
Ejemplo: "McProfit — fintech para gestion de inversiones"
```

**Pregunta 2: Estetica**

Mostrar tabla de presets disponibles:

| # | Estetica | Primary | Secondary | Font | Roundness | Referentes |
|---|----------|---------|-----------|------|-----------|------------|
| 1 | Calm Enterprise | #4F46E5 (Indigo) | #8B5CF6 (Violet) | GEIST | Rounded (12px) | Linear, Stripe |
| 2 | Bold Startup | #7C3AED (Violet) | #EC4899 (Pink) | DM_SANS | Medium (8px) | Notion, Figma |
| 3 | Minimal Tool | #171717 (Neutral) | #525252 (Gray) | INTER | Sharp (4px) | GitHub, Vercel |
| 4 | Financial Pro | #0F172A (Slate) | #0EA5E9 (Sky) | PLUS_JAKARTA_SANS | Medium (8px) | Stripe, Wise |
| 5 | Health & Care | #059669 (Emerald) | #14B8A6 (Teal) | MANROPE | Full/Pill | Calm, Headspace |
| 6 | Developer DX | #F97316 (Orange) | #EAB308 (Yellow) | SPACE_GROTESK | Medium (8px) | Vercel, Railway |
| 7 | Custom | (preguntar) | (preguntar) | (preguntar) | (preguntar) | — |

```
¿Que estetica se acerca mas a tu producto? (1-7)
```

**Si elige 1-6** → cargar preset completo, confirmar con usuario, permitir override de cualquier campo.

**Si elige 7 (Custom)** → continuar con preguntas 3-7.

**Pregunta 3: Color primario** (solo si Custom)

```
¿Color primario? (hex, ej: #4F46E5)
Puedo sugerir uno si me dices el sector del producto.
```

**Pregunta 4: Color secundario** (solo si Custom)

```
¿Color secundario? (hex, ej: #8B5CF6)
Si no tienes uno, puedo derivarlo del primario (complementario o analogo).
```

**Pregunta 5: Tipografia** (solo si Custom)

Mostrar tabla de fuentes soportadas por Stitch:

| # | Fuente | Estilo | Recomendada para |
|---|--------|--------|------------------|
| 1 | GEIST | Modern, clean, Vercel-style | SaaS, tech products, calm enterprise |
| 2 | INTER | Neutral, versatile | Universal, safe choice |
| 3 | DM_SANS | Geometric, friendly | Startups, consumer products |
| 4 | PLUS_JAKARTA_SANS | Elegant, modern | Fintech, premium SaaS |
| 5 | SPACE_GROTESK | Technical, distinctive | Developer tools, data products |
| 6 | SORA | Geometric, balanced | Modern apps, dashboards |
| 7 | IBM_PLEX_SANS | Corporate, reliable | Enterprise, B2B |
| 8 | MANROPE | Warm, rounded | Health, education, HR |
| 9 | RUBIK | Soft, approachable | Consumer, mobile-first |
| 10 | SOURCE_SANS_THREE | Clean, readable | Content-heavy, documentation |
| 11 | MONTSERRAT | Bold, impactful | Marketing, landing pages |
| 12 | WORK_SANS | Professional, balanced | Business tools, enterprise |

```
¿Tipografia? (1-12, o nombre directamente)
```

**Pregunta 6: Roundness** (solo si Custom)

| # | Nombre | CSS radius | Stitch enum | Efecto |
|---|--------|------------|-------------|--------|
| 1 | Sharp | 4px | ROUND_FOUR | Profesional, tecnico |
| 2 | Medium | 8px | ROUND_EIGHT | Balanceado, moderno |
| 3 | Rounded | 12px | ROUND_TWELVE | Amigable, suave |
| 4 | Full/Pill | 9999px | ROUND_FULL | Jugueton, bold |

```
¿Roundness? (1-4)
```

**Pregunta 7: Dispositivo principal** (solo si Custom)

```
¿Desktop-first o mobile-first?
```

### 1.3 Derivar colores complementarios

A partir de los colores primario y secundario, derivar automaticamente:

```
Paleta completa:
├── primary: {color elegido}
├── secondary: {color elegido}
├── accent: {derivar — triadic o split-complementary del primary}
├── success: #10B981 (Emerald 500 — standard)
├── warning: #F59E0B (Amber 500 — standard)
├── error: #EF4444 (Red 500 — standard)
├── info: #3B82F6 (Blue 500 — standard)
├── neutral-50 a neutral-900: {escala de grises derivada}
├── surface-light: #FFFFFF
├── surface-dark: #0F172A
├── text-primary-light: #1E293B
├── text-primary-dark: #F1F5F9
├── text-secondary-light: #64748B
└── text-secondary-dark: #94A3B8
```

### 1.4 Mapear tipografia a Stitch enum

```
Mapeo de fuentes:
├── headlineFont: {fuente elegida} (para titulos h1-h3)
├── bodyFont: {fuente elegida} (para texto body)
├── labelFont: {fuente elegida} (para labels, captions, buttons)
└── monoFont: "JetBrains Mono" o "Fira Code" (para code blocks — solo CSS, no Stitch)
```

**REGLA**: Las 3 fuentes de Stitch (headline, body, label) usan la MISMA familia por defecto. Solo separar si el usuario lo pide explicitamente o si la estetica lo requiere (ej: serif para headlines + sans para body).

### 1.5 Confirmar tokens con el usuario

Antes de generar cualquier artefacto, mostrar resumen completo:

```markdown
## Identidad Visual — {Nombre del Producto}

| Token | Valor |
|-------|-------|
| Nombre | {nombre} |
| Dominio | {dominio} |
| Estetica | {nombre preset o "Custom"} |
| Primary | {hex} ████ |
| Secondary | {hex} ████ |
| Accent | {hex} ████ |
| Font Headline | {FONT_ENUM} |
| Font Body | {FONT_ENUM} |
| Roundness | {nombre} ({Npx}) |
| Device | {desktop-first / mobile-first} |

¿Confirmas estos tokens? (si / ajustar campo)
```

**IMPORTANTE**: No avanzar al Paso 2 sin confirmacion explicita del usuario.

---

## Paso 2: Generar Brand Kit

> Solo si no existe `doc/brand/brand_kit/` o el usuario pidio regenerar.

### 2.1 Crear estructura de directorios

```bash
mkdir -p doc/brand/brand_kit
```

### 2.2 Generar `variables.css`

Archivo con CSS custom properties para light y dark mode:

```css
/* Brand Kit — {Nombre del Producto}
 * Generated by /visual-setup
 * Estetica: {estetica}
 */

:root {
  /* === Primary === */
  --color-primary: {primary};
  --color-primary-hover: {primary-600};
  --color-primary-active: {primary-700};
  --color-primary-subtle: {primary-50};
  --color-on-primary: #FFFFFF;

  /* === Secondary === */
  --color-secondary: {secondary};
  --color-secondary-hover: {secondary-600};
  --color-secondary-active: {secondary-700};
  --color-secondary-subtle: {secondary-50};
  --color-on-secondary: #FFFFFF;

  /* === Accent === */
  --color-accent: {accent};
  --color-accent-subtle: {accent-50};

  /* === Semantic === */
  --color-success: #10B981;
  --color-warning: #F59E0B;
  --color-error: #EF4444;
  --color-info: #3B82F6;

  /* === Neutral === */
  --color-neutral-50: {neutral-50};
  --color-neutral-100: {neutral-100};
  --color-neutral-200: {neutral-200};
  --color-neutral-300: {neutral-300};
  --color-neutral-400: {neutral-400};
  --color-neutral-500: {neutral-500};
  --color-neutral-600: {neutral-600};
  --color-neutral-700: {neutral-700};
  --color-neutral-800: {neutral-800};
  --color-neutral-900: {neutral-900};
  --color-neutral-950: {neutral-950};

  /* === Surfaces === */
  --color-surface: #FFFFFF;
  --color-surface-raised: {neutral-50};
  --color-surface-overlay: rgba(0, 0, 0, 0.5);
  --color-border: {neutral-200};
  --color-border-strong: {neutral-300};

  /* === Text === */
  --color-text-primary: #1E293B;
  --color-text-secondary: #64748B;
  --color-text-tertiary: #94A3B8;
  --color-text-inverse: #F1F5F9;

  /* === Typography === */
  --font-heading: '{font-name}', system-ui, sans-serif;
  --font-body: '{font-name}', system-ui, sans-serif;
  --font-label: '{font-name}', system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', 'Fira Code', monospace;

  /* === Sizes === */
  --text-xs: 0.75rem;    /* 12px */
  --text-sm: 0.875rem;   /* 14px */
  --text-base: 1rem;     /* 16px */
  --text-lg: 1.125rem;   /* 18px */
  --text-xl: 1.25rem;    /* 20px */
  --text-2xl: 1.5rem;    /* 24px */
  --text-3xl: 1.875rem;  /* 30px */
  --text-4xl: 2.25rem;   /* 36px */

  /* === Spacing === */
  --space-1: 0.25rem;    /* 4px */
  --space-2: 0.5rem;     /* 8px */
  --space-3: 0.75rem;    /* 12px */
  --space-4: 1rem;       /* 16px */
  --space-6: 1.5rem;     /* 24px */
  --space-8: 2rem;       /* 32px */
  --space-12: 3rem;      /* 48px */
  --space-16: 4rem;      /* 64px */

  /* === Radius === */
  --radius-sm: {radius-sm}px;
  --radius-md: {radius-md}px;
  --radius-lg: {radius-lg}px;
  --radius-full: 9999px;

  /* === Shadows === */
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
  --shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
}

/* === Dark Mode === */
[data-theme="dark"], .dark {
  --color-primary: {primary-400};
  --color-primary-hover: {primary-300};
  --color-primary-active: {primary-200};
  --color-primary-subtle: {primary-950};
  --color-on-primary: #0F172A;

  --color-secondary: {secondary-400};
  --color-secondary-hover: {secondary-300};
  --color-secondary-active: {secondary-200};
  --color-secondary-subtle: {secondary-950};
  --color-on-secondary: #0F172A;

  --color-accent: {accent-400};
  --color-accent-subtle: {accent-950};

  --color-surface: #0F172A;
  --color-surface-raised: #1E293B;
  --color-surface-overlay: rgba(0, 0, 0, 0.7);
  --color-border: #334155;
  --color-border-strong: #475569;

  --color-text-primary: #F1F5F9;
  --color-text-secondary: #94A3B8;
  --color-text-tertiary: #64748B;
  --color-text-inverse: #1E293B;
}
```

**Reglas de derivacion de radius por roundness:**

| Roundness | radius-sm | radius-md | radius-lg |
|-----------|-----------|-----------|-----------|
| Sharp (ROUND_FOUR) | 2 | 4 | 6 |
| Medium (ROUND_EIGHT) | 4 | 8 | 12 |
| Rounded (ROUND_TWELVE) | 6 | 12 | 16 |
| Full (ROUND_FULL) | 8 | 16 | 9999 |

### 2.3 Generar `tailwind.config.js`

```javascript
// Brand Kit — {Nombre del Producto}
// Generated by /visual-setup

/** @type {import('tailwindcss').Config} */
export default {
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: 'var(--color-primary)',
          hover: 'var(--color-primary-hover)',
          active: 'var(--color-primary-active)',
          subtle: 'var(--color-primary-subtle)',
        },
        secondary: {
          DEFAULT: 'var(--color-secondary)',
          hover: 'var(--color-secondary-hover)',
          active: 'var(--color-secondary-active)',
          subtle: 'var(--color-secondary-subtle)',
        },
        accent: {
          DEFAULT: 'var(--color-accent)',
          subtle: 'var(--color-accent-subtle)',
        },
        success: 'var(--color-success)',
        warning: 'var(--color-warning)',
        error: 'var(--color-error)',
        info: 'var(--color-info)',
        surface: {
          DEFAULT: 'var(--color-surface)',
          raised: 'var(--color-surface-raised)',
        },
        border: {
          DEFAULT: 'var(--color-border)',
          strong: 'var(--color-border-strong)',
        },
      },
      fontFamily: {
        heading: 'var(--font-heading)',
        body: 'var(--font-body)',
        label: 'var(--font-label)',
        mono: 'var(--font-mono)',
      },
      borderRadius: {
        sm: 'var(--radius-sm)',
        md: 'var(--radius-md)',
        lg: 'var(--radius-lg)',
        full: 'var(--radius-full)',
      },
      boxShadow: {
        sm: 'var(--shadow-sm)',
        md: 'var(--shadow-md)',
        lg: 'var(--shadow-lg)',
        xl: 'var(--shadow-xl)',
      },
    },
  },
};
```

### 2.4 Generar `SKILL.md` (resumen compacto para agentes)

Este archivo es lo que los sub-agentes (AG-02, AG-06) reciben en su contexto. Maximo ~600 tokens.

```markdown
# Brand: {Nombre del Producto}

> {Dominio} — Estetica: {nombre estetica}

## Paleta

| Rol | Hex | Uso |
|-----|-----|-----|
| Primary | {hex} | CTAs, links, focus rings, active states |
| Secondary | {hex} | Secondary buttons, tags, badges |
| Accent | {hex} | Highlights, notifications, progress |
| Neutral | {neutral-500} | Borders, dividers, disabled states |

## Tipografia

- **Heading**: {font-name} (bold/semibold)
- **Body**: {font-name} (regular, 16px base)
- **Label**: {font-name} (medium, 14px)
- **Mono**: JetBrains Mono (code blocks)

## Forma

- **Radius**: {roundness-name} ({N}px base)
- **Shadows**: {subtle/moderate/elevated} — usar shadow-sm por defecto, shadow-md para cards elevadas
- **Borders**: 1px solid neutral-200 (light) / neutral-700 (dark)

## Reglas

1. Primary solo para CTAs principales y elementos interactivos primarios
2. Secondary para acciones secundarias, nunca para texto
3. Neutral-50 para fondos de cards, neutral-100 para fondos de seccion
4. Mantener contraste minimo 4.5:1 (AA) para texto
5. Dark mode usa las variantes -400 de primary/secondary (mas brillantes sobre fondo oscuro)
6. Espaciado consistente: multiplos de 4px (space-1 a space-16)
```

### 2.5 Generar `light.md` (especificaciones tema claro)

```markdown
# {Nombre} — Light Theme

## Surfaces
- Background: #FFFFFF
- Card: {neutral-50}
- Section alt: {neutral-100}
- Sidebar: #FFFFFF border-r neutral-200

## Text
- Primary: #1E293B
- Secondary: #64748B
- Disabled: #CBD5E1

## Interactive
- Button primary: bg {primary}, text white, hover {primary-600}
- Button secondary: bg white, border {neutral-300}, hover bg {neutral-50}
- Input: bg white, border {neutral-300}, focus ring {primary}/20%
- Link: {primary}, hover {primary-700}, underline on hover

## Feedback
- Success: bg #ECFDF5, border #10B981, text #065F46
- Error: bg #FEF2F2, border #EF4444, text #991B1B
- Warning: bg #FFFBEB, border #F59E0B, text #92400E
- Info: bg #EFF6FF, border #3B82F6, text #1E40AF
```

### 2.6 Generar `dark.md` (especificaciones tema oscuro)

```markdown
# {Nombre} — Dark Theme

## Surfaces
- Background: #0F172A
- Card: #1E293B
- Section alt: #334155
- Sidebar: #0F172A border-r #334155

## Text
- Primary: #F1F5F9
- Secondary: #94A3B8
- Disabled: #475569

## Interactive
- Button primary: bg {primary-400}, text #0F172A, hover {primary-300}
- Button secondary: bg #1E293B, border #475569, hover bg #334155
- Input: bg #1E293B, border #475569, focus ring {primary-400}/20%
- Link: {primary-400}, hover {primary-300}, underline on hover

## Feedback
- Success: bg #064E3B, border #10B981, text #A7F3D0
- Error: bg #7F1D1D, border #EF4444, text #FECACA
- Warning: bg #78350F, border #F59E0B, text #FDE68A
- Info: bg #1E3A5F, border #3B82F6, text #BFDBFE
```

### 2.7 Confirmar Brand Kit generado

```
Brand Kit generado en doc/brand/brand_kit/:
├── SKILL.md          — Resumen para agentes (~600 tokens)
├── variables.css     — Tokens CSS (light + dark)
├── tailwind.config.js — Configuracion Tailwind con CSS vars
├── light.md          — Specs tema claro
└── dark.md           — Specs tema oscuro

¿Quieres revisar o ajustar algun archivo antes de continuar?
```

---

## Paso 3: Configurar Google Stitch

### 3.1 Verificar API Key de Stitch

```
¿Hay API Key de Stitch configurada?
├── stitch_set_api_key ya ejecutado → Continuar
├── stitch.apiKey en settings.local.json → Usar esa
└── No hay key → Preguntar al usuario:
    "Necesito tu API Key de Google Stitch para crear el proyecto y design system.
     Puedes obtenerla en: https://stitch.withgoogle.com/settings
     Introduce tu API Key:"
```

Si el usuario proporciona API Key, configurarla via MCP:

```
mcp__SpecBox-MCP__stitch_set_api_key(
  project="{project_path}",
  api_key="{api_key}"
)
```

### 3.2 Crear proyecto en Stitch

> Solo si no hay `stitch.projectId` valido en settings.

```
mcp__stitch__create_project(
  title="{Nombre del Producto}"
)
```

Guardar el `projectId` retornado para el siguiente paso.

### 3.3 Crear Design System en Stitch

**CRITICO**: El `designMd` es el campo mas importante. Stitch lo lee para guiar TODA la generacion visual. Debe ser un resumen denso y completo del brand kit.

```
mcp__stitch__create_design_system(
  projectId="{stitch_project_id}",
  designSystem={
    "displayName": "{Nombre del Producto} Design System",
    "theme": {
      "colorMode": "LIGHT",
      "headlineFont": "{FONT_ENUM}",
      "bodyFont": "{FONT_ENUM}",
      "labelFont": "{FONT_ENUM}",
      "roundness": "{ROUND_FOUR|ROUND_EIGHT|ROUND_TWELVE|ROUND_FULL}",
      "customColor": "{primary_hex}",
      "overridePrimaryColor": "{primary_hex}",
      "overrideSecondaryColor": "{secondary_hex}",
      "overrideTertiaryColor": "{accent_hex}",
      "overrideNeutralColor": "{neutral_500_hex}",
      "colorVariant": "{color_variant}",
      "designMd": "{design_md_content}"
    }
  }
)
```

**Mapeo de estetica a colorVariant:**

| Estetica | colorVariant | Razon |
|----------|-------------|-------|
| Calm Enterprise | TONAL_SPOT | Palette armonica, profesional |
| Bold Startup | VIBRANT | Colores saturados, energeticos |
| Minimal Tool | NEUTRAL | Palette restringida, funcional |
| Financial Pro | FIDELITY | Fidelidad al color elegido |
| Health & Care | TONAL_SPOT | Armonia natural, confianza |
| Developer DX | EXPRESSIVE | Colores distintos, personalidad |
| Custom | TONAL_SPOT | Default seguro |

**Contenido del `designMd`** (~2000 palabras max):

Generar un Markdown denso que incluya:

```markdown
# {Nombre del Producto} — Design Guidelines

## Brand Identity
- Product: {nombre} — {dominio}
- Aesthetic: {estetica} ({referentes})
- Visual tone: {profesional/energetico/minimal/calido/tecnico}

## Color System
- Primary: {hex} — Use for CTAs, active states, focus rings, primary actions
- Secondary: {hex} — Use for secondary buttons, tags, badges, supporting elements
- Accent: {hex} — Use for highlights, notifications, progress indicators
- Semantic: Success #10B981, Warning #F59E0B, Error #EF4444, Info #3B82F6
- Neutrals: Scale from {neutral-50} (lightest bg) to {neutral-900} (darkest text)
- RULE: Primary buttons are solid primary bg with white text. Secondary buttons are outlined with neutral border.
- RULE: Card backgrounds use neutral-50. Section alternating backgrounds use neutral-100.

## Typography
- Headings: {font-name}, bold, sizes 36/30/24/20px (h1/h2/h3/h4)
- Body: {font-name}, regular, 16px base, line-height 1.5
- Labels: {font-name}, medium, 14px, letter-spacing 0.01em
- RULE: Maximum 2 font weights per page. Bold for headings, regular for body.

## Shape & Spacing
- Border radius: {N}px base ({roundness-name})
- Buttons: {radius-md}px radius
- Cards: {radius-lg}px radius
- Inputs: {radius-md}px radius
- Spacing: 4px grid. Minimum padding inside cards: 16px. Section gaps: 48px.
- RULE: All interactive elements have at least 44px tap target.

## Component Patterns
- Cards: white bg, {radius-lg}px radius, shadow-sm, 1px border neutral-200, 24px padding
- Buttons: {radius-md}px radius, 14px font, 500 weight, 12px 24px padding
- Inputs: {radius-md}px radius, 1px border neutral-300, 12px 16px padding, focus ring 2px primary/20%
- Tables: header bg neutral-50, rows alternate white/neutral-50, 1px border-b neutral-200
- Navigation: fixed top, white bg, shadow-sm, 64px height
- Sidebar: 280px width, white bg, border-r neutral-200

## Layout Principles
- Max content width: 1280px (centered)
- Grid: 12 columns with 24px gap
- Responsive breakpoints: sm 640px, md 768px, lg 1024px, xl 1280px
- {desktop-first|mobile-first} approach

## Visual Hierarchy
1. Page title (h1) — largest, bold, primary text color
2. Section title (h2) — medium, semibold
3. Card title (h3) — smaller, semibold
4. Body text — regular weight, secondary text for descriptions

## Do NOT
- Use gradients on backgrounds (flat colors only)
- Use more than 2 font sizes in a single card
- Stack more than 3 CTAs in one viewport
- Use shadows heavier than shadow-md on cards
- Mix rounded and sharp corners in the same view
```

### 3.4 Guardar asset ID del Design System

Tras la creacion, `create_design_system` retorna un `name` con formato `assets/{asset_id}`.
Extraer el `asset_id` y guardar para siguiente paso.

### 3.5 Aplicar Design System al proyecto

Inmediatamente despues de crear el Design System, llamar a `update_design_system` para activarlo:

```
mcp__stitch__update_design_system(
  name="assets/{asset_id}",
  projectId="{stitch_project_id}",
  designSystem={...mismo objeto que en create...}
)
```

### 3.6 Confirmar con usuario

```
Google Stitch configurado:
├── Proyecto: "{Nombre}" (ID: {stitch_project_id})
├── Design System: "{Nombre} Design System" (Asset: {asset_id})
├── Color Mode: LIGHT (dark mode se implementa en codigo)
├── Font: {font_name}
├── Roundness: {roundness_name}
└── Color Variant: {variant}

¿Todo correcto?
```

---

## Paso 4: Configurar VEG Base

> Solo si no existe `doc/veg/base/` o el usuario pidio regenerar.

### 4.1 Crear estructura

```bash
mkdir -p doc/veg/base
```

### 4.2 Generar VEG base

Crear `doc/veg/base/veg-{project-slug}.md` derivando TODAS las directivas del brand kit (no inventar):

```markdown
# VEG: {Nombre del Producto} — Base

> Feature: Global (base para todas las features)
> Modo: uniforme
> Generado: {fecha}

## Contexto del Target

- **Quien**: {derivar del dominio — ej: "Profesionales financieros que gestionan inversiones"}
- **Referentes visuales**: {referentes de la estetica elegida}
- **Tolerancia visual**: {minimal / balanced / expressive — derivar de estetica}
- **Plataforma primaria**: {desktop-first / mobile-first}

## Pilar 1: Imagenes

### Estrategia de imagen

| Campo | Valor |
|-------|-------|
| Tipo | {derivar de estetica y dominio} |
| Mood | {derivar de estetica} |
| Paleta | {derivar de colores elegidos} |
| Sujetos | {derivar de dominio} |

### Prompts de imagen por seccion

| Seccion | Tipo | Prompt |
|---------|------|--------|
| Hero | {tipo} | "{prompt contextualizado al dominio y estetica}" |
| Features | {tipo} | "{prompt}" |
| Empty states | {tipo} | "{prompt}" |
| Backgrounds | {tipo} | "{prompt}" |

## Pilar 2: Motion

### Estrategia de motion

| Campo | Valor |
|-------|-------|
| Nivel | {derivar de estetica: calm→subtle, bold→moderate, minimal→subtle} |
| Personalidad | {derivar de estetica} |

### Catalogo de animaciones

| Tipo | Animacion | Duracion | Easing |
|------|-----------|----------|--------|
| page_enter | {derivar} | {N}ms | {derivar} |
| scroll_reveal | {derivar} | {N}ms | {derivar} |
| scroll_stagger_delay | — | {N}ms | — |
| hover_buttons | {derivar} | {N}ms | — |
| loading | {derivar} | — | — |
| transitions_pages | {derivar} | {N}ms | — |
| transitions_modals | {derivar} | {N}ms | — |
| feedback_success | {derivar} | — | — |
| feedback_error | {derivar} | — | — |

**Reglas de nivel:**
- subtle: SOLO page_enter + loading. Skip scroll, hover, feedback.
- moderate: Todos excepto feedback.
- expressive: Catalogo completo.

## Pilar 3: Diseno

### Estrategia de diseno

| Campo | Valor |
|-------|-------|
| Densidad | {derivar de estetica} |
| Whitespace | {derivar de estetica} |
| Separacion de secciones | {derivar de estetica} |

### Tipografia

| Campo | Valor |
|-------|-------|
| Heading weight | {derivar} |
| Body spacing | {derivar} |
| Hero scale | {derivar} |

### Jerarquia visual

| Campo | Valor |
|-------|-------|
| Estilo | {derivar de estetica y dominio} |
| CTA prominence | {derivar} |
| Data presentation | {derivar de dominio} |

## Form Factor Adaptations

### Desktop (>= 1024px)
- Layout: {derivar — ej: sidebar + main content area}
- Grid: 12 columnas, gap 24px
- Max width: 1280px centered
- Navigation: {top bar / sidebar / combined}

### Tablet (768px - 1023px)
- Layout: {derivar — ej: collapsible sidebar, stack secondary panels}
- Grid: 8 columnas, gap 16px
- Navigation: {hamburger / bottom tabs / collapsible sidebar}

### Mobile (< 768px)
- Layout: {derivar — ej: single column, bottom sheet for details}
- Grid: 4 columnas, gap 12px
- Navigation: {bottom tabs / hamburger}
- Touch targets: minimo 44px

## Resumen para inyeccion en sub-agentes (~400 tokens)

> Este bloque es lo que viaja a los sub-agentes dentro del context budget.

VEG [uniforme] Base: {Nombre del Producto}
Images: {type}, mood {mood}, palette {palette}
Motion: level {level}, personality {personality}
  - page_enter: {animation} {duration}ms {easing}
  - scroll: {animation} stagger {delay}ms
  - loading: {style}
  - transitions: {pages} {duration}ms
Design: density {density}, whitespace {whitespace}
  - hierarchy: {style}, CTA {prominence}
  - typography: heading {weight}, body {spacing}, hero {scale}
Form factors: {desktop-first|mobile-first}, breakpoints 640/768/1024/1280
Brand: {primary} + {secondary}, font {font-name}, radius {N}px
```

**Reglas de derivacion por estetica:**

| Estetica | Densidad | Whitespace | Motion Level | Hierarchy | CTA |
|----------|----------|------------|--------------|-----------|-----|
| Calm Enterprise | balanced | generous | subtle | card-based | medium |
| Bold Startup | balanced | moderate | moderate | full-bleed | high |
| Minimal Tool | compact | moderate | subtle | minimal | subtle |
| Financial Pro | compact | moderate | subtle | dashboard | medium |
| Health & Care | spacious | generous | moderate | card-based | medium |
| Developer DX | compact | moderate | subtle | dashboard | medium |

---

## Paso 5: Configurar Multi-Form-Factor y Prompt Template

### 5.1 Actualizar `settings.local.json`

Leer `.claude/settings.local.json` actual (o crear si no existe) y MERGE con:

```json
{
  "stitch": {
    "projectId": "{stitch_project_id}",
    "designSystemAssetId": "{asset_id}",
    "deviceType": "{DESKTOP|MOBILE}",
    "modelId": "GEMINI_3_PRO",
    "multiFormFactor": true,
    "formFactors": ["DESKTOP", "TABLET", "MOBILE"],
    "brandContextFile": "doc/brand/brand_kit/SKILL.md"
  }
}
```

**REGLA**: Hacer MERGE con el JSON existente, no sobrescribir. Preservar todas las keys existentes (trello, plane, acceptance, etc.).

### 5.2 Generar `doc/design/stitch-prompt-template.md`

```bash
mkdir -p doc/design
```

```markdown
# Stitch Prompt Template — {Nombre del Producto}

> Generado por /visual-setup — usar como base para TODAS las generaciones de pantalla.
> Design System Asset: {asset_id}
> Stitch Project: {stitch_project_id}

## Estructura del Prompt

Cada generacion de pantalla via `mcp__stitch__generate_screen_from_text` debe seguir esta estructura:

---

### Template

```
[SCREEN NAME]
{UC-XXX}: {nombre del use case}

[PURPOSE]
{descripcion funcional de la pantalla — que hace el usuario aqui}

[VISUAL DIRECTION]
{Pegar aqui el bloque "Resumen para inyeccion" del VEG base o del VEG de la feature}

[LAYOUT]
- Device: {DESKTOP|TABLET|MOBILE}
- Structure: {descripcion del layout — ej: "sidebar left 280px + main content area"}
- Sections: {enumerar secciones de arriba a abajo}

[CONTENT]
- Header: {que muestra}
- Main: {contenido principal}
- Sidebar/Secondary: {si aplica}
- Footer/Actions: {botones, acciones}

[COMPONENTS]
- {componente 1}: {especificacion — ej: "data table with 5 columns, sortable, paginated"}
- {componente 2}: {especificacion}

[INTERACTIONS]
- {interaccion 1}: {ej: "click row → expand detail panel right"}
- {interaccion 2}: {ej: "filter dropdown → update table in place"}

[RULES]
- ALWAYS use LIGHT MODE (dark mode is handled in code via CSS variables)
- Follow the Design System applied to this project (asset {asset_id})
- Use brand colors: primary {primary_hex}, secondary {secondary_hex}
- Font: {font_name} for all text
- Radius: {roundness_name} ({N}px)
- Minimum touch target: 44px on mobile
- Maintain 4.5:1 contrast ratio for all text
```

---

## Multi-Form-Factor Protocol

Para cada pantalla que requiera responsive, generar 3 versiones:

| # | Form Factor | Stitch deviceType | Nombre archivo |
|---|------------|-------------------|----------------|
| 1 | Desktop | DESKTOP | `{uc-id}_{screen-name}_desktop.html` |
| 2 | Tablet | TABLET | `{uc-id}_{screen-name}_tablet.html` |
| 3 | Mobile | MOBILE | `{uc-id}_{screen-name}_mobile.html` |

**Reglas:**
- Generar SIEMPRE desktop primero (es la referencia principal)
- Tablet y mobile se generan con el mismo prompt + adaptaciones de layout
- Para tablet: colapsar sidebar, reducir columnas de grid, reorganizar panels
- Para mobile: single column, bottom sheet para detalles, bottom tabs para nav
- Guardar en: `doc/design/{feature}/{uc-id}/`

## Seleccion de Modelo

| Complejidad | Modelo | Cuando usar |
|-------------|--------|-------------|
| Simple | GEMINI_3_FLASH | Pantallas con 1-3 secciones, formularios simples, paginas de confirmacion |
| Compleja | GEMINI_3_PRO | Dashboards, tablas de datos, multi-panel, pantallas con >3 secciones |

## Referencia Rapida

| Parametro | Valor |
|-----------|-------|
| Stitch Project ID | `{stitch_project_id}` |
| Design System Asset | `{asset_id}` |
| Primary Color | `{primary_hex}` |
| Secondary Color | `{secondary_hex}` |
| Font | `{font_name}` |
| Roundness | `{roundness_name}` |
| Color Mode | LIGHT (siempre) |
| Brand Context | `doc/brand/brand_kit/SKILL.md` |
| VEG Base | `doc/veg/base/veg-{slug}.md` |
```

---

## Paso 6: Actualizar CLAUDE.md del Proyecto

### 6.1 Buscar CLAUDE.md del proyecto

```bash
ls CLAUDE.md 2>/dev/null
```

Si no existe → WARNING: "No se encontro CLAUDE.md en la raiz del proyecto. Creando seccion de diseno standalone en doc/brand/README.md."

### 6.2 Insertar seccion "Sistema de Diseno"

Buscar en CLAUDE.md un lugar apropiado para insertar (despues de "Stack" o "Estructura", antes de "Para contribuir"). Si ya existe una seccion de diseno, REEMPLAZARLA.

Insertar:

```markdown
## Sistema de Diseno

> Configurado via `/visual-setup` — {fecha}

### Identidad Visual

| Campo | Valor |
|-------|-------|
| Estetica | {nombre estetica} ({referentes}) |
| Dominio | {dominio} |
| Primary | `{primary_hex}` |
| Secondary | `{secondary_hex}` |
| Font | {font_name} |
| Roundness | {roundness_name} ({N}px) |
| Device | {desktop-first / mobile-first} |

### Google Stitch

| Campo | Valor |
|-------|-------|
| Project ID | `{stitch_project_id}` |
| Design System | `{asset_id}` |
| Color Mode | LIGHT (dark mode via CSS vars) |
| Multi-Form-Factor | DESKTOP + TABLET + MOBILE |

### Brand Kit

| Archivo | Ruta |
|---------|------|
| Resumen agentes | `doc/brand/brand_kit/SKILL.md` |
| CSS Tokens | `doc/brand/brand_kit/variables.css` |
| Tailwind Config | `doc/brand/brand_kit/tailwind.config.js` |
| Light Theme | `doc/brand/brand_kit/light.md` |
| Dark Theme | `doc/brand/brand_kit/dark.md` |

### VEG & Design

| Archivo | Ruta |
|---------|------|
| VEG Base | `doc/veg/base/veg-{slug}.md` |
| Prompt Template | `doc/design/stitch-prompt-template.md` |

### Reglas de Diseno

1. Stitch genera SIEMPRE en Light Mode — dark mode se implementa en codigo con tokens CSS
2. Todo prompt de Stitch debe seguir `doc/design/stitch-prompt-template.md`
3. Cada pantalla genera 3 form factors (desktop, tablet, mobile) si `multiFormFactor: true`
4. El Design System Asset se aplica automaticamente a todas las pantallas generadas
5. El brand kit se inyecta como contexto en sub-agentes (AG-02, AG-06)
```

### 6.3 Actualizar estructura del monorepo en CLAUDE.md

Si CLAUDE.md tiene una seccion de estructura de archivos/carpetas, agregar:

```
├── doc/
│   ├── brand/
│   │   ├── brand_kit/
│   │   │   ├── SKILL.md         ← Resumen compacto para agentes
│   │   │   ├── variables.css    ← Tokens CSS (light + dark)
│   │   │   ├── tailwind.config.js ← Config Tailwind
│   │   │   ├── light.md         ← Specs tema claro
│   │   │   └── dark.md          ← Specs tema oscuro
│   │   └── brand_briefing.md    ← (opcional) briefing original
│   ├── veg/
│   │   └── base/
│   │       └── veg-{slug}.md    ← VEG base global
│   └── design/
│       └── stitch-prompt-template.md ← Template de prompts Stitch
```

---

## Paso 7: Resumen y Validacion

### 7.1 Verificar completitud

Ejecutar checklist:

```
Verificacion de /visual-setup:
├── [x] Brand Kit generado en doc/brand/brand_kit/
│   ├── [x] SKILL.md (resumen agentes)
│   ├── [x] variables.css (tokens CSS)
│   ├── [x] tailwind.config.js
│   ├── [x] light.md
│   └── [x] dark.md
├── [x] Stitch configurado
│   ├── [x] Proyecto creado (ID: {id})
│   ├── [x] Design System creado (Asset: {id})
│   └── [x] settings.local.json actualizado
├── [x] VEG base generado
│   └── [x] doc/veg/base/veg-{slug}.md
├── [x] Multi-Form-Factor configurado
│   ├── [x] settings.local.json → multiFormFactor: true
│   └── [x] doc/design/stitch-prompt-template.md
├── [x] CLAUDE.md actualizado
│   ├── [x] Seccion "Sistema de Diseno"
│   └── [x] Estructura de archivos
└── [ ] Sin campos vacios en ningun archivo
```

### 7.2 Validar que no hay campos vacios

Buscar placeholders sin resolver:

```bash
grep -r "{.*}" doc/brand/brand_kit/ doc/veg/base/ doc/design/stitch-prompt-template.md 2>/dev/null
```

Si hay campos con `{placeholder}` → ERROR: listar y pedir al usuario los valores faltantes.

### 7.3 Mostrar resumen final

```markdown
## /visual-setup completado

### Identidad Visual: {Nombre del Producto}

| Artefacto | Estado | Ubicacion |
|-----------|--------|-----------|
| Brand Kit | Generado | `doc/brand/brand_kit/` |
| Stitch Project | Creado | ID: `{stitch_project_id}` |
| Design System | Aplicado | Asset: `{asset_id}` |
| VEG Base | Generado | `doc/veg/base/veg-{slug}.md` |
| Prompt Template | Generado | `doc/design/stitch-prompt-template.md` |
| settings.local.json | Actualizado | `.claude/settings.local.json` |
| CLAUDE.md | Actualizado | `CLAUDE.md` |

### Siguiente paso

El proyecto esta listo para `/plan`. Al ejecutar `/plan`:
- Los disenos de Stitch usaran el Design System configurado
- El VEG base se inyectara como "Visual Direction" en cada prompt
- Los 3 form factors se generaran automaticamente (si multiFormFactor: true)
- Los sub-agentes (AG-02, AG-06) recibiran el brand kit como contexto
```

---

## Manejo de Errores

### Stitch API no disponible

```
¿Stitch responde?
├── SI → Continuar normalmente
└── NO → Generar TODOS los artefactos locales (brand kit, VEG, template)
    └── WARNING: "Stitch no responde. Se generaron todos los artefactos locales.
         Cuando Stitch este disponible, ejecuta /visual-setup de nuevo
         para crear el proyecto y design system remotos."
    └── Marcar en settings.local.json: "stitch.pendingSetup": true
```

### Brand Kit parcial

```
¿El brand kit existente esta completo?
├── Tiene SKILL.md + variables.css → Completo, reusar
├── Solo tiene SKILL.md → Generar variables.css, tailwind, light.md, dark.md
├── Solo tiene variables.css → Generar SKILL.md, light.md, dark.md
└── Solo tiene briefing → Parsear y generar todo
```

### Usuario cancela en medio

Todos los artefactos generados hasta el punto de cancelacion se mantienen. El usuario puede re-ejecutar `/visual-setup` y el skill detectara lo que ya existe (Paso 0) y completara lo que falta.

---

## Referencia de Enums Stitch

### Fuentes (headlineFont, bodyFont, labelFont)

| Enum | Nombre | Estilo |
|------|--------|--------|
| GEIST | Geist | Modern, clean, Vercel |
| INTER | Inter | Neutral, versatile |
| DM_SANS | DM Sans | Geometric, friendly |
| PLUS_JAKARTA_SANS | Plus Jakarta Sans | Elegant, modern |
| SPACE_GROTESK | Space Grotesk | Technical, distinctive |
| SORA | Sora | Geometric, balanced |
| IBM_PLEX_SANS | IBM Plex Sans | Corporate, reliable |
| MANROPE | Manrope | Warm, rounded |
| RUBIK | Rubik | Soft, approachable |
| SOURCE_SANS_THREE | Source Sans 3 | Clean, readable |
| MONTSERRAT | Montserrat | Bold, impactful |
| WORK_SANS | Work Sans | Professional, balanced |
| BE_VIETNAM_PRO | Be Vietnam Pro | Modern, geometric |
| EPILOGUE | Epilogue | Contemporary, editorial |
| LEXEND | Lexend | Readable, accessibility |
| NEWSREADER | Newsreader | Serif, editorial |
| NOTO_SERIF | Noto Serif | Classic, serif |
| PUBLIC_SANS | Public Sans | Government, neutral |
| SPLINE_SANS | Spline Sans | Clean, tech |
| DOMINE | Domine | Serif, formal |
| LIBRE_CASLON_TEXT | Libre Caslon Text | Serif, elegant |
| EB_GARAMOND | EB Garamond | Serif, classic |
| LITERATA | Literata | Serif, reading |
| SOURCE_SERIF_FOUR | Source Serif 4 | Serif, versatile |
| METROPOLIS | Metropolis | Geometric, urban |
| NUNITO_SANS | Nunito Sans | Rounded, friendly |
| ARIMO | Arimo | Neutral, Arial-like |
| HANKEN_GROTESK | Hanken Grotesk | Clean, modern |

### Roundness

| Enum | CSS | UI Name |
|------|-----|---------|
| ROUND_FOUR | 4px | Sharp |
| ROUND_EIGHT | 8px | Medium |
| ROUND_TWELVE | 12px | Rounded |
| ROUND_FULL | 9999px | Full/Pill |

### Color Variant

| Enum | Descripcion | Mejor para |
|------|-------------|------------|
| TONAL_SPOT | Harmonious palette from seed | Default seguro, enterprise |
| VIBRANT | Saturated, energetic | Startups, consumer |
| NEUTRAL | Restrained, functional | Minimal, tools |
| FIDELITY | True to chosen color | Financial, brand-strict |
| EXPRESSIVE | Distinct, personality | Developer, creative |
| MONOCHROME | Single hue variations | Ultra-minimal |
| CONTENT | Derived from content | Media, galleries |
| RAINBOW | Full spectrum | Playful, kids |
| FRUIT_SALAD | Colorful, varied | Fun, casual |

### Color Mode

| Enum | Nota |
|------|------|
| LIGHT | **SIEMPRE usar LIGHT** — Stitch solo genera bien en light mode |
| DARK | No usar — dark mode se implementa en codigo con CSS vars |

### Device Type

| Enum | Breakpoint |
|------|-----------|
| DESKTOP | >= 1024px |
| TABLET | 768px - 1023px |
| MOBILE | < 768px |
| AGNOSTIC | Sin breakpoint especifico |
