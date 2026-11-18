"""El CLAUDE.md de un proyecto: zonas de la plantilla y lo del proyecto (UC-12209).

La plantilla marca sus secciones con

    <!-- @specbox:claude-md start id="memoria" -->
    ...
    <!-- @specbox:claude-md end -->

Lo que queda fuera de los marcadores es del proyecto y ``upgrade_project`` no lo toca:

- ``merge_claude_md``: un CLAUDE.md con marcadores. Sustituye el cuerpo de cada zona por el de la
  plantilla, añade las zonas nuevas (tras la zona anterior en el orden de la plantilla) y quita las
  que la plantilla ya no tiene.
- ``propose_claude_md``: un CLAUDE.md sin marcadores (de antes de la 6.38.0). No se escribe: se
  devuelve la propuesta con las secciones que salen y adónde van (``RELOCATIONS``), y las que se
  quedan porque son del proyecto.

Todo es puro (texto → texto) para que el servidor no toque el disco de nadie.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

ZONE_START = re.compile(r'^<!-- @specbox:claude-md start id="([a-z0-9-]+)" -->\s*$')
ZONE_END = re.compile(r"^<!-- @specbox:claude-md end -->\s*$")


class MalformedZones(ValueError):
    """Un marcador abierto sin cerrar, cerrado sin abrir o repetido."""


@dataclass(frozen=True)
class Segment:
    kind: str  # "text" | "zone"
    text: str  # el texto entero del segmento, marcadores incluidos
    zone_id: str = ""


def split_zones(text: str) -> list[Segment]:
    """Parte el texto en tramos del proyecto y zonas de la plantilla, en orden."""
    segments: list[Segment] = []
    buf: list[str] = []
    zone: str | None = None
    seen: set[str] = set()
    for line in text.splitlines(keepends=True):
        start = ZONE_START.match(line.rstrip("\n"))
        end = ZONE_END.match(line.rstrip("\n"))
        if start:
            if zone is not None:
                raise MalformedZones(f"la zona «{zone}» se abre otra vez sin cerrarse")
            if start.group(1) in seen:
                raise MalformedZones(f"la zona «{start.group(1)}» aparece dos veces")
            if buf:
                segments.append(Segment("text", "".join(buf)))
            buf = [line]
            zone = start.group(1)
            seen.add(zone)
        elif end:
            if zone is None:
                raise MalformedZones("hay un cierre de zona sin su apertura")
            buf.append(line)
            segments.append(Segment("zone", "".join(buf), zone))
            buf, zone = [], None
        else:
            buf.append(line)
    if zone is not None:
        raise MalformedZones(f"la zona «{zone}» no se cierra")
    if buf:
        segments.append(Segment("text", "".join(buf)))
    return segments


def zone_ids(text: str) -> list[str]:
    return [s.zone_id for s in split_zones(text) if s.kind == "zone"]


def has_zones(text: str) -> bool:
    return any(ZONE_START.match(line) for line in text.splitlines())


@dataclass
class MergeResult:
    content: str
    replaced: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)


def _ensure_newline(text: str) -> str:
    return text if text.endswith("\n") else text + "\n"


def merge_claude_md(current: str, template: str) -> MergeResult:
    """Sustituye solo las zonas de la plantilla; lo del proyecto queda igual, byte a byte."""
    tpl = {s.zone_id: s.text for s in split_zones(template) if s.kind == "zone"}
    order = list(tpl)
    segments = split_zones(current)
    result = MergeResult(content="")
    present = [s.zone_id for s in segments if s.kind == "zone"]

    out: list[Segment] = []
    for seg in segments:
        if seg.kind == "text":
            out.append(seg)
        elif seg.zone_id in tpl:
            if seg.text != tpl[seg.zone_id]:
                result.replaced.append(seg.zone_id)
            out.append(Segment("zone", tpl[seg.zone_id], seg.zone_id))
        else:
            result.removed.append(seg.zone_id)

    # Zonas nuevas: tras la zona anterior de la plantilla que ya está, o antes de la siguiente.
    for index, zid in enumerate(order):
        if zid in present:
            continue
        new = Segment("zone", tpl[zid], zid)
        ids = [s.zone_id for s in out]
        before = next((z for z in reversed(order[:index]) if z in ids), None)
        after = next((z for z in order[index + 1:] if z in ids), None)
        if before is not None:
            pos = ids.index(before) + 1
        elif after is not None:
            pos = ids.index(after)
        else:
            pos = len(out)
        if pos > 0 and not out[pos - 1].text.endswith("\n"):
            out[pos - 1] = Segment(out[pos - 1].kind, out[pos - 1].text + "\n", out[pos - 1].zone_id)
        out.insert(pos, Segment("zone", _ensure_newline(new.text), zid))
        result.added.append(zid)

    result.content = "".join(s.text for s in out)
    return result


# ── CLAUDE.md sin marcadores (plantilla anterior a la 6.38.0) ─────────────────────────────

GUIDE = "doc/guides/claude-md.md"

# Secciones de la plantilla anterior: adónde fue cada una. La guía repite esta tabla y una prueba
# comprueba que cada destino existe y trae lo que se le atribuye.
RELOCATIONS: list[dict[str, str]] = [
    {
        "section": "Memoria Persistente (Engram) — REQUERIDO",
        "zone": "memoria",
        "goes_to": "zona «memoria» (la comprobación y qué hacer tras una compactación); "
        "la instalación por sistema, la persistencia y las tools, a doc/guides/memoria-engram.md",
    },
    {
        "section": "Quality Contract — Calidad sobre velocidad",
        "zone": "calidad",
        "goes_to": "zona «calidad» (las cinco reglas); la tabla de antipatrones, a "
        "rules/GLOBAL_RULES.md (Antipatrones prohibidos)",
    },
    {
        "section": "Agentes del Proyecto",
        "zone": "agentes",
        "goes_to": "zona «agentes» (la tabla); Agent Teams, a docs/agent-teams.md",
    },
    {
        "section": "Comandos Disponibles",
        "zone": "recorrido",
        "goes_to": "zona «recorrido» (comandos y recorrido de la UC)",
    },
    {
        "section": "Flujo de Desarrollo",
        "zone": "recorrido",
        "goes_to": "zona «recorrido» (recorrido de la UC y la CI a mano)",
    },
    {
        "section": "Trello — Fuente de Verdad (Spec-Driven)",
        "zone": "recorrido",
        "goes_to": "zona «recorrido» (el tablero, sea cual sea el backend); "
        "lo propio de Trello, a doc/guides/claude-md.md (Trello)",
    },
    {
        "section": "Acceptance Testing — Gherkin BDD",
        "zone": "pruebas",
        "goes_to": "zona «pruebas»; el formato .feature y el paquete por stack, a "
        ".claude/skills/implement/SKILL.md (Paso 7.5) y rules/GLOBAL_RULES.md (Acceptance Testing)",
    },
    {
        "section": "Visual Experience Generation — VEG (v3.9)",
        "zone": "pruebas",
        "goes_to": "zona «pruebas» (una línea); los tres pilares y la configuración, a "
        ".claude/skills/visual-setup/SKILL.md y .claude/skills/plan/SKILL.md (Paso 2.5b)",
    },
    {
        "section": "E2E Testing",
        "zone": "pruebas",
        "goes_to": "zona «pruebas»; los patrones por stack, a architecture/{stack}/e2e-testing.md",
    },
    {
        "section": "Permisos de Claude Code",
        "zone": "permisos",
        "goes_to": "zona «permisos»; el detalle, a doc/guides/permisos.md",
    },
    {
        "section": "Hooks",
        "zone": "permisos",
        "goes_to": "zona «permisos»; cada hook, a doc/guides/hooks.md",
    },
]

# Secciones de la plantilla anterior que son del proyecto: se quedan tal cual.
PROJECT_SECTIONS = ("Stack", "Arquitectura", "Reglas del Proyecto", "Sistema de Diseño", "Servicios Externos")

# Zonas que van antes de las secciones del proyecto en la propuesta: lo que el agente lee primero.
_LEADING_ZONES = ("version", "memoria", "calidad")
_TRAILING_ZONES: tuple[str, ...] = ()


def _norm(heading: str) -> str:
    text = unicodedata.normalize("NFKD", heading).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


_RELOCATED = {_norm(r["section"]): r for r in RELOCATIONS}
_RELOCATED_PREFIXES = {
    _norm("Memoria Persistente"): "Memoria Persistente (Engram) — REQUERIDO",
    _norm("Quality Contract"): "Quality Contract — Calidad sobre velocidad",
    _norm("Trello"): "Trello — Fuente de Verdad (Spec-Driven)",
    _norm("Acceptance Testing"): "Acceptance Testing — Gherkin BDD",
    _norm("Visual Experience Generation"): "Visual Experience Generation — VEG (v3.9)",
}


def _relocation_for(heading: str) -> dict[str, str] | None:
    key = _norm(heading)
    if key in _RELOCATED:
        return _RELOCATED[key]
    for prefix, section in _RELOCATED_PREFIXES.items():
        if key.startswith(prefix):
            return _RELOCATED[_norm(section)]
    return None


def _h2_sections(text: str) -> tuple[str, list[tuple[str, str]]]:
    """(preámbulo, [(título, texto)]) por encabezados de nivel 2, sin mirar dentro de bloques de código."""
    preamble: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    fence = False
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith("```"):
            fence = not fence
        if not fence and line.startswith("## "):
            sections.append((line[3:].strip(), [line]))
        elif sections:
            sections[-1][1].append(line)
        else:
            preamble.append(line)
    return "".join(preamble), [(title, "".join(body)) for title, body in sections]


@dataclass
class Proposal:
    content: str
    sections_leaving: list[dict[str, str]]
    sections_kept: list[str]


def propose_claude_md(current: str, template: str) -> Proposal:
    """La propuesta para un CLAUDE.md sin marcadores: la plantilla con lo del proyecto dentro."""
    preamble, sections = _h2_sections(current)
    zones = [s for s in split_zones(template) if s.kind == "zone"]
    by_id = {s.zone_id: s.text for s in zones}

    leaving: list[dict[str, str]] = []
    kept: list[str] = []
    kept_text: list[str] = []
    for title, body in sections:
        relocation = _relocation_for(title)
        if relocation:
            leaving.append({"section": title, "goes_to": relocation["goes_to"]})
        else:
            kept.append(title)
            kept_text.append(_ensure_newline(body))

    # El título del proyecto se queda; la línea «Generado con SpecBox Engine» la pone la zona «version».
    title_lines = [
        line for line in preamble.splitlines(keepends=True)
        if not line.lstrip().startswith("> Generado con SpecBox Engine")
    ]
    head = "".join(title_lines).rstrip("\n") + "\n\n" if "".join(title_lines).strip() else ""

    parts: list[str] = [head]
    for zid in _LEADING_ZONES:
        if zid in by_id:
            parts.append(_ensure_newline(by_id[zid]) + "\n")
    parts.extend(kept_text)
    for seg in zones:
        if seg.zone_id in _LEADING_ZONES or seg.zone_id in _TRAILING_ZONES:
            continue
        parts.append("\n" + _ensure_newline(seg.text))
    for zid in _TRAILING_ZONES:
        if zid in by_id:
            parts.append("\n" + _ensure_newline(by_id[zid]))
    content = re.sub(r"\n{3,}", "\n\n", "".join(parts))
    return Proposal(content=content, sections_leaving=leaving, sections_kept=kept)


def claude_md_for_upgrade(current: str | None, template: str, *, confirm: bool = False) -> tuple[str | None, dict]:
    """(contenido que escribir o None, informe) para ``upgrade_project``.

    - ``current`` None: el cliente no mandó su CLAUDE.md; no se escribe nada.
    - ``current`` vacío: el proyecto no tiene CLAUDE.md; se crea con la plantilla.
    - con marcadores: se sustituyen solo las zonas.
    - sin marcadores: propuesta; se escribe solo con ``confirm``.
    """
    if current is None:
        return None, {
            "status": "content_required",
            "message": (
                "El CLAUDE.md no se regenera a ciegas: pasa su contenido en claude_md_content "
                "(cadena vacía si el proyecto no tiene) y upgrade_project solo cambiará las zonas "
                "de la plantilla."
            ),
            "guide": GUIDE,
        }
    if not current.strip():
        return template, {"status": "created", "zones": zone_ids(template)}
    try:
        marked = has_zones(current)
        if marked:
            split_zones(current)
    except MalformedZones as exc:
        return None, {
            "status": "malformed",
            "message": f"Los marcadores del CLAUDE.md no cuadran ({exc}); no se toca. Arréglalos y repite.",
            "guide": GUIDE,
        }
    if marked:
        merged = merge_claude_md(current, template)
        if merged.content == current:
            return None, {"status": "unchanged"}
        return merged.content, {
            "status": "merged",
            "replaced": merged.replaced,
            "added": merged.added,
            "removed": merged.removed,
        }
    proposal = propose_claude_md(current, template)
    report = {
        "status": "applied" if confirm else "proposal",
        "sections_leaving": proposal.sections_leaving,
        "sections_kept": proposal.sections_kept,
        "guide": GUIDE,
    }
    if confirm:
        return proposal.content, report
    report["proposed_content"] = proposal.content
    report["how_to_apply"] = (
        "Enseña a la persona sections_leaving (qué sale y adónde va). Si está de acuerdo, repite "
        "upgrade_project con el mismo claude_md_content y confirm_claude_md=true."
    )
    return None, report
