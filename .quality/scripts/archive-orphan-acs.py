#!/usr/bin/env python3
"""
archive-orphan-acs.py — Mueve a archive.json los AC cuyo UC padre ya fue archivado.

Drift de archivado incompleto: al archivar un UC, sus AC hijos se quedaron en
items.json. El backend los ignora (sin UC padre no se renderizan), pero ensucian
el board. Este script los reúne con su padre en archive.json.

Edición directa local (MCP remoto no puede tocar el filesystem local — ver
[[project_mcp_remote_freeform_local]]).

Solo mueve AC cuyo parent_id apunta a un item que YA está en archive.json. Cualquier
AC con padre vivo (UC en items.json) o padre inexistente se reporta y se DEJA.
Idempotente. Backup .bak. Dry-run por defecto.
"""
from __future__ import annotations
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRACKING = ROOT / "doc" / "tracking"
ITEMS = TRACKING / "items.json"
ARCHIVE = TRACKING / "archive.json"


def main(apply: bool) -> None:
    items = json.loads(ITEMS.read_text(encoding="utf-8"))
    archive = json.loads(ARCHIVE.read_text(encoding="utf-8"))

    archive_ids = {a["id"] for a in archive}
    uc_item_ids = {i["id"] for i in items if i.get("meta", {}).get("tipo") == "UC"}

    to_move: list[dict] = []
    skipped: list[str] = []
    for a in items:
        if a.get("meta", {}).get("tipo") != "AC":
            continue
        pid = a.get("parent_id")
        if pid in uc_item_ids:
            continue  # AC sano, su UC está vivo
        # huérfano: clasificar destino
        if pid in archive_ids:
            to_move.append(a)
        elif pid in {i["id"] for i in items}:
            skipped.append(f"{a['id']}: parent {pid} sigue en items.json pero no es UC — DEJADO")
        else:
            skipped.append(f"{a['id']}: parent {pid} no existe ni en items ni archive — DEJADO")

    print(f"{'APLICANDO' if apply else 'DRY-RUN'} — mover {len(to_move)} AC a archive.json")
    # resumen por UC padre
    from collections import Counter
    by_parent = Counter(a["parent_id"] for a in to_move)
    arch_names = {x["id"]: x["name"] for x in archive}
    for pid, n in sorted(by_parent.items()):
        print(f"  {n} AC <- {arch_names.get(pid, pid)[:60]}")
    for s in skipped:
        print(f"  SKIP {s}")

    if not apply:
        print("\n(dry-run; re-ejecutar con --apply para escribir)")
        return

    if not to_move:
        print("\nNada que mover. Ya limpio.")
        return

    shutil.copy(ITEMS, ITEMS.with_suffix(".json.bak"))
    shutil.copy(ARCHIVE, ARCHIVE.with_suffix(".json.bak"))

    move_ids = {a["id"] for a in to_move}
    new_items = [i for i in items if i["id"] not in move_ids]
    new_archive = archive + to_move

    ITEMS.write_text(json.dumps(new_items, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    ARCHIVE.write_text(json.dumps(new_archive, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # verificación post
    check = json.loads(ITEMS.read_text(encoding="utf-8"))
    uc_ids2 = {i["id"] for i in check if i.get("meta", {}).get("tipo") == "UC"}
    remaining = [
        a["id"] for a in check
        if a.get("meta", {}).get("tipo") == "AC" and a.get("parent_id") not in uc_ids2
    ]
    print(f"\nVERIFICACIÓN: AC huérfanos restantes en items.json: {len(remaining)}")
    print(f"  items.json: {len(new_items)} (era {len(items)})")
    print(f"  archive.json: {len(new_archive)} (era {len(archive)})")
    print(f"  Backups: items.json.bak, archive.json.bak")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
