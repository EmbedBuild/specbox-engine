# VEG Image Providers — Investigacion y Recomendaciones

> Fecha: 2026-03-07
> Contexto: Fase 0 del feature VEG (Visual Experience Generation)
> Objetivo: Elegir el MCP de generacion de imagenes para el sistema VEG

---

## Criterios de evaluacion

| Criterio | Peso | Descripcion |
|----------|------|-------------|
| Calidad de output | Alto | Imagenes profesionales, no "AI generica" |
| Control de estilo | Alto | Mood, paleta, tipo (foto vs ilustracion vs 3D) |
| Formatos y resoluciones | Medio | Aspect ratios variados, 2K/4K, PNG/WebP |
| Madurez del MCP | Medio | Estable, mantenimiento activo, docs claras |
| Coste por imagen | Medio | Pricing razonable para batch (5-15 imgs/proyecto) |
| Integracion Claude Code | Alto | MCP stdio/remote, compatible con nuestro stack |
| Stock search + Generacion | Bonus | Buscar en stock Y generar con IA |

---

## Providers evaluados

### 0. Canva MCP (Oficial — SELECCIONADO como PRIMARY)

**URL:** Remote MCP via `npx -y mcp-remote@latest https://mcp.canva.com/mcp`
**Transporte:** Remote (Streamable HTTP) — MCP oficial mantenido por Canva

**Tools MCP:**
- `generate-design` — genera diseños completos con AI (Magic Media incluido en Premium)
- `export-design` — exporta como PNG/PDF a resoluciones personalizadas
- `search-designs` — busca en el workspace del usuario
- `resize-design` — cambia dimensiones/aspect ratio
- `get-design` — metadata de diseños existentes

**Calidad:** Profesional. Canva Design Model entiende estructura, layers, branding, jerarquia visual.
**Control de estilo:** Mood, paleta, tipo de contenido via prompt natural. Respeta Brand Kit si existe.
**Pricing:** **€0 adicional** con suscripcion Canva Pro (€12/mes) o Premium. Generacion ilimitada.
**Auth:** OAuth automatico — abre navegador, login con cuenta Canva, autorizar. Sin API key manual.
**Ventaja unica:** Genera diseños editables con layers (no fotos planas), exporta como PNG. Magic Media (text-to-image) incluido en Premium.
**Limitacion:** Genera diseños (canvas con layers), no fotos sueltas hiperrealistas. Exportar aplana a PNG. Para fotorrealismo puro, el fallback (lansespirit/OpenAI) es superior.

**Configuracion MCP:**
```json
{
  "mcpServers": {
    "canva": {
      "command": "npx",
      "args": ["-y", "mcp-remote@latest", "https://mcp.canva.com/mcp"]
    }
  }
}
```

### 1. Freepik MCP (Oficial)

**Repo:** [freepik-company/freepik-mcp](https://github.com/freepik-company/freepik-mcp) — 30 stars, Python
**Transporte:** Remote (Streamable HTTP) via `npx -y mcp-remote https://api.freepik.com/mcp`

**Tools MCP:**
- `search_resources` — stock photos, vectors, PSDs, iconos (millones de recursos)
- `generate_image` — Mystic AI (basado en Flux, curado por profesionales)
- `download_resource` — descarga directa
- `check_status` — generacion asincrona
- Clasificacion AI de imagenes

**Calidad:** Profesional. Mystic curado por fotografos y artistas VFX. Hasta 4K.
**Control de estilo:** Modo realism, creative detailing, aspect ratios multiples.
**Pricing:** Pay-per-use via API. Trial credits gratis.
**Ventaja unica:** UNICO MCP que combina stock search + generacion AI + clasificacion en uno.

### 2. OpenAI Image MCP (GPT-Image-1)

**Repo:** [SureScaleAI/openai-gpt-image-mcp](https://github.com/SureScaleAI/openai-gpt-image-mcp) — 97 stars, TypeScript
**Transporte:** stdio

**Tools MCP:**
- `generate_image` — text-to-image (GPT-Image-1, GPT-Image-1.5, DALL-E 3)
- `edit_image` — inpainting, outpainting, compositing

**Calidad:** Top-tier. GPT-Image-1.5 lidera benchmarks (LM Arena 1264). Excelente texto en imagen.
**Control de estilo:** vivid/natural, background transparency, quality tiers.
**Pricing:** $0.005 (mini) a $0.19 (high) por imagen 1024x1024.

### 3. lansespirit/image-gen-mcp (Multi-provider)

**Repo:** [lansespirit/image-gen-mcp](https://github.com/lansespirit/image-gen-mcp) — 49 stars, Python
**Transporte:** stdio + SSE + Streamable HTTP

**Providers:** OpenAI (GPT-Image-1) + Google Imagen 4/Ultra/3
**Ventaja:** Multi-provider con triple transporte. Imagen 4 Ultra a $0.06/imagen.

### 4. Replicate MCP (Flux)

**Repo:** [GongRzhe/Image-Generation-MCP-Server](https://github.com/GongRzhe/Image-Generation-MCP-Server) — 50 stars
**Estado:** ARCHIVADO (read-only) desde marzo 2026. **DESCARTADO.**

### 5. Hugging Face MCP

**URL:** `https://huggingface.co/mcp?login` (Remote)
**Modelos:** FLUX.1 Krea, Qwen-Image, FLUX.1-schnell
**Pricing:** Gratis con limites (ZeroGPU credits)
**Limitacion:** Colas posibles, dependencia de disponibilidad de Spaces.

### 6. Google Gemini Imagen 4

**Via** lansespirit/image-gen-mcp (incluido arriba)
**Modelos:** Imagen 4.0, 4.0 Fast, 4.0 Ultra
**Pricing:** $0.02-0.06/imagen. Mejor precio/calidad del mercado.

### 7. WritingMate ImageGen MCP

**Repo:** [writingmate/imagegen-mcp](https://github.com/writingmate/imagegen-mcp) — 9 stars, 779 downloads
**Estado:** Baja traccion. **DESCARTADO** por riesgo de abandono.

---

## Tabla comparativa

| Criterio | Canva (Oficial) | Freepik (Oficial) | OpenAI (SureScale) | lansespirit | Hugging Face |
|---|---|---|---|---|---|
| **Transporte** | Remote HTTP | Remote HTTP | stdio | stdio + SSE + HTTP | Remote HTTP |
| **Calidad** | Profesional (Design Model) | Profesional (Mystic) | Top-tier (GPT-Image-1.5) | Top-tier (multi) | Variable |
| **AI generation** | Si (Magic Media) | Si (Mystic) | Si | Si | Si |
| **Design layouts** | Si (layers editables) | No | No | No | No |
| **Image editing** | No (via Canva web) | No | Si | Si (via OpenAI) | No |
| **Stock search** | Si (Canva Elements) | Si (millones) | No | No | No |
| **Texto en imagen** | Bueno | Bueno | Excelente | Excelente (GPT) | Bueno (Qwen) |
| **Export PNG** | Si (`export-design`) | Si | Si | Si | Variable |
| **Coste/imagen** | **€0 (suscripcion)** | Pay-per-use | $0.005-0.19 | $0.02-0.19 | Gratis (limites) |
| **Auth** | OAuth (browser) | API key | API key | API key | OAuth |
| **Madurez** | Alta (empresa, MCP oficial) | Alta (empresa) | Alta (97 stars) | Media (49 stars) | Alta (oficial HF) |

---

## Recomendacion (ACTUALIZADA 2026-03-07)

### Provider PRIMARIO: Canva MCP (Oficial Remote)

**Justificacion:**
1. **€0 adicional** — incluido en suscripcion Canva Pro/Premium que ya se tiene
2. **MCP oficial** mantenido por Canva — Remote HTTP, zero config local
3. **OAuth automatico** — sin API keys, sin billing adicional
4. **Magic Media incluido** — text-to-image integrado en Premium
5. **Diseños editables** — si necesitas retocar algo, abres en Canva web
6. **Export como PNG** — `export-design` aplana layers a imagen final usable
7. **Stock de Canva Elements** — millones de fotos, ilustraciones, iconos incluidos

**Configuracion MCP:**
```json
{
  "mcpServers": {
    "canva": {
      "command": "npx",
      "args": ["-y", "mcp-remote@latest", "https://mcp.canva.com/mcp"]
    }
  }
}
```

**Flujo: generate-design → export-design → PNG**
```
1. Llamar generate-design con prompt VEG (ej: "1920x1080 hero image, professional...")
2. Canva genera diseño con AI (Magic Media + Design Model + stock elements)
3. Llamar export-design → PNG a resolucion deseada
4. Guardar en doc/veg/{feature}/assets/{id}.png
```

**Limitacion conocida:** Para fotorrealismo hiperrealista tipo "persona real en oficina" donde se necesita calidad fotografica pura, el fallback (lansespirit/GPT-Image-1) es superior. Canva es excelente para ilustraciones, banners, hero images con composicion, iconos y backgrounds.

### Provider FALLBACK: lansespirit/image-gen-mcp (OpenAI + Gemini Imagen 4)

**Justificacion:**
1. **Fotorrealismo superior** — GPT-Image-1.5 y Gemini Imagen 4 Ultra
2. **Texto excepcional** — GPT-Image-1.5 para assets con texto legible
3. **Image editing** — inpainting, outpainting
4. **Triple transporte** — stdio + SSE + HTTP

**Configuracion MCP:**
```json
{
  "mcpServers": {
    "image-gen": {
      "command": "python",
      "args": ["-m", "image_gen_mcp"],
      "env": {
        "OPENAI_API_KEY": "${OPENAI_API_KEY}",
        "GOOGLE_API_KEY": "${GOOGLE_API_KEY}"
      }
    }
  }
}
```

### Provider ALTERNATIVO: Freepik MCP

Util para proyectos donde se prefiere stock-first search + Mystic AI. Requiere plan de pago de Freepik.

### Arquitectura VEG de imagenes

```
VEG Image Pipeline
├── 1. Canva generate-design (primary — €0)
│   ├── Prompt VEG → diseño con AI → export PNG
│   ├── Exito → guardar en doc/veg/{feature}/assets/
│   └── Fallo o no disponible → fallback
├── 2. Fallback: lansespirit (de pago)
│   ├── Imagen con texto legible → GPT-Image-1
│   ├── Fotorrealismo puro → Imagen 4 Ultra
│   └── Fallo → PENDING_IMAGES.md
└── 3. Registrar en image_prompts.md
```

---

## Descartados

| Provider | Razon |
|----------|-------|
| Replicate/GongRzhe | Repo ARCHIVADO (muerto) |
| WritingMate | 9 stars, 779 downloads, riesgo abandono |
| Hugging Face (produccion) | Colas, limites ZeroGPU, no fiable |
| chug2k/gemini-imagen4 | 3 stars, lansespirit ya incluye Imagen 4 |
