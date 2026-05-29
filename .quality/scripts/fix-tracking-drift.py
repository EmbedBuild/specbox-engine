#!/usr/bin/env python3
"""
fix-tracking-drift.py — Limpieza puntual de drift en doc/tracking/items.json.

Edición DIRECTA del FreeformBackend (fuente de verdad local). Necesario porque el
MCP corre remoto (SPECBOX_ENGINE_MCP_URL) y no puede tocar el filesystem local —
ver BLOCKER FreeForm+remote-MCP en CLAUDE.md.

Dos correcciones:

  1. Colisión de uc_id (uc_id son globales en FreeForm): US-BACKEND-SWITCH reusó
     UC-401..406 que ya pertenecían a US-NATIVE-SUPABASE (más antiguo). Renumera
     el bloque de US-BACKEND-SWITCH a UC-801..806. Toca meta.uc_id + nombre [UC-XXX]
     del UC, y meta.us_id NO cambia. Los AC hijos no referencian el uc_id, pero su
     nombre [AC-XX] no cambia.

  2. US-MCP-OBSERVABILITY duplicado: item-fb79f388 es un huérfano vacío (0 hijos),
     recreado 5 min después como item-696f1953 (con 8 UCs). Se mueve el vacío a
     archive.json.

Idempotente con guardas: si ya está aplicado, no hace nada y lo reporta.
Backup .bak antes de escribir.
"""
from __future__ import annotations
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRACKING = ROOT / "doc" / "tracking"
ITEMS = TRACKING / "items.json"
ARCHIVE = TRACKING / "archive.json"

# --- Correcciones declarativas ---
BACKEND_SWITCH_US_ID = "US-BACKEND-SWITCH"
UC_RENUMBER = {  # old -> new (solo el bloque de US-BACKEND-SWITCH)
    "UC-401": "UC-801",
    "UC-402": "UC-802",
    "UC-403": "UC-803",
    "UC-404": "UC-804",
    "UC-405": "UC-805",
    "UC-406": "UC-806",
}
ORPHAN_OBSERVABILITY_ITEM = "item-fb79f388"  # US-MCP-OBSERVABILITY vacío


def renumber_name(name: str, old: str, new: str) -> str:
    """Reemplaza [UC-401] -> [UC-801] o 'UC-401:' -> 'UC-801:' al inicio del nombre."""
    return re.sub(rf"(\[){re.escape(old)}(\])", rf"\g<1>{new}\g<2>", name, count=1)


def main(apply: bool) -> None:
    items = json.loads(ITEMS.read_text(encoding="utf-8"))
    by_id = {i["id"]: i for i in items}

    # localizar la US BACKEND-SWITCH
    bs_us = next(
        (i for i in items
         if i.get("meta", {}).get("tipo") == "US"
         and i["meta"].get("us_id") == BACKEND_SWITCH_US_ID),
        None,
    )
    if not bs_us:
        raise SystemExit(f"FATAL: no encuentro la US {BACKEND_SWITCH_US_ID}")

    # UCs hijos de BACKEND-SWITCH a renumerar
    changes: list[str] = []
    renumbered_ucs = 0
    for it in items:
        if (it.get("parent_id") == bs_us["id"]
                and it.get("meta", {}).get("tipo") == "UC"):
            old = it["meta"].get("uc_id")
            if old in UC_RENUMBER:
                new = UC_RENUMBER[old]
                changes.append(f"UC renumber: {old} -> {new}  ({it['id']})")
                if apply:
                    it["meta"]["uc_id"] = new
                    it["name"] = renumber_name(it["name"], old, new)
                renumbered_ucs += 1

    # archivar huérfano de OBSERVABILITY
    orphan = by_id.get(ORPHAN_OBSERVABILITY_ITEM)
    archive_orphan = False
    if orphan:
        kids = [i for i in items if i.get("parent_id") == orphan["id"]]
        if kids:
            changes.append(
                f"SKIP archivar {ORPHAN_OBSERVABILITY_ITEM}: tiene {len(kids)} hijos (NO es el vacío)"
            )
        else:
            archive_orphan = True
            changes.append(
                f"ARCHIVE: {ORPHAN_OBSERVABILITY_ITEM} (US-MCP-OBSERVABILITY vacío, 0 hijos)"
            )
    else:
        changes.append(f"SKIP archivar {ORPHAN_OBSERVABILITY_ITEM}: ya no está en items.json")

    print(f"{'APLICANDO' if apply else 'DRY-RUN'} — {len(changes)} acciones:")
    for c in changes:
        print(f"  - {c}")

    if not apply:
        print("\n(dry-run; re-ejecutar con --apply para escribir)")
        return

    # --- escribir ---
    shutil.copy(ITEMS, ITEMS.with_suffix(".json.bak"))

    new_items = items
    if archive_orphan:
        shutil.copy(ARCHIVE, ARCHIVE.with_suffix(".json.bak"))
        archive = json.loads(ARCHIVE.read_text(encoding="utf-8"))
        archive.append(orphan)
        ARCHIVE.write_text(json.dumps(archive, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        new_items = [i for i in items if i["id"] != ORPHAN_OBSERVABILITY_ITEM]

    ITEMS.write_text(json.dumps(new_items, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # --- verificación post: 0 uc_id duplicados ---
    check = json.loads(ITEMS.read_text(encoding="utf-8"))
    from collections import Counter
    uc_counts = Counter(
        i["meta"]["uc_id"] for i in check if i.get("meta", {}).get("tipo") == "UC"
    )
    us_counts = Counter(
        i["meta"]["us_id"] for i in check if i.get("meta", {}).get("tipo") == "US"
    )
    dup_uc = {k: v for k, v in uc_counts.items() if v > 1}
    dup_us = {k: v for k, v in us_counts.items() if v > 1}
    print(f"\nVERIFICACIÓN post-escritura:")
    print(f"  UC totales: {sum(uc_counts.values())}  | uc_id duplicados: {dup_uc or 'ninguno ✓'}")
    print(f"  US totales: {sum(us_counts.values())}  | us_id duplicados: {dup_us or 'ninguno ✓'}")
    print(f"  Renumerados: {renumbered_ucs} UC  | Archivados: {1 if archive_orphan else 0}")
    print(f"\nBackup: {ITEMS.name}.bak")


if __name__ == "__main__":
    import sys
    main(apply="--apply" in sys.argv)
