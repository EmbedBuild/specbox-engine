# VEG Motion Strategy — Investigacion y Recomendaciones

> Fecha: 2026-03-07
> Contexto: Fase 0 del feature VEG (Visual Experience Generation)
> Objetivo: Elegir las herramientas de animacion/micro-interacciones por stack

---

## Catalogo VEG a cubrir

El VEG define un catalogo abstracto de animaciones que debe traducirse a codigo:

| Tipo | Animaciones |
|------|-------------|
| page_enter | fade-in, slide-up, scale-in, none |
| scroll_reveal | fade-in-up, stagger, parallax, none |
| hover_buttons | scale-1.02, glow, color-shift, lift-shadow, none |
| loading | skeleton, shimmer, spinner, dots, progress |
| transitions | fade, slide, shared-element, morph |
| feedback | checkmark-animate, confetti, subtle-pulse, shake, red-flash, none |

Tres niveles de intensidad:
- **subtle**: solo page_enter + loading
- **moderate**: todos excepto feedback
- **expressive**: catalogo completo

---

## Flutter

### Opciones evaluadas

| Opcion | Version | Popularidad | Cobertura VEG | Claude genera bien? | Setup |
|--------|---------|-------------|---------------|---------------------|-------|
| **flutter_animate** | v4.5.2 | 4.15k likes, Flutter Favorite | Completa (90%) | Excelente | 1 linea pubspec |
| Built-in Flutter | N/A | Nativo | Parcial | Si, pero verboso | Cero deps |
| flutter_micro_interactions | v0.0.2 | 40 likes | Parcial | Riesgoso | 1 linea |
| Rive | Latest | Profesional | Completa | NO genera assets | Editor externo |
| Lottie | Latest | Estandar | Completa (si tienes JSONs) | NO genera JSONs | Assets externos |

### Recomendacion: `flutter_animate` v4.5.2

**Justificacion:**

1. **API perfecta para Claude.** Patron chainable declarativo:
```dart
Text("Hello").animate()
  .fadeIn(duration: 600.ms)
  .then(delay: 200.ms)
  .scale(begin: Offset(0.8, 0.8), end: Offset(1, 1))
```

2. **Stagger nativo:**
```dart
AnimateList(
  interval: 400.ms,
  effects: [FadeEffect(duration: 300.ms), SlideEffect()],
  children: items,
)
```

3. **Catalogo como constantes reutilizables:**
```dart
// veg_motion_catalog.dart
const vegPageEnterFadeIn = [
  FadeEffect(duration: Duration(milliseconds: 300)),
  SlideEffect(begin: Offset(0, 0.1), end: Offset.zero),
];

const vegScrollStagger = [
  FadeEffect(duration: Duration(milliseconds: 200)),
  SlideEffect(begin: Offset(0, 0.15)),
];

// Uso:
myWidget.animate(effects: vegPageEnterFadeIn);
```

4. **Efectos incluidos:** fade, scale, slide, blur, shake, shimmer, shadow, crossfade, color/tint, GLSL shaders

5. **Maduro y estable.** Flutter Favorite, publisher verificado (gskinner.com), 715k descargas

**Complementos:**
- `Hero` widget (built-in Flutter) para shared-element transitions
- `lottie` package solo para consumir assets pre-hechos (confetti, checkmark) descargados de LottieFiles

**Descartados:**
- Built-in Flutter: demasiado verboso (30-50 lineas por animacion con StatefulWidget + TickerProvider)
- flutter_micro_interactions: inmaduro (v0.0.2, 219 descargas)
- Rive: requiere diseñador externo creando assets en editor visual
- Lottie: Claude no puede crear JSONs de Lottie, solo consumirlos

### Traduccion del catalogo VEG a flutter_animate

| VEG | flutter_animate | Nivel |
|-----|-----------------|-------|
| page_enter: fade-in | `.fadeIn(duration: 300.ms)` | subtle |
| page_enter: slide-up | `.slide(begin: Offset(0, 0.1)).fadeIn()` | subtle |
| page_enter: scale-in | `.scale(begin: Offset(0.9, 0.9)).fadeIn()` | subtle |
| scroll_reveal: fade-in-up | `.fadeIn().slide(begin: Offset(0, 0.15))` | moderate |
| scroll_reveal: stagger | `AnimateList(interval: 50.ms, effects: [...])` | moderate |
| hover_buttons: scale | `.scale(end: Offset(1.02, 1.02))` con MouseRegion | moderate |
| hover_buttons: lift-shadow | `.shadow(...)` con MouseRegion | moderate |
| loading: shimmer | `.shimmer(duration: 1.s)` | subtle |
| loading: skeleton | Container + `.shimmer()` | subtle |
| transitions: fade | PageRouteBuilder + `.fadeIn()` | moderate |
| transitions: shared-element | Hero widget (built-in) | moderate |
| feedback: shake | `.shake()` | expressive |
| feedback: confetti | Lottie asset pre-hecho | expressive |
| feedback: subtle-pulse | `.scale(begin: 1.0, end: 1.05).then().scale(end: 1.0)` repeat | expressive |

### Dependencias a anadir en pubspec.yaml

```yaml
dependencies:
  flutter_animate: ^4.5.2
  # Solo si se necesitan animaciones complejas pre-hechas (confetti, checkmark):
  lottie: ^3.3.1
```

---

## React

### Opciones evaluadas

| Opcion | Version | Descargas/sem | Cobertura VEG | Claude genera bien? | Setup |
|--------|---------|---------------|---------------|---------------------|-------|
| **motion** (ex Framer Motion) | v12.35.0 | 3.6M | Completa | Excelente | 1 comando npm |
| CSS Transitions | N/A | Nativo | Parcial (subtle+moderate) | Excelente | Cero deps |
| GSAP | v3.x | 1.47M | Completa | Si, con cuidado | 2 paquetes |
| React Spring | v10.x | 788k | Parcial | Parcial | 1 paquete |
| Motion One | - | Fusionado con Motion | N/A | N/A | N/A |

### Recomendacion: `motion` v12.35.0

**Justificacion:**

1. **API declarativa ideal para Claude:**
```jsx
<motion.div
  initial={{ opacity: 0, y: 20 }}
  animate={{ opacity: 1, y: 0 }}
  exit={{ opacity: 0 }}
  transition={{ duration: 0.3 }}
/>
```

2. **Variants como catalogo reutilizable:**
```js
// vegMotionCatalog.js
export const vegPageEnter = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.3 } },
};

export const vegStaggerContainer = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.05 } },
};

export const vegHoverScale = {
  whileHover: { scale: 1.02 },
  transition: { type: "spring", stiffness: 300 },
};
```

3. **Features unicos que ningun competidor tiene:**
   - `AnimatePresence` para exit animations
   - `layoutId` para shared-element transitions
   - `useScroll` + `useTransform` para parallax
   - `whileHover`, `whileTap` para gestures

4. **Estandar de facto.** 3.6M descargas semanales, 30.7k stars. Maxima documentacion y ejemplos.

**Complemento:** CSS Transitions para hover effects ultra-simples (color-shift en `:hover`)

**Descartados:**
- GSAP: overkill para apps, API imperativa mas propensa a errores de cleanup en React
- React Spring: menor DX, sin AnimatePresence/layoutId
- Motion One: se fusiono con Motion, ya no es libreria separada

### Traduccion del catalogo VEG a motion

| VEG | motion (React) | Nivel |
|-----|----------------|-------|
| page_enter: fade-in | `initial={{ opacity: 0 }} animate={{ opacity: 1 }}` | subtle |
| page_enter: slide-up | `initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}` | subtle |
| page_enter: scale-in | `initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }}` | subtle |
| scroll_reveal: fade-in-up | `whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}` | moderate |
| scroll_reveal: stagger | `staggerChildren: 0.05` en variant container | moderate |
| scroll_reveal: parallax | `useScroll()` + `useTransform()` | moderate |
| hover_buttons: scale | `whileHover={{ scale: 1.02 }}` | moderate |
| hover_buttons: lift-shadow | `whileHover={{ y: -2, boxShadow: "..." }}` | moderate |
| loading: shimmer | `animate={{ opacity: [0.5, 1] }} transition={{ repeat: Infinity }}` | subtle |
| loading: skeleton | Gradient animado con `background-position` | subtle |
| transitions: fade | `AnimatePresence` + `exit={{ opacity: 0 }}` | moderate |
| transitions: shared-element | `layoutId="shared-id"` | moderate |
| feedback: shake | `animate={{ x: [0, -10, 10, -10, 0] }}` | expressive |
| feedback: confetti | Lib externa (canvas-confetti) | expressive |
| feedback: subtle-pulse | `animate={{ scale: [1, 1.05, 1] }} transition={{ repeat: 2 }}` | expressive |

### Dependencias a anadir en package.json

```json
{
  "dependencies": {
    "motion": "^12.35.0"
  },
  "devDependencies": {}
}
```

Solo si se necesita confetti: `canvas-confetti` (~6KB)

---

## Resumen ejecutivo

| Stack | Herramienta principal | Version | Complemento | Bundle | Generacion Claude |
|-------|----------------------|---------|-------------|--------|-------------------|
| **Flutter** | `flutter_animate` | v4.5.2 | Hero (built-in) + Lottie (assets) | Minimo | Excelente (chainable) |
| **React** | `motion` | v12.35.0 | CSS hovers triviales | ~85KB gzip | Excelente (declarativo) |

**Filosofia comun:** API declarativa, composable, definible como catalogo de constantes. Claude Code genera codigo correcto y mantenible con ambas.

**Riesgos:**
1. **Hover en mobile:** Los efectos hover no aplican en touch. Los sub-agentes deben usar `whileTap` en mobile.
2. **Performance en listas largas:** Stagger con muchos items puede causar jank. Limitar a 10-15 items visibles.
3. **Shared-element (morph):** En Flutter requiere Hero widget con rutas nombradas. En React requiere `layoutId` con `AnimatePresence`. Ambos necesitan planning cuidadoso.

**Mitigaciones:**
- El catalogo VEG incluye `none` como opcion para cada tipo de animacion
- El nivel `subtle` deshabilita scroll_reveal, hover y feedback — safe default
- El sub-agente AG-02 recibe instrucciones explicitas de respetar el nivel y no inventar animaciones
