"""CLI del publicador de estado del engine (UC-1603, US-16).

Entrypoint re-ejecutable de forma aislada — el skill `/release` lo invoca tras bumpear
versión + changelog, y el mantenedor puede re-lanzarlo a mano si la publicación falló:

    SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... \
        uv run python -m server.site_publish

Exit codes:
  0  publicación OK
  2  faltan credenciales (SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY)
  3  fallo de publicación (red / HTTP) — el release NO debe abortar por esto

Nunca imprime la credencial.
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

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

    print(
        f"[site-publish] Publicando estado del engine v{state.release.version} "
        f"({len(state.features)} features, {len(state.changelog)} versiones de changelog)…"
    )
    with httpx.Client(timeout=30.0) as client:
        result = publish(state, creds, client)

    if result.ok:
        print(f"[site-publish] OK — {result.steps} pasos aplicados a Supabase.")
        return 0

    print(f"[site-publish] FALLO: {result.message}", file=sys.stderr)
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
