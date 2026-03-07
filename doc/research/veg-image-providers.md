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

| Criterio | Freepik (Oficial) | OpenAI (SureScale) | lansespirit | Hugging Face |
|---|---|---|---|---|
| **Stars** | 30 | 97 | 49 | N/A (remoto oficial) |
| **Transporte** | Remote HTTP | stdio | stdio + SSE + HTTP | Remote HTTP |
| **Calidad** | Profesional (Mystic) | Top-tier (GPT-Image-1.5) | Top-tier (multi) | Variable |
| **Image editing** | No | Si | Si (via OpenAI) | No |
| **Stock search** | Si (millones) | No | No | No |
| **Texto en imagen** | Bueno | Excelente | Excelente (GPT) | Bueno (Qwen) |
| **Resolucion max** | 4K | 1792x1024 | 2048x2048 | Variable |
| **Coste/imagen** | Pay-per-use | $0.005-0.19 | $0.02-0.19 | Gratis (limites) |
| **Madurez** | Alta (empresa) | Alta (97 stars) | Media (49 stars) | Alta (oficial HF) |

---

## Recomendacion

### Provider PRIMARIO: Freepik MCP (Oficial Remote)

**Justificacion:**
1. **Stock search + generacion AI** en un solo MCP — buscar en millones de recursos existentes Y generar cuando no hay match
2. **Transporte remoto oficial** — sin instalacion local, configuracion minima
3. **Calidad profesional Mystic** — curado por profesionales, hasta 4K
4. **Mantenido por empresa** (Freepik S.L.) — no es repo community
5. **Clasificacion AI incluida** — catalogar imagenes generadas

**Configuracion MCP:**
```json
{
  "mcpServers": {
    "freepik": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://api.freepik.com/mcp", "--header", "x-freepik-api-key:${FREEPIK_API_KEY}"]
    }
  }
}
```

### Provider FALLBACK: lansespirit/image-gen-mcp (OpenAI + Gemini Imagen 4)

**Justificacion:**
1. **Multi-provider** — GPT-Image-1 + Imagen 4 Ultra, los dos mejores motores
2. **Image editing** — inpainting, outpainting (Freepik no lo ofrece)
3. **Texto excepcional** — GPT-Image-1.5 para assets con texto legible
4. **Triple transporte** — stdio + SSE + HTTP
5. **Mejor precio/calidad** — Imagen 4 Ultra a $0.06/imagen

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

### PROTOTIPADO (opcional): Hugging Face MCP

Para testing y comparativas rapidas sin coste. No recomendado para produccion.

### Arquitectura VEG de imagenes

```
VEG Image Pipeline
├── 1. Buscar en stock (Freepik search_resources)
│   ├── Match encontrado → download_resource → usar
│   └── Sin match → siguiente paso
├── 2. Generar con Mystic (Freepik generate_image)
│   ├── Exito → guardar en doc/veg/{feature}/assets/
│   └── Fallo → fallback
├── 3. Fallback: lansespirit
│   ├── Imagen compleja con texto → GPT-Image-1
│   ├── Fotorrealismo puro → Imagen 4 Ultra
│   └── Fallo → documentar prompt para generacion manual
└── 4. Registrar en image_prompts.md
```

---

## Descartados

| Provider | Razon |
|----------|-------|
| Replicate/GongRzhe | Repo ARCHIVADO (muerto) |
| WritingMate | 9 stars, 779 downloads, riesgo abandono |
| Hugging Face (produccion) | Colas, limites ZeroGPU, no fiable |
| chug2k/gemini-imagen4 | 3 stars, lansespirit ya incluye Imagen 4 |
