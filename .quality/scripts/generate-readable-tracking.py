#!/usr/bin/env python3
"""
generate-readable-tracking.py — Capa de lectura humana sobre el FreeformBackend.

Lee doc/tracking/items.json (fuente de verdad del FreeformBackend, NO se toca) y
genera markdowns legibles y curados por US y por UC siguiendo el patrón de
specbox_cloud:

    doc/tracking/us/US-XX_slug.md   ← uno por User Story
    doc/tracking/uc/UC-XXX_slug.md  ← uno por Use Case (con sus ACs + link al US padre)
    doc/tracking/index.json         ← índice ligero
    doc/tracking/README.md          ← vista general

NO modifica items.json / config.json / labels.json / archive.json / comments/
/ attachments/ / progress/ — esos son los archivos vivos del backend.

Idempotente: regenera us/ y uc/ desde cero en cada ejecución.
"""
from __future__ import annotations
import json
import re
import shutil
import unicodedata
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRACKING = ROOT / "doc" / "tracking"
ITEMS = TRACKING / "items.json"

STATE_MAP = {
    "user_stories": "draft",
    "backlog": "ready",
    "todo": "ready",
    "in_progress": "in-progress",
    "review": "review",
    "done": "done",
}

AC_STATE_GLYPH = {
    "done": "✅ cumplido",
    "in_progress": "🟡 en progreso",
    "review": "🟡 en progreso",
    "backlog": "⬜ pendiente",
    "user_stories": "⬜ pendiente",
}

TODAY = date.today().isoformat()


# Quita prefijos de id al inicio del nombre: "[UC-101] ", "UC-001: ", "US-XX — "
_PREFIX_RE = re.compile(r"^\s*(?:\[[A-Z]+-[\w-]+\]|(?:US|UC|AC)-[\w-]+\s*[:—\-])\s*", re.IGNORECASE)


def strip_prefix(name: str) -> str:
    return _PREFIX_RE.sub("", name).strip()


def slugify(text: str) -> str:
    text = strip_prefix(text)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:60] or "sin-titulo"


def yaml_escape(value: str) -> str:
    value = (value or "").replace("\n", " ").strip()
    if any(c in value for c in ":#") or value == "":
        return json.dumps(value, ensure_ascii=False)
    return value


def main() -> None:
    items = json.loads(ITEMS.read_text(encoding="utf-8"))
    by_id = {i["id"]: i for i in items}

    us_items = [i for i in items if i.get("meta", {}).get("tipo") == "US"]
    uc_items = [i for i in items if i.get("meta", {}).get("tipo") == "UC"]

    # children index
    children: dict[str, list[dict]] = {}
    for i in items:
        pid = i.get("parent_id")
        if pid:
            children.setdefault(pid, []).append(i)

    us_dir = TRACKING / "us"
    uc_dir = TRACKING / "uc"
    for d in (us_dir, uc_dir):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)

    # Ordinalidad cronológica: orden por (created_at, id) → prefijo NN al FINAL del
    # id-prefix del nombre de archivo. Formato: US-XX-NN_slug.md / UC-XXX-NN_slug.md.
    # Los más recientes quedan al final del listado de la carpeta.
    dup_warnings: list[str] = []

    def _assign_ordinals(group: list[dict], id_key: str, kind: str, width: int) -> dict[str, str]:
        """Asigna _fname con ordinal cronológico al FRENTE y devuelve {id_meta: fname}.

        Formato: <KIND>-<NN>-<slug>.md (p.ej. US-01-specbox-para-equipos.md).
        El ordinal NN va delante para que la carpeta se ordene cronológicamente
        (los más recientes al final). El id original (us_id/uc_id) vive en el
        frontmatter, no se pierde. Reporta ids duplicados (drift en items.json).
        El primer item registrado gana el enlace canónico (clave = id de meta).
        """
        ordered = sorted(group, key=lambda i: (i["created_at"], i["id"]))
        canonical: dict[str, str] = {}
        seen_ids: set[str] = set()
        for n, item in enumerate(ordered, 1):
            mid = item["meta"][id_key]
            if mid in seen_ids:
                dup_warnings.append(
                    f"{id_key} duplicado en items.json: {mid} (item {item['id']})"
                )
            seen_ids.add(mid)
            fname = f"{kind}-{n:0{width}d}-{slugify(item['name'])}.md"
            item["_fname"] = fname
            item["_ordinal"] = f"{kind}-{n:0{width}d}"
            canonical.setdefault(mid, fname)
        return canonical

    us_filename = _assign_ordinals(us_items, "us_id", "US", 2)
    uc_filename = _assign_ordinals(uc_items, "uc_id", "UC", 3)

    # ---- Generar US ----
    for us in us_items:
        usid = us["meta"]["us_id"]
        title = strip_prefix(us["name"])
        status = STATE_MAP.get(us["state"], us["state"])
        hours = us["meta"].get("horas", "")
        desc = (us.get("description") or "").strip()

        child_ucs = sorted(
            (c for c in children.get(us["id"], []) if c.get("meta", {}).get("tipo") == "UC"),
            key=lambda c: c["meta"].get("uc_id", ""),
        )
        uc_rows = "\n".join(
            f"| {c['meta']['uc_id']} | [{strip_prefix(c['name'])}](../uc/{c['_fname']}) | {STATE_MAP.get(c['state'], c['state'])} |"
            for c in child_ucs
        ) or "| — | _Sin UCs registrados_ | — |"

        fm = [
            "---",
            f"id: {usid}",
            f"ordinal: {us['_ordinal']}",
            f"title: {yaml_escape(title)}",
            f"status: {status}",
            f"hours: {hours}" if hours else "hours:",
            "owner: Jesús Pérez",
            f"created: {us['created_at'][:10]}",
            f"updated: {TODAY}",
            "source: items.json (FreeformBackend)",
            "---",
            "",
        ]
        body = [
            f"# {usid} — {title}",
            "",
            "## Como… quiero… para…",
            "",
            "\n".join(f"> {line}" for line in (desc or "_Sin descripción._").splitlines()),
            "",
            "## Use Cases asociados",
            "",
            "| UC | Título | Estado |",
            "|----|--------|--------|",
            uc_rows,
            "",
            "## Notas",
            "",
            f"_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o "
            f"regenerar con `.quality/scripts/generate-readable-tracking.py`._",
            "",
        ]
        (us_dir / us["_fname"]).write_text("\n".join(fm + body), encoding="utf-8")

    # ---- Generar UC ----
    for uc in uc_items:
        ucid = uc["meta"]["uc_id"]
        title = strip_prefix(uc["name"])
        status = STATE_MAP.get(uc["state"], uc["state"])
        usid = uc["meta"].get("us_id", "")
        actor = uc["meta"].get("actor", "")
        hours = uc["meta"].get("horas", "")
        desc = (uc.get("description") or "").strip()
        # algunos imports repiten el título como H1 al inicio de la descripción
        first_line = desc.splitlines()[0] if desc else ""
        if first_line.lstrip("# ").strip().lower() == strip_prefix(uc["name"]).lower() or \
           first_line.lstrip("# ").lower().startswith(f"{ucid.lower()}"):
            desc = "\n".join(desc.splitlines()[1:]).strip()

        parent_link = ""
        if usid and usid in us_filename:
            parent_link = f"> **US padre:** [{usid}](../us/{us_filename[usid]})\n"
        elif usid:
            parent_link = f"> **US padre:** {usid}\n"

        acs = sorted(
            (c for c in children.get(uc["id"], []) if c.get("meta", {}).get("tipo") == "AC"),
            key=lambda c: c["meta"].get("ac_id", ""),
        )
        ac_blocks = []
        for ac in acs:
            acid = ac["meta"].get("ac_id", "AC-?")
            ac_text = strip_prefix(ac["name"])
            glyph = AC_STATE_GLYPH.get(ac["state"], "⬜ pendiente")
            evidence = ac["meta"].get("evidence", "")
            block = [f"### {acid}", "", ac_text, "", f"- **Estado:** {glyph}"]
            if evidence:
                block.append(f"- **Evidencia:** {evidence}")
            ac_blocks.append("\n".join(block))
        ac_section = "\n\n".join(ac_blocks) if ac_blocks else "_Sin Acceptance Criteria registrados._"

        fm = [
            "---",
            f"id: {ucid}",
            f"ordinal: {uc['_ordinal']}",
            f"title: {yaml_escape(title)}",
            f"parent_us: {usid}",
            f"status: {status}",
            f"actor: {yaml_escape(actor)}" if actor else "actor:",
            f"hours: {hours}" if hours else "hours:",
            "owner: Jesús Pérez",
            f"created: {uc['created_at'][:10]}",
            f"updated: {TODAY}",
            "source: items.json (FreeformBackend)",
            "---",
            "",
        ]
        body = [
            f"# {ucid} — {title}",
            "",
            parent_link.rstrip(),
            "",
            "## Objetivo / Descripción",
            "",
            desc or "_Sin descripción en el board. El detalle vive en el PRD/plan de la US._",
            "",
            "## Acceptance Criteria",
            "",
            ac_section,
            "",
            "## Notas",
            "",
            "_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o "
            "regenerar con `.quality/scripts/generate-readable-tracking.py`._",
            "",
        ]
        (uc_dir / uc["_fname"]).write_text("\n".join(fm + body), encoding="utf-8")

    # ---- index.json ----
    index = {
        "project": "specbox-engine",
        "schema_version": "1.0",
        "backend": "freeform",
        "updated": TODAY,
        "source_of_truth": "doc/tracking/items.json",
        "readable_layers": {
            "us": f"doc/tracking/us/ ({len(us_items)} markdowns)",
            "uc": f"doc/tracking/uc/ ({len(uc_items)} markdowns)",
            "progress": "doc/tracking/progress/ (auto-generado por FreeformBackend)",
        },
        "note": "us/ y uc/ son capa de LECTURA curada, regenerable. La fuente de verdad es items.json.",
        "counts": {"us": len(us_items), "uc": len(uc_items),
                   "ac": len([i for i in items if i.get("meta", {}).get("tipo") == "AC"])},
    }
    (TRACKING / "index.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    # ---- README.md (índice navegable, orden cronológico) ----
    us_sorted = sorted(us_items, key=lambda u: (u["created_at"], u["id"]))
    us_table = "\n".join(
        f"| {u['_ordinal']} "
        f"| [{u['meta']['us_id']}](us/{u['_fname']}) "
        f"| {strip_prefix(u['name'])} "
        f"| {STATE_MAP.get(u['state'], u['state'])} "
        f"| {len([c for c in children.get(u['id'], []) if c.get('meta', {}).get('tipo') == 'UC'])} |"
        for u in us_sorted
    )
    readme = f"""# Tracking — specbox-engine

Capa de **lectura humana** sobre el FreeformBackend. Cuando necesites revisar
una US o un UC, busca aquí su markdown:

- **[`us/`](us/)** — un `.md` legible por cada User Story ({len(us_items)} docs).
- **[`uc/`](uc/)** — un `.md` legible por cada Use Case con sus ACs y enlace al US padre ({len(uc_items)} docs).
- **[`_templates/`](_templates/)** — plantillas para crear US/UC nuevos a mano.

## Fuente de verdad

| Archivo | Rol | ¿Editar a mano? |
|---------|-----|-----------------|
| `items.json` | Fuente de verdad del FreeformBackend (US/UC/AC) | ❌ vía MCP |
| `config.json`, `labels.json`, `archive.json` | Estado del backend | ❌ vía MCP |
| `comments/`, `attachments/` | Comentarios y evidencia adjunta | ❌ vía MCP |
| `progress/` | Telemetría markdown auto-generada por el backend | ❌ auto |
| **`us/`, `uc/`** | **Capa de lectura curada (regenerable)** | ⚠️ regenerar |
| `index.json` | Índice ligero de esta capa | ⚠️ regenerar |

`us/` y `uc/` se **regeneran** desde `items.json` con:

```bash
python3 .quality/scripts/generate-readable-tracking.py
```

> Editar un `.md` de `us/` o `uc/` a mano se perderá en la próxima regeneración.
> Para cambios persistentes, muta el board vía las tools MCP (`update_uc`, `mark_ac`, …)
> y vuelve a generar.

## User Stories

| # | US | Título | Estado | UCs |
|---|----|--------|--------|-----|
{us_table}

_Generado {TODAY} desde `items.json` ({index['counts']['us']} US · {index['counts']['uc']} UC · {index['counts']['ac']} AC)._
"""
    (TRACKING / "README.md").write_text(readme, encoding="utf-8")

    print(f"OK — {len(us_items)} US, {len(uc_items)} UC generados en doc/tracking/{{us,uc}}/")
    print("    + index.json + README.md")
    if dup_warnings:
        print("\n⚠️  DRIFT detectado en items.json (revisar vía MCP):")
        for w in dup_warnings:
            print(f"    - {w}")


if __name__ == "__main__":
    main()
