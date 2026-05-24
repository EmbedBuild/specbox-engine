#!/usr/bin/env python3
"""Regenerate templates/canonical_docs.json from server/app_docs/registry.py.

The hook `.claude/hooks/app-docs-sync-guard.mjs` is Node.js and cannot
import Python directly. To keep both sides honest, this script serializes
the `CANONICAL_DOCS` list to a JSON descriptor that the hook reads.

Run after editing `registry.py`:
    python3 .quality/scripts/regenerate-canonical-docs-json.py

CI verifies the regenerated file is byte-equal to the committed one
(`tests/test_canonical_docs_sync.py`). If it differs, the build fails
and the developer must commit the updated JSON.

Source-of-truth resolution: Python (registry.py). The JSON is generated,
never edited manually.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from server.app_docs.registry import CANONICAL_DOCS  # noqa: E402


def serialize() -> str:
    docs = []
    for d in CANONICAL_DOCS:
        docs.append(
            {
                "id": d.id,
                "path": d.path,
                "introduced_in": d.introduced_in,
                "template_path": d.template_path,
                "required_zones": {k: v.value for k, v in d.required_zones.items()},
                "event_zone_map": {k: list(v) for k, v in d.event_zone_map.items()},
            }
        )
    return json.dumps(
        {
            "schema_version": 1,
            "generated_by": ".quality/scripts/regenerate-canonical-docs-json.py",
            "source": "server/app_docs/registry.py",
            "docs": docs,
        },
        indent=2,
        ensure_ascii=False,
        sort_keys=False,
    ) + "\n"


def main() -> int:
    target = REPO_ROOT / "templates" / "canonical_docs.json"
    new = serialize()

    if "--check" in sys.argv:
        if not target.exists():
            print(f"FAIL: {target} does not exist. Run without --check to generate.")
            return 1
        current = target.read_text(encoding="utf-8")
        if current != new:
            print(
                f"FAIL: {target} is out of sync with server/app_docs/registry.py.\n"
                f"Run: python3 .quality/scripts/regenerate-canonical-docs-json.py"
            )
            return 1
        print(f"OK: {target} is in sync with registry.py")
        return 0

    target.write_text(new, encoding="utf-8")
    print(f"Wrote {target} ({len(CANONICAL_DOCS)} canonical docs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
