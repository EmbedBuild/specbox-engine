"""Parsers puros de ENGINE_VERSION.yaml y CHANGELOG.md (UC-1601).

Sin dependencias de FastMCP ni de red ni de filesystem: reciben texto, devuelven
dataclasses. Esto los hace triviales de testear (AC-01/02/03 de UC-1601) y reutilizables
por el publicador (UC-1602) y el skill /release (UC-1603).

Decisiones de parseo:
- `since_version` de cada feature se deriva del comentario `# New (vX.Y.Z)` /
  `# Existing (vX.Y.Z)` que precede a su bloque en `features:`. `yaml.safe_load` descarta
  comentarios, así que ese campo se extrae del texto crudo, no del árbol YAML.
- `public_highlights` se deriva de forma DETERMINISTA (ver `derive_public_highlights`):
  primero del `### Added` de la versión en CHANGELOG.md (lenguaje de producto, legible);
  si no hay, del bloque `changelog:` de ENGINE_VERSION.yaml. Siempre 2-4 bullets, recortados.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import yaml

# Cuántos highlights públicos exponer por versión (2-4 por contrato del PRD US-18/UC-1801).
MIN_HIGHLIGHTS = 2
MAX_HIGHLIGHTS = 4
# Longitud máxima de un highlight para que sea "de producto" y no un párrafo.
HIGHLIGHT_MAX_CHARS = 180


@dataclass
class FeatureInfo:
    feature_key: str
    category: str = ""
    since_version: str = ""
    status: str = "active"


@dataclass
class ReleaseInfo:
    version: str
    codename: str = ""
    release_date: str = ""  # ISO date string (YYYY-MM-DD) o "" si ausente
    min_claude_code: str = ""


@dataclass
class ChangelogEntry:
    version: str
    codename: str = ""
    release_date: str = ""
    sections: dict[str, list[str]] = field(default_factory=dict)  # {"Added": [...], ...}
    public_highlights: list[str] = field(default_factory=list)


@dataclass
class EngineState:
    """Estado completo listo para publicar a Supabase."""

    release: ReleaseInfo
    features: list[FeatureInfo]
    stacks: dict[str, str]
    services: list[str]
    project_managers: list[str]
    changelog: list[ChangelogEntry]


# ---------------------------------------------------------------------------
# ENGINE_VERSION.yaml
# ---------------------------------------------------------------------------

# Comentario que marca el since_version de los bloques de features, p.ej. "# New (v4.0.0)".
_SINCE_COMMENT = re.compile(r"#\s*(?:New|Existing)\s*\(v?([0-9][0-9A-Za-z.\-]*)\)")
# Línea de feature dentro de features:, p.ej. "  - agent-skills".
_FEATURE_LINE = re.compile(r"^\s*-\s+(\S.*?)\s*$")


def _date_to_str(value) -> str:
    """Normaliza una fecha YAML (date | str | None) a 'YYYY-MM-DD' o ''."""
    if value is None:
        return ""
    # yaml.safe_load convierte fechas ISO a datetime.date.
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value).strip()


def _derive_feature_since_versions(yaml_text: str) -> dict[str, str]:
    """Mapea feature_key -> since_version leyendo los comentarios del bloque `features:`.

    Recorre solo la sección `features:` (desde su cabecera hasta la siguiente clave de
    nivel raíz). Cada `# New (vX)` fija el since para las features que le siguen.
    """
    lines = yaml_text.splitlines()
    in_features = False
    current_since = ""
    result: dict[str, str] = {}

    for line in lines:
        stripped = line.strip()
        # Cabecera de la sección features:
        if re.match(r"^features:\s*$", line):
            in_features = True
            continue
        if not in_features:
            continue
        # Fin de la sección: una nueva clave raíz (sin indentar, termina en ':').
        if line and not line[0].isspace() and stripped.endswith(":"):
            break

        comment_match = _SINCE_COMMENT.search(line)
        if comment_match:
            current_since = comment_match.group(1)
            continue

        feature_match = _FEATURE_LINE.match(line)
        if feature_match:
            key = feature_match.group(1).strip().strip('"').strip("'")
            # Una feature puede venir como dict (key: ...) — quedarnos con la clave.
            key = key.split(":")[0].strip()
            if key:
                result.setdefault(key, current_since)

    return result


def parse_engine_version(yaml_text: str) -> EngineState:
    """Parsea ENGINE_VERSION.yaml a un EngineState (sin el campo changelog enriquecido).

    El campo `changelog` se rellena de forma básica desde el bloque `changelog:` del YAML;
    `build_engine_state` lo enriquece luego con el CHANGELOG.md si está disponible.
    """
    data = yaml.safe_load(yaml_text) or {}

    release = ReleaseInfo(
        version=str(data.get("version", "")).strip(),
        codename=str(data.get("codename", "") or "").strip(),
        release_date=_date_to_str(data.get("release_date")),
        min_claude_code=str(data.get("min_claude_code", "") or "").strip(),
    )

    since_map = _derive_feature_since_versions(yaml_text)
    features: list[FeatureInfo] = []
    raw_features = data.get("features") or []
    for item in raw_features:
        if isinstance(item, dict):
            # Forma {key: {...}} — poco habitual pero soportada.
            for key, meta in item.items():
                fkey = str(key).strip()
                meta = meta or {}
                features.append(
                    FeatureInfo(
                        feature_key=fkey,
                        category=str(meta.get("category", "") or ""),
                        since_version=str(meta.get("since", "") or since_map.get(fkey, "")),
                        status=str(meta.get("status", "active") or "active"),
                    )
                )
        else:
            fkey = str(item).strip()
            if fkey:
                features.append(
                    FeatureInfo(feature_key=fkey, since_version=since_map.get(fkey, ""))
                )

    stacks = {str(k): str(v) for k, v in (data.get("stacks") or {}).items()}
    services = [str(s) for s in (data.get("services") or [])]
    project_managers = [str(p) for p in (data.get("project_managers") or [])]

    # Changelog básico desde el bloque YAML (date/codename/changes por versión).
    changelog: list[ChangelogEntry] = []
    raw_changelog = data.get("changelog") or {}
    for version, meta in raw_changelog.items():
        meta = meta or {}
        changes = [str(c) for c in (meta.get("changes") or [])]
        changelog.append(
            ChangelogEntry(
                version=str(version),
                codename=str(meta.get("codename", "") or ""),
                release_date=_date_to_str(meta.get("date")),
                sections={"Changes": changes} if changes else {},
            )
        )

    return EngineState(
        release=release,
        features=features,
        stacks=stacks,
        services=services,
        project_managers=project_managers,
        changelog=changelog,
    )


# ---------------------------------------------------------------------------
# CHANGELOG.md (Keep a Changelog)
# ---------------------------------------------------------------------------

# Cabecera de versión: "## [6.11.0] - 2026-06-14 — "Self Update""
_VERSION_HEADER = re.compile(
    r'^##\s*\[(?P<version>[^\]]+)\]\s*-\s*(?P<date>\d{4}-\d{2}-\d{2})?\s*(?:[—–-]\s*"?(?P<codename>[^"]*?)"?\s*)?$'
)
# Cabecera de sección: "### Added"
_SECTION_HEADER = re.compile(r"^###\s+(?P<name>.+?)\s*$")
# Ítem de lista markdown.
_LIST_ITEM = re.compile(r"^\s*[-*]\s+(?P<text>.+?)\s*$")


def parse_changelog_md(md_text: str) -> list[ChangelogEntry]:
    """Parsea un CHANGELOG.md (Keep a Changelog) a una lista de ChangelogEntry por versión.

    Cada entry lleva sus secciones (Added/Changed/Fixed/...) con la lista de ítems. El
    orden de salida respeta el del documento (descendente por versión, como el fichero).
    """
    entries: list[ChangelogEntry] = []
    current: ChangelogEntry | None = None
    current_section: str | None = None

    for raw_line in md_text.splitlines():
        header = _VERSION_HEADER.match(raw_line)
        if header:
            if current is not None:
                entries.append(current)
            current = ChangelogEntry(
                version=header.group("version").strip(),
                codename=(header.group("codename") or "").strip(),
                release_date=(header.group("date") or "").strip(),
                sections={},
            )
            current_section = None
            continue

        if current is None:
            continue

        section = _SECTION_HEADER.match(raw_line)
        if section:
            current_section = section.group("name").strip()
            current.sections.setdefault(current_section, [])
            continue

        if current_section is not None:
            item = _LIST_ITEM.match(raw_line)
            if item:
                current.sections[current_section].append(_strip_markdown(item.group("text")))

    if current is not None:
        entries.append(current)

    return entries


# ---------------------------------------------------------------------------
# public_highlights (derivación determinista)
# ---------------------------------------------------------------------------

_MD_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_MD_EMPH = re.compile(r"(\*\*|__|\*|_|`)")
_UC_SUFFIX = re.compile(r"\s*\((?:US|UC)-[0-9A-Za-z/.\-]+\)\s*$")
_TRAILING_UC = re.compile(r"\s*\((?:US|UC)-[^)]*\)")


def _strip_markdown(text: str) -> str:
    """Convierte un ítem markdown a texto plano legible (sin enlaces, énfasis, ni refs UC)."""
    text = _MD_LINK.sub(r"\1", text)
    text = _MD_EMPH.sub("", text)
    text = _TRAILING_UC.sub("", text)
    return text.strip()


def _product_phrase(text: str) -> str:
    """Recorta un ítem técnico a una frase de producto: primera oración, sin prefijo 'feat:'."""
    text = re.sub(r"^(feat|fix|chore|test|docs|refactor|perf)(\([^)]*\))?:\s*", "", text, flags=re.I)
    # Quedarnos con la parte antes del primer ' — ' o '. ' o '; ' para una frase corta.
    for sep in (" — ", " – ", ". ", "; "):
        idx = text.find(sep)
        if 0 < idx <= HIGHLIGHT_MAX_CHARS:
            text = text[:idx]
            break
    text = text.strip().rstrip(".")
    if len(text) > HIGHLIGHT_MAX_CHARS:
        text = text[: HIGHLIGHT_MAX_CHARS - 1].rstrip() + "…"
    return text


def derive_public_highlights(
    version: str,
    md_entries: list[ChangelogEntry],
    yaml_entries: list[ChangelogEntry],
) -> list[str]:
    """Deriva 2-4 highlights de producto para una versión, de forma DETERMINISTA.

    Prioridad de fuente (la primera no vacía gana):
    1. Sección `Added` del CHANGELOG.md de esa versión (lenguaje de producto).
    2. Cualquier otra sección del CHANGELOG.md (Changed/Fixed), en orden de aparición.
    3. El bloque `changelog:` de ENGINE_VERSION.yaml (campo `changes`).

    Determinista: misma entrada -> misma salida. Recorta a MAX_HIGHLIGHTS, exige al menos
    los que haya (puede devolver <MIN si la fuente es pobre; el caller decide qué hacer).
    """
    md_by_version = {e.version: e for e in md_entries}
    yaml_by_version = {e.version: e for e in yaml_entries}

    candidates: list[str] = []

    md_entry = md_by_version.get(version)
    if md_entry:
        # 1. Added primero; 2. resto de secciones en orden.
        ordered_sections = list(md_entry.sections.items())
        ordered_sections.sort(key=lambda kv: (kv[0] != "Added",))
        for _name, items in ordered_sections:
            for item in items:
                phrase = _product_phrase(item)
                if phrase and phrase not in candidates:
                    candidates.append(phrase)
                if len(candidates) >= MAX_HIGHLIGHTS:
                    break
            if len(candidates) >= MAX_HIGHLIGHTS:
                break

    # 3. Fallback al YAML.
    if not candidates:
        yaml_entry = yaml_by_version.get(version)
        if yaml_entry:
            for items in yaml_entry.sections.values():
                for item in items:
                    phrase = _product_phrase(item)
                    if phrase and phrase not in candidates:
                        candidates.append(phrase)
                    if len(candidates) >= MAX_HIGHLIGHTS:
                        break

    return candidates[:MAX_HIGHLIGHTS]


def build_engine_state(yaml_text: str, changelog_md_text: str | None = None) -> EngineState:
    """Construye el EngineState completo combinando ambas fuentes.

    El changelog del EngineState se enriquece con el CHANGELOG.md cuando se provee:
    cada versión gana sus `sections` del markdown y sus `public_highlights` derivados.
    Si no se provee markdown, se conserva el changelog básico del YAML y los highlights
    se derivan de ese mismo bloque.
    """
    state = parse_engine_version(yaml_text)
    md_entries = parse_changelog_md(changelog_md_text) if changelog_md_text else []

    yaml_changelog = state.changelog
    md_by_version = {e.version: e for e in md_entries}

    enriched: list[ChangelogEntry] = []
    # Unión de versiones: las del YAML (autoridad de existencia) enriquecidas con MD.
    for entry in yaml_changelog:
        md = md_by_version.get(entry.version)
        sections = md.sections if md and md.sections else entry.sections
        codename = entry.codename or (md.codename if md else "")
        release_date = entry.release_date or (md.release_date if md else "")
        highlights = derive_public_highlights(entry.version, md_entries, yaml_changelog)
        enriched.append(
            ChangelogEntry(
                version=entry.version,
                codename=codename,
                release_date=release_date,
                sections=sections,
                public_highlights=highlights,
            )
        )

    state.changelog = enriched
    return state
