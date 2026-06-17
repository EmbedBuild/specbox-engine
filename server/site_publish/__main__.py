"""CLI del publicador de estado del engine (UC-1603 US-16 + UC-2003 US-20).

Entrypoint re-ejecutable de forma aislada — el skill `/release` lo invoca tras bumpear
versión + changelog, y el mantenedor puede re-lanzarlo a mano si la publicación falló:

    SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... \
        uv run python -m server.site_publish

En una sola invocación publica DOS cosas a Supabase:
  1. Estado de release/changelog (US-16): engine_release, engine_changelog_entry, engine_feature.
  2. Inventario de capacidades (US-20): engine_agent, engine_tool, engine_skill, engine_vscode_ext
     — extraído del propio código del engine (agents/*.md, decoradores @*.tool, skills, package.json).

Exit codes:
  0  publicación OK (release/changelog E inventario)
  2  faltan credenciales (SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY)
  3  fallo de publicación (red / HTTP) — el release NO debe abortar por esto

Nunca imprime la credencial.
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

from server.site_publish.inventory import build_capability_inventory, publish_inventory
from server.site_publish.parser import build_engine_state
from server.site_publish.publisher import (
    MissingCredentialsError,
    PublishCredentials,
    publish,
)


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    engine_root = Path(argv[0]) if argv else Path(__file__).resolve().parents[2]

    version_file = engine_root / "ENGINE_VERSION.yaml"
    changelog_file = engine_root / "CHANGELOG.md"

    if not version_file.exists():
        print(f"[site-publish] ERROR: no existe {version_file}", file=sys.stderr)
        return 3

    yaml_text = version_file.read_text(encoding="utf-8")
    changelog_text = changelog_file.read_text(encoding="utf-8") if changelog_file.exists() else None
    state = build_engine_state(yaml_text, changelog_text)

    try:
        creds = PublishCredentials.from_env()
    except MissingCredentialsError as exc:
        print(f"[site-publish] {exc}", file=sys.stderr)
        return 2

    inventory = build_capability_inventory(engine_root)
    ext_version = inventory.vscode_ext.version if inventory.vscode_ext else "—"

    print(
        f"[site-publish] Publicando estado del engine v{state.release.version} "
        f"({len(state.features)} features, {len(state.changelog)} versiones de changelog) "
        f"+ inventario ({len(inventory.agents)} agentes, {len(inventory.tools)} tools, "
        f"{len(inventory.skills)} skills, ext v{ext_version})…"
    )
    with httpx.Client(timeout=30.0) as client:
        result = publish(state, creds, client)
        if not result.ok:
            print(f"[site-publish] FALLO (release/changelog): {result.message}", file=sys.stderr)
            return 3

        inv_result = publish_inventory(inventory, creds, client)
        if not inv_result.ok:
            print(f"[site-publish] FALLO (inventario): {inv_result.message}", file=sys.stderr)
            return 3

    total_steps = result.steps + inv_result.steps
    print(f"[site-publish] OK — {total_steps} pasos aplicados a Supabase (release + inventario).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
