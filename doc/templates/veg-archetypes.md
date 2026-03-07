# VEG Archetypes — Reglas de derivacion por tipo de target

> Estas reglas son DEFAULTS que el orquestador aplica automaticamente.
> El JTBD emocional del target puede sobreescribirlas.

---

## Tabla de arquetipos

| Senal del target | Imagenes | Motion | Diseno |
|-----------------|----------|--------|--------|
| Corporate / Enterprise / +45 | Fotografia real, mood professional, cool | Subtle, ease-out, skeleton loading | Balanced, moderate whitespace, card-based |
| Startup / Tech / 25-35 | Ilustracion flat/3D, mood energy, vibrant | Moderate, spring easing, shimmer | Spacious, generous whitespace, full-bleed |
| Creative / Design / Premium | Mixed/editorial, mood premium, muted | Expressive, custom easings, morph transitions | Spacious, editorial, oversized headings |
| Consumer / Mainstream | Fotografia personas, mood confidence, warm | Moderate, ease-out, familiar patterns | Balanced, card-based, high CTA prominence |
| Gen-Z / Young / <25 | Ilustracion bold/3D, mood playful, vibrant | Expressive, bounce/spring, confetti feedback | Spacious, bold gradients, oversized hero |
| Conservador / Gobierno / Legal | Fotografia institucional, mood calm, neutral | Subtle, ningun bounce, spinner loading | Compact/balanced, tight whitespace, tables |

---

## Reglas detalladas por arquetipo

### Corporate / Enterprise / +45

```yaml
image_strategy:
  type: photography
  mood: professional
  palette: cool
  subjects: people | spaces

motion_strategy:
  level: subtle
  personality: corporate
  catalog:
    page_enter: { animation: fade-in, duration: 300, easing: ease-out }
    scroll_reveal: { animation: none }
    hover_buttons: { animation: none }
    loading: { style: skeleton }
    transitions: { pages: fade, duration: 300 }
    feedback: { success: none, error: none }

design_strategy:
  density: balanced
  whitespace: moderate
  section_separation: dividers
  typography_feel:
    heading_weight: bold
    body_spacing: standard
    hero_scale: large
  visual_hierarchy:
    style: card-based
    cta_prominence: medium
    data_presentation: tables
```

### Startup / Tech / 25-35

```yaml
image_strategy:
  type: illustration_flat
  mood: energy
  palette: vibrant
  subjects: abstract_shapes | objects

motion_strategy:
  level: moderate
  personality: friendly
  catalog:
    page_enter: { animation: slide-up, duration: 400, easing: spring }
    scroll_reveal: { animation: stagger, duration: 200, stagger_delay: 50 }
    hover_buttons: { animation: scale-1.02, duration: 150 }
    loading: { style: shimmer }
    transitions: { pages: slide, duration: 300 }
    feedback: { success: none, error: none }

design_strategy:
  density: spacious
  whitespace: generous
  section_separation: large-gap
  typography_feel:
    heading_weight: bold
    body_spacing: airy
    hero_scale: oversized
  visual_hierarchy:
    style: full-bleed
    cta_prominence: high
    data_presentation: big-numbers
```

### Creative / Design / Premium

```yaml
image_strategy:
  type: mixed
  mood: premium
  palette: muted
  subjects: spaces | objects

motion_strategy:
  level: expressive
  personality: elegant
  catalog:
    page_enter: { animation: scale-in, duration: 500, easing: ease-out }
    scroll_reveal: { animation: parallax, duration: 300, stagger_delay: 80 }
    hover_buttons: { animation: glow, duration: 200 }
    loading: { style: shimmer }
    transitions: { pages: morph, duration: 400 }
    feedback: { success: subtle-pulse, error: shake }

design_strategy:
  density: spacious
  whitespace: generous
  section_separation: gradient-flow
  typography_feel:
    heading_weight: black
    body_spacing: airy
    hero_scale: oversized
  visual_hierarchy:
    style: editorial
    cta_prominence: subtle
    data_presentation: narrative
```

### Consumer / Mainstream

```yaml
image_strategy:
  type: photography
  mood: confidence
  palette: warm
  subjects: people

motion_strategy:
  level: moderate
  personality: friendly
  catalog:
    page_enter: { animation: fade-in, duration: 300, easing: ease-out }
    scroll_reveal: { animation: fade-in-up, duration: 200, stagger_delay: 50 }
    hover_buttons: { animation: lift-shadow, duration: 150 }
    loading: { style: skeleton }
    transitions: { pages: fade, duration: 250 }
    feedback: { success: none, error: none }

design_strategy:
  density: balanced
  whitespace: moderate
  section_separation: color-blocks
  typography_feel:
    heading_weight: bold
    body_spacing: standard
    hero_scale: large
  visual_hierarchy:
    style: card-based
    cta_prominence: high
    data_presentation: big-numbers
```

### Gen-Z / Young / <25

```yaml
image_strategy:
  type: illustration_3d
  mood: playful
  palette: vibrant
  subjects: abstract_shapes

motion_strategy:
  level: expressive
  personality: playful
  catalog:
    page_enter: { animation: scale-in, duration: 400, easing: bounce }
    scroll_reveal: { animation: stagger, duration: 250, stagger_delay: 40 }
    hover_buttons: { animation: scale-1.02, duration: 100 }
    loading: { style: dots }
    transitions: { pages: slide, duration: 350 }
    feedback: { success: confetti, error: shake }

design_strategy:
  density: spacious
  whitespace: generous
  section_separation: gradient-flow
  typography_feel:
    heading_weight: black
    body_spacing: airy
    hero_scale: oversized
  visual_hierarchy:
    style: full-bleed
    cta_prominence: high
    data_presentation: big-numbers
```

### Conservador / Gobierno / Legal

```yaml
image_strategy:
  type: photography
  mood: calm
  palette: neutral
  subjects: spaces | objects

motion_strategy:
  level: subtle
  personality: corporate
  catalog:
    page_enter: { animation: fade-in, duration: 250, easing: ease-out }
    scroll_reveal: { animation: none }
    hover_buttons: { animation: color-shift, duration: 200 }
    loading: { style: spinner }
    transitions: { pages: fade, duration: 200 }
    feedback: { success: none, error: red-flash }

design_strategy:
  density: compact
  whitespace: tight
  section_separation: dividers
  typography_feel:
    heading_weight: semibold
    body_spacing: compact
    hero_scale: standard
  visual_hierarchy:
    style: dashboard
    cta_prominence: medium
    data_presentation: tables
```

---

## Sobreescritura por JTBD emocional

El JTBD emocional puede modificar los defaults del arquetipo. Ejemplos:

| Arquetipo base | JTBD emocional | Cambio |
|----------------|----------------|--------|
| Corporate +45 | "sentirse innovador" | motion → moderate, imagenes → mixed |
| Corporate +45 | "sentirse en control" | mantener defaults (ya transmite control) |
| Startup 25-35 | "sentirse serio/confiable" | imagenes → photography, motion → subtle |
| Gen-Z <25 | "sentirse profesional" | motion → moderate, diseno → balanced |
| Consumer | "sentirse premium" | palette → muted, hierarchy → editorial |

**Regla general:** El JTBD emocional ajusta max 2 pilares del arquetipo base. Nunca se ignora completamente el arquetipo.

---

## Como usa el orquestador esta tabla

1. Leer target/ICP del PRD
2. Identificar el arquetipo mas cercano por senales (edad, rol, sector, tipo de uso)
3. Aplicar defaults del arquetipo
4. Si hay JTBD emocional: evaluar si contradice algun pilar y ajustar (max 2 cambios)
5. Si hay referentes visuales: cruzar con los defaults y ajustar mood/type si difieren
6. Generar el artefacto VEG con los 3 pilares configurados
