# VEG: {target_name}

> Feature: {feature_name}
> Modo: {uniforme | por-perfil | por-icp}
> Generado: {fecha}

## Contexto del Target

- **Quien**: {descripcion del target/ICP}
- **JTBD Racional**: {que necesita resolver — solo en Modo 3}
- **JTBD Emocional**: {como necesita sentirse — solo en Modo 3}
- **Referentes visuales**: {apps/webs que usa habitualmente}
- **Tolerancia visual**: {minimal / balanced / expressive}
- **Plataforma primaria**: {mobile-first / desktop-first}

## Pilar 1: Imagenes

### Estrategia de imagen

| Campo | Valor |
|-------|-------|
| Tipo | {photography / illustration_flat / illustration_3d / abstract / mixed} |
| Mood | {confidence / energy / calm / professional / playful / premium / bold} |
| Paleta | {warm / cool / neutral / vibrant / muted} |
| Sujetos | {people / objects / spaces / data_viz / abstract_shapes} |

### Prompts de imagen por seccion

| Seccion | Tipo | Prompt |
|---------|------|--------|
| Hero | {photo/illustration/...} | "{prompt contextualizado}" |
| Features | {tipo} | "{prompt}" |
| Social proof | {tipo} | "{prompt}" |
| Empty states | {tipo} | "{prompt}" |
| Backgrounds | {tipo} | "{prompt}" |

## Pilar 2: Motion

### Estrategia de motion

| Campo | Valor |
|-------|-------|
| Nivel | {subtle / moderate / expressive} |
| Personalidad | {corporate / friendly / bold / elegant / playful} |

### Catalogo de animaciones

| Tipo | Animacion | Duracion | Easing |
|------|-----------|----------|--------|
| page_enter | {fade-in / slide-up / scale-in / none} | {N}ms | {ease-out / spring / bounce} |
| scroll_reveal | {fade-in-up / stagger / parallax / none} | {N}ms | {ease-out / spring} |
| scroll_stagger_delay | — | {N}ms | — |
| hover_buttons | {scale-1.02 / glow / color-shift / lift-shadow / none} | {N}ms | — |
| loading | {skeleton / shimmer / spinner / dots / progress} | — | — |
| transitions_pages | {fade / slide / shared-element / morph} | {N}ms | — |
| transitions_modals | {scale-fade / slide-up / none} | {N}ms | — |
| feedback_success | {checkmark-animate / confetti / subtle-pulse / none} | — | — |
| feedback_error | {shake / red-flash / none} | — | — |

**Reglas de nivel:**
- subtle: SOLO page_enter + loading. Skip scroll, hover, feedback.
- moderate: Todos excepto feedback.
- expressive: Catalogo completo.

## Pilar 3: Diseno

### Estrategia de diseno

| Campo | Valor |
|-------|-------|
| Densidad | {spacious / balanced / compact} |
| Whitespace | {generous / moderate / tight} |
| Separacion de secciones | {large-gap / dividers / color-blocks / gradient-flow} |

### Tipografia

| Campo | Valor |
|-------|-------|
| Heading weight | {black / bold / semibold} |
| Body spacing | {airy / standard / compact} |
| Hero scale | {oversized / large / standard} |

### Jerarquia visual

| Campo | Valor |
|-------|-------|
| Estilo | {card-based / full-bleed / editorial / dashboard / minimal} |
| CTA prominence | {high / medium / subtle} |
| Data presentation | {charts / big-numbers / tables / narrative} |

## Resumen para inyeccion en sub-agentes (~400 tokens)

> Este bloque es lo que viaja a los sub-agentes dentro del context budget.

```
VEG [{mode}] Target: {target_name}
Images: {type}, mood {mood}, palette {palette}
Motion: level {level}, personality {personality}
  - page_enter: {animation} {duration}ms {easing}
  - scroll: {animation} stagger {delay}ms
  - loading: {style}
  - transitions: {pages} {duration}ms
Design: density {density}, whitespace {whitespace}
  - hierarchy: {style}, CTA {prominence}
  - typography: heading {weight}, body {spacing}, hero {scale}
Image prompt hero: "{prompt corto}"
Image prompt features: "{prompt corto}"
```
