"""Formato del PRD: el PRD dice qué; el plan, cómo (US-123 · UC-12304).

Un PRD nuevo lleva su versión de formato en un comentario invisible justo debajo del título:

    # PRD: …
    <!-- @specbox:prd format="2" -->

Sin marca, el PRD es de formato 1 (los de antes) y nada avisa. En el formato 2 el PRD no trae
«Stack técnico» ni «Archivos principales» (eso va al plan), solo nombra ficheros en su sección
«Restricciones de implementación (opcional, de este cambio)» y guarda lo descartado en
«Alternativas descartadas» (UC-12303).

``check_prd_format`` es pura: recibe el texto del PRD y no lee el tablero ni el disco ni guarda nada,
así que no añade superficie (modelo de amenazas, §4). /prd la llama al escribir el PRD y /plan antes
de generar el plan; los avisos no detienen nada.
"""

from __future__ import annotations

import re
from typing import Any

from ._mutation_helpers import _EXPOSURE_PATH_RE

#: La versión de formato que escriben hoy las plantillas de /prd.
CURRENT_FORMAT = 2

#: ``<!-- @specbox:prd format="2" -->``, con la misma forma que los marcadores ``@specbox:zone``.
FORMAT_MARK_RE = re.compile(r'<!--\s*@specbox:prd\s+format="(\d+)"\s*-->')
FORMAT_MARK = f'<!-- @specbox:prd format="{CURRENT_FORMAT}" -->'

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
#: Las secciones donde un PRD de formato 2 puede nombrar ficheros: sus restricciones y el estado de
#: implementación que el engine añade al final (``write_implementation_status``).
_PATHS_ALLOWED_RE = re.compile(
    r"^restricciones de implementaci[oó]n\b|^implementation status\b|^estado de implementaci[oó]n\b",
    re.IGNORECASE,
)
_PENDING_SECTION_RE = re.compile(r"^pendiente de decidir\b", re.IGNORECASE)
_ALTERNATIVES_SECTION_RE = re.compile(r"^alternativas descartadas\b", re.IGNORECASE)
_PENDING_MARK_RE = re.compile(r"\[\s*POR DECIDIR\b", re.IGNORECASE)
#: Lo citado no es una marca (la documentación nombra `[POR DECIDIR` entre comillas).
_QUOTED_RE = re.compile(r"`[^`\n]*`|«[^»\n]*»")

#: Cuántas líneas del principio se miran para la marca de formato (va debajo del título).
_MARK_WINDOW = 10


def prd_format_version(text: str) -> int:
    """La versión de formato de un PRD: la de su marca, o 1 si no la tiene."""
    head = "\n".join((text or "").splitlines()[:_MARK_WINDOW])
    match = FORMAT_MARK_RE.search(head)
    return int(match.group(1)) if match else 1


def _sections(text: str) -> list[tuple[str, int, int, list[tuple[int, str]]]]:
    """(título, nivel, línea, [(número de línea, texto)]) de cada sección; la de antes del primer
    encabezado tiene título "" y nivel 0. Las líneas de dentro de un bloque de código no abren
    sección."""
    out: list[tuple[str, int, int, list[tuple[int, str]]]] = [("", 0, 1, [])]
    in_code = False
    for number, line in enumerate((text or "").splitlines(), 1):
        if line.lstrip().startswith("```"):
            in_code = not in_code
        heading = None if in_code else _HEADING_RE.match(line)
        if heading:
            out.append((heading.group(2), len(heading.group(1)), number, []))
        else:
            out[-1][3].append((number, line))
    return out


def _paths_outside_restrictions(text: str) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    allowed_level: int | None = None  # nivel del encabezado que abrió una sección permitida
    for title, level, heading_line, lines in _sections(text):
        if allowed_level is not None and level and level <= allowed_level:
            allowed_level = None
        # Una subsección con el mismo nombre («### Implementation Status — UC-1») no estrecha la zona.
        if allowed_level is None and level and _PATHS_ALLOWED_RE.search(title):
            allowed_level = level
        if allowed_level is not None:
            continue
        # El propio encabezado también cuenta («### Cambiar server/x.py» nombra un fichero).
        for number, line in ([(heading_line, title)] if level else []) + lines:
            paths = [m.group(0) for m in _EXPOSURE_PATH_RE.finditer(line)]
            if paths:
                warnings.append({
                    "code": "paths_outside_restrictions",
                    "line": number,
                    "section": title or "(antes del primer encabezado)",
                    "paths": paths,
                    "message": (
                        "El PRD dice qué; el plan, cómo. Lleva estas rutas al plan, o a «Restricciones de "
                        "implementación» si el cambio obliga a respetarlas."
                    ),
                })
    return warnings


def _missing_pending_section(text: str) -> list[dict[str, Any]]:
    sections = _sections(text)
    has_section = any(level and _PENDING_SECTION_RE.search(title) for title, level, _, _ in sections)
    if has_section:
        return []
    marks = [
        number
        for _, _, _, lines in sections
        for number, line in lines
        if _PENDING_MARK_RE.search(_QUOTED_RE.sub(" ", line))
    ]
    if not marks:
        return []
    return [{
        "code": "missing_pending_section",
        "lines": marks,
        "message": (
            "El PRD tiene marcas [POR DECIDIR: …] y no tiene la sección «Pendiente de decidir» que las "
            "lista. Añádela con cada marca y quién la decide."
        ),
    }]


def _missing_alternatives(text: str) -> list[dict[str, Any]]:
    """UC-12303: el formato 2 guarda lo descartado junto a la spec («Ninguna» también vale)."""
    if any(level and _ALTERNATIVES_SECTION_RE.search(title) for title, level, _, _ in _sections(text)):
        return []
    return [{
        "code": "missing_alternatives",
        "message": (
            "El PRD no tiene la sección «Alternativas descartadas». Añade cada opción que se planteó y no "
            "se eligió, con el motivo y quién la descartó, o escribe «Ninguna»."
        ),
    }]


def check_prd_format_content(prd_content: str) -> dict[str, Any]:
    """La versión de formato de un PRD y sus avisos. Pura: no lee ni escribe nada."""
    version = prd_format_version(prd_content)
    warnings: list[dict[str, Any]] = []
    if version >= 2:
        warnings += _paths_outside_restrictions(prd_content)
        warnings += _missing_pending_section(prd_content)
        warnings += _missing_alternatives(prd_content)
    return {
        "format_version": version,
        "current_format": CURRENT_FORMAT,
        "warnings": warnings,
        "summary": (
            f"PRD de formato {version}: "
            + (f"{len(warnings)} aviso(s)." if warnings else "sin avisos.")
            + ("" if version >= 2 else " Sin marca de formato: es un PRD anterior y no se le pide el formato nuevo.")
        ),
    }


async def check_prd_format(prd_content: str) -> dict[str, Any]:
    """Comprueba el formato de un PRD (UC-12304): el PRD dice qué; el plan, cómo.

    Pasa el texto del PRD (el cliente lo lee de su disco). Devuelve ``{format_version,
    current_format, warnings, summary}``. Un PRD sin la marca ``<!-- @specbox:prd format="2" -->``
    es de formato 1 y no recibe avisos. En el formato 2:

    - ``paths_outside_restrictions``: una ruta de fichero fuera de «Restricciones de
      implementación» (con su línea, su sección y las rutas);
    - ``missing_pending_section``: marcas ``[POR DECIDIR: …]`` sin la sección «Pendiente de decidir»;
    - ``missing_alternatives``: falta «Alternativas descartadas» (UC-12303; «Ninguna» vale).

    Es pura: no lee el tablero ni el disco ni guarda el texto. Los avisos no detienen nada.
    """
    if not isinstance(prd_content, str):
        return {"error": "prd_content must be the PRD text", "code": "VALIDATION_FAILED"}
    return check_prd_format_content(prd_content)


def register_prd_format_tools(mcp_instance) -> None:
    """Registra ``check_prd_format`` (US-123 · UC-12304)."""
    mcp_instance.tool(
        description="Check a PRD's format (pure: pass its text as prd_content; nothing is read or "
        "stored). Returns format_version (1 when it has no <!-- @specbox:prd format=\"2\" --> mark) "
        "and warnings for format 2: file paths outside «Restricciones de implementación» "
        "(paths_outside_restrictions), [POR DECIDIR: …] marks without a «Pendiente de decidir» "
        "section (missing_pending_section) and no «Alternativas descartadas» section "
        "(missing_alternatives). /prd calls it after writing a PRD and /plan before planning; the "
        "warnings do not stop anything."
    )(check_prd_format)
