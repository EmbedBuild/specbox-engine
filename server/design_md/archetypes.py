"""Canonical VEG archetypes (v3.9) translated into DESIGN.md defaults.

When the generator can't infer values from project inputs, it falls back
to the archetype's defaults. The 6 archetypes correspond 1:1 to those
documented in ``doc/templates/veg-archetypes.md``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ArchetypeId(str, Enum):
    CORPORATE = "corporate"
    STARTUP = "startup"
    CREATIVE = "creative"
    CONSUMER = "consumer"
    GEN_Z = "gen_z"
    GOV = "gov"


def default_archetype() -> ArchetypeId:
    return ArchetypeId.STARTUP


@dataclass(frozen=True)
class Archetype:
    palette: dict
    typography: dict
    rounded: dict
    spacing: dict
    components: dict
    tone: str
    color_guidance: str
    typography_guidance: str
    layout_guidance: str
    elevation_guidance: str
    shapes_guidance: str
    components_guidance: str
    dos: list[str] = field(default_factory=list)
    donts: list[str] = field(default_factory=list)


def _typo(family: str = "Inter, sans-serif") -> dict:
    return {
        "fontFamily": {"heading": family, "body": family},
        "fontSize": {"h1": "32px", "h2": "24px", "h3": "20px", "body": "16px", "caption": "13px"},
        "fontWeight": {"regular": 400, "medium": 500, "semibold": 600, "bold": 700},
        "lineHeight": {"tight": 1.2, "normal": 1.5, "relaxed": 1.75},
    }


def _spacing() -> dict:
    return {"xs": "4px", "sm": "8px", "md": "16px", "lg": "24px", "xl": "32px", "xxl": "48px"}


def _components_baseline() -> dict:
    return {
        "button_primary": {
            "backgroundColor": "{colors.primary}",
            "textColor": "#FFFFFF",
            "rounded": "{rounded.md}",
            "padding": "{spacing.sm} {spacing.md}",
        },
        "card": {
            "backgroundColor": "{colors.surface}",
            "rounded": "{rounded.lg}",
            "padding": "{spacing.lg}",
        },
        "input": {
            "backgroundColor": "{colors.background}",
            "textColor": "{colors.text_primary}",
            "rounded": "{rounded.md}",
            "padding": "{spacing.sm} {spacing.md}",
        },
    }


# ── Archetype definitions ──────────────────────────────────────────────

ARCHETYPES: dict[ArchetypeId, Archetype] = {
    ArchetypeId.CORPORATE: Archetype(
        palette={
            "primary": "#0B5394",
            "primary_hover": "#093F73",
            "background": "#FFFFFF",
            "surface": "#F4F6F8",
            "text_primary": "#1A1A1A",
            "text_secondary": "#5F6B7A",
            "border": "#D8DEE6",
            "error": "#B00020",
            "success": "#1B5E20",
            "warning": "#A86200",
        },
        typography=_typo("Roboto, sans-serif"),
        rounded={"sm": "2px", "md": "4px", "lg": "6px", "full": "9999px"},
        spacing=_spacing(),
        components=_components_baseline(),
        tone="Sobrio, autoritativo, factual. Sin lenguaje coloquial.",
        color_guidance="Paleta restringida; usar el primary únicamente para CTAs principales y elementos de navegación primaria.",
        typography_guidance="Jerarquía estricta: H1 una vez por pantalla. Cuerpo legible a 16px sin excepción.",
        layout_guidance="Densidad media-alta. Grid de 12 columnas. Whitespace funcional, no decorativo.",
        elevation_guidance="Sombras mínimas (0-2dp). Cards con borde antes que sombra.",
        shapes_guidance="Bordes ligeramente redondeados. Sin formas decorativas.",
        components_guidance="Botones rectangulares, inputs con etiqueta superior. Tablas son ciudadanos de primera clase.",
        dos=[
            "Mantener jerarquía visual clara con tipografía",
            "Usar primary únicamente para acciones principales",
            "Preferir tablas y formularios estructurados sobre cards decorativos",
        ],
        donts=[
            "Gradientes, neon, glow",
            "Iconografía ilustrada o cartoon",
            "Tipografías display o decorativas",
        ],
    ),
    ArchetypeId.STARTUP: Archetype(
        palette={
            "primary": "#5B5BD6",
            "primary_hover": "#4747B8",
            "background": "#FFFFFF",
            "surface": "#F8F9FB",
            "text_primary": "#0F172A",
            "text_secondary": "#64748B",
            "border": "#E2E8F0",
            "error": "#DC2626",
            "success": "#16A34A",
            "warning": "#D97706",
        },
        typography=_typo("Inter, sans-serif"),
        rounded={"sm": "4px", "md": "8px", "lg": "12px", "full": "9999px"},
        spacing=_spacing(),
        components=_components_baseline(),
        tone="Moderno, claro, accesible. Tono profesional pero cercano.",
        color_guidance="Paleta moderna con un único color de marca. Reservar para CTAs y estados activos.",
        typography_guidance="Inter o equivalente sans-serif moderna. Pesos 400 y 600 son los workhorses.",
        layout_guidance="Densidad media. Whitespace generoso. Grid responsive 12 columnas con breakpoints multi-form-factor.",
        elevation_guidance="Sombras suaves (4-8dp) en cards y modales para definir jerarquía sin ruido.",
        shapes_guidance="Bordes 8-12px. Iconos line-style consistentes (Lucide, Phosphor).",
        components_guidance="Botones primarios y secundarios con jerarquía clara. Cards como contenedor principal.",
        dos=[
            "Whitespace generoso, no temer dejar respirar el contenido",
            "CTA primario único y visible por pantalla",
            "Estados (hover, focus, disabled) consistentes en toda la app",
        ],
        donts=[
            "Densidad tipo dashboard corporativo",
            "Más de un acento de color por pantalla",
            "Iconos rellenos mezclados con line-style en la misma vista",
        ],
    ),
    ArchetypeId.CREATIVE: Archetype(
        palette={
            "primary": "#FF4F8B",
            "primary_hover": "#E03B74",
            "background": "#FAFAFA",
            "surface": "#FFFFFF",
            "text_primary": "#111111",
            "text_secondary": "#5A5A5A",
            "border": "#EFEFEF",
            "error": "#FF3B30",
            "success": "#34C759",
            "warning": "#FF9500",
        },
        typography=_typo("Manrope, Inter, sans-serif"),
        rounded={"sm": "8px", "md": "16px", "lg": "24px", "full": "9999px"},
        spacing=_spacing(),
        components=_components_baseline(),
        tone="Expresivo, audaz, con personalidad. Tipografía y color son protagonistas.",
        color_guidance="Permite acentos saturados. El primary puede aparecer en background de bloques hero.",
        typography_guidance="Tipografía display para H1. Cuerpo siempre legible (≥16px).",
        layout_guidance="Density baja. Layouts asimétricos permitidos en hero. Cards con dimensiones variables.",
        elevation_guidance="Sombras pronunciadas o nulas — evita el medio término. Layered depth en hero.",
        shapes_guidance="Bordes muy redondeados. Formas decorativas (blobs, líneas, splatter) en headers.",
        components_guidance="Botones con personalidad: redondeados o pill. Inputs grandes con label flotante.",
        dos=[
            "Apostar por una imagen hero impactante",
            "Tipografía display selectiva en headlines",
            "Mostrar trabajo/portfolio con respiración entre items",
        ],
        donts=[
            "Plantilla genérica de SaaS sin alma visual",
            "Stock photography genérica",
            "CTA tímidos o escondidos",
        ],
    ),
    ArchetypeId.CONSUMER: Archetype(
        palette={
            "primary": "#E8725A",
            "primary_hover": "#D4654E",
            "background": "#FFFFFF",
            "surface": "#FFF8F4",
            "text_primary": "#1F1B16",
            "text_secondary": "#7A6E62",
            "border": "#EFE4D9",
            "error": "#D7263D",
            "success": "#3CAEA3",
            "warning": "#E8AB1D",
        },
        typography=_typo("Inter, sans-serif"),
        rounded={"sm": "6px", "md": "12px", "lg": "20px", "full": "9999px"},
        spacing=_spacing(),
        components=_components_baseline(),
        tone="Cálido, cercano, confiable. Lenguaje claro de consumidor.",
        color_guidance="Tonos cálidos con buen contraste. Reservar primary para CTAs de compra/conversión.",
        typography_guidance="Sans-serif friendly. Tamaños generosos en mobile.",
        layout_guidance="Densidad media-baja. Mobile-first. Cards de producto con imagen como héroe.",
        elevation_guidance="Sombras muy suaves. Cards con borde tenue para definir.",
        shapes_guidance="Esquinas redondeadas (12-20px) para suavidad. Iconos amistosos.",
        components_guidance="Botones grandes y táctiles en mobile. Inputs con etiqueta arriba siempre.",
        dos=[
            "Mobile-first sin compromiso",
            "Imágenes auténticas, no stock",
            "Microcopy cercano y útil",
        ],
        donts=[
            "Densidad de información tipo dashboard",
            "Términos técnicos sin traducir a beneficios",
            "Pop-ups intrusivos",
        ],
    ),
    ArchetypeId.GEN_Z: Archetype(
        palette={
            "primary": "#9B5CFF",
            "primary_hover": "#7E3FE0",
            "background": "#0E0B1A",
            "surface": "#161126",
            "text_primary": "#F4F0FF",
            "text_secondary": "#B4A7DA",
            "border": "#2B2240",
            "error": "#FF5C8A",
            "success": "#3DDC97",
            "warning": "#FFB444",
        },
        typography=_typo("Space Grotesk, Inter, sans-serif"),
        rounded={"sm": "6px", "md": "14px", "lg": "22px", "full": "9999px"},
        spacing=_spacing(),
        components=_components_baseline(),
        tone="Directo, irreverente, con humor. Energía alta. Sin condescendencia.",
        color_guidance="Dark mode por defecto. Acentos neón sobre fondo oscuro. Primary muy saturado.",
        typography_guidance="Tipografías geométricas o mono para detalle. Headlines grandes y rotundos.",
        layout_guidance="Densidad media. Grid quebrado permitido. Bento grids son trend, considerar uso.",
        elevation_guidance="Glow en lugar de sombra clásica. Layered depth con blur.",
        shapes_guidance="Stickers, badges, emoji-style icons. Bordes muy redondeados o duros, sin medio.",
        components_guidance="Botones pill con glow. Inputs con underline animado. Toasts con personalidad.",
        dos=[
            "Dark mode pulido, no negro plano",
            "Microinteracciones generosas",
            "Lenguaje meme-aware sin forzar",
        ],
        donts=[
            "Estética corporativa boomer",
            "Stock photography genérica",
            "CTA tímidos",
        ],
    ),
    ArchetypeId.GOV: Archetype(
        palette={
            "primary": "#1F4E8C",
            "primary_hover": "#173A6B",
            "background": "#FFFFFF",
            "surface": "#F2F4F7",
            "text_primary": "#0E1A2B",
            "text_secondary": "#54667A",
            "border": "#C9D1DA",
            "error": "#9F1A1A",
            "success": "#1F6F43",
            "warning": "#8B5A00",
        },
        typography=_typo("Source Sans Pro, sans-serif"),
        rounded={"sm": "2px", "md": "4px", "lg": "6px", "full": "9999px"},
        spacing=_spacing(),
        components=_components_baseline(),
        tone="Formal, accesible, neutro. Lenguaje claro y procedimental.",
        color_guidance="Paleta institucional sobria. Cumplir contraste WCAG AAA donde sea posible.",
        typography_guidance="Sans-serif accesibles (Source Sans Pro, Atkinson Hyperlegible). Cuerpo ≥16px.",
        layout_guidance="Densidad media. Lectura lineal priorizada. Formularios largos bien segmentados.",
        elevation_guidance="Sombras mínimas. Bordes y separadores definen jerarquía.",
        shapes_guidance="Esquinas casi rectas. Iconografía pictográfica clara, no ilustrada.",
        components_guidance="Botones rectangulares con foco visible (outline 2px). Inputs accesibles con asistencia.",
        dos=[
            "Cumplir WCAG 2.2 AA mínimo (AAA donde sea posible)",
            "Lenguaje claro: nivel de lectura ≤ B2",
            "Indicadores de progreso en formularios largos",
        ],
        donts=[
            "Microcopy con humor o jerga",
            "Animaciones decorativas",
            "Densidad alta tipo cockpit",
        ],
    ),
}
