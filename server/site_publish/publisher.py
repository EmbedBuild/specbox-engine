"""Publicador del estado del engine a Supabase (UC-1602, US-16).

Hace UPSERT idempotente de un EngineState a las tablas `public.engine_release`,
`public.engine_feature` y `public.engine_changelog_entry` vía la REST API de Supabase
(PostgREST), autenticado con el **service-role key** (que bypassa RLS — las tablas son
solo-lectura para anon).

Seguridad (AC-03): la credencial se lee de variables de entorno y NUNCA se imprime. El
helper `_redact` enmascara cualquier secreto en los logs/errores.

Testabilidad (AC-01/02): la lógica que decide *qué* peticiones hacer
(`build_publish_requests`) es pura y separada del transporte HTTP (`publish` con un
cliente inyectable), de modo que se puede testear sin red.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from server.site_publish.parser import EngineState


SUPABASE_URL_ENV = "SUPABASE_URL"
SERVICE_ROLE_ENV = "SUPABASE_SERVICE_ROLE_KEY"


@dataclass
class PublishRequest:
    """Una petición REST a PostgREST (método, path relativo, params, body, headers extra)."""

    method: str
    path: str  # p.ej. "/rest/v1/engine_release"
    params: dict[str, str]
    json: list[dict] | dict | None
    prefer: str = ""  # cabecera Prefer (p.ej. "resolution=merge-duplicates")


@dataclass
class PublishCredentials:
    url: str
    service_role_key: str

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "PublishCredentials":
        env = env if env is not None else dict(os.environ)
        url = (env.get(SUPABASE_URL_ENV) or "").rstrip("/")
        key = env.get(SERVICE_ROLE_ENV) or ""
        if not url or not key:
            raise MissingCredentialsError(
                f"Faltan credenciales: define {SUPABASE_URL_ENV} y {SERVICE_ROLE_ENV} "
                f"en el entorno (service-role, no anon key)."
            )
        return cls(url=url, service_role_key=key)


class MissingCredentialsError(RuntimeError):
    """Se lanza cuando faltan SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY."""


def _redact(text: str, *secrets: str) -> str:
    """Enmascara secretos en un texto antes de loguear (AC-03)."""
    out = text
    for secret in secrets:
        if secret and secret in out:
            out = out.replace(secret, "***REDACTED***")
    return out


def build_publish_requests(state: EngineState) -> list[PublishRequest]:
    """Construye la secuencia de peticiones idempotentes para publicar el EngineState.

    Orden (importa por la FK changelog->release y por el índice único de is_current):
      1. Poner is_current=false en TODAS las releases (PATCH global).
      2. UPSERT de engine_release de la versión actual con is_current=true.
      3. UPSERT del histórico de releases del changelog (is_current=false) para satisfacer
         la FK de engine_changelog_entry.
      4. UPSERT de engine_feature (catálogo completo).
      5. UPSERT de engine_changelog_entry (todas las versiones con highlights).

    Todo UPSERT usa Prefer: resolution=merge-duplicates → idempotente (AC-01).
    """
    requests: list[PublishRequest] = []
    current_version = state.release.version

    # 1. Reset de is_current (PATCH a todas las filas donde is_current=true).
    requests.append(
        PublishRequest(
            method="PATCH",
            path="/rest/v1/engine_release",
            params={"is_current": "eq.true"},
            json={"is_current": False},
        )
    )

    # 3 (pre). Histórico de releases derivado del changelog, para que la FK del changelog
    # no falle. La versión actual se sobrescribe en el paso 2 con is_current=true.
    release_rows: list[dict] = []
    seen_versions: set[str] = set()
    for entry in state.changelog:
        if entry.version in seen_versions:
            continue
        seen_versions.add(entry.version)
        release_rows.append(
            {
                "version": entry.version,
                "codename": entry.codename or "",
                "release_date": entry.release_date or None,
                "min_claude_code": "",
                "is_current": False,
            }
        )
    if release_rows:
        requests.append(
            PublishRequest(
                method="POST",
                path="/rest/v1/engine_release",
                params={},
                json=release_rows,
                prefer="resolution=merge-duplicates",
            )
        )

    # 2. UPSERT de la release ACTUAL con is_current=true (gana sobre el histórico).
    requests.append(
        PublishRequest(
            method="POST",
            path="/rest/v1/engine_release",
            params={},
            json=[
                {
                    "version": current_version,
                    "codename": state.release.codename or "",
                    "release_date": state.release.release_date or None,
                    "min_claude_code": state.release.min_claude_code or "",
                    "is_current": True,
                }
            ],
            prefer="resolution=merge-duplicates",
        )
    )

    # 4. Catálogo de features.
    feature_rows = [
        {
            "feature_key": f.feature_key,
            "category": f.category or "",
            "since_version": f.since_version or "",
            "status": f.status or "active",
        }
        for f in state.features
    ]
    if feature_rows:
        requests.append(
            PublishRequest(
                method="POST",
                path="/rest/v1/engine_feature",
                params={},
                json=feature_rows,
                prefer="resolution=merge-duplicates",
            )
        )

    # 5. Changelog con highlights.
    changelog_rows = [
        {
            "version": e.version,
            "codename": e.codename or "",
            "release_date": e.release_date or None,
            "public_highlights": e.public_highlights,
        }
        for e in state.changelog
    ]
    if changelog_rows:
        requests.append(
            PublishRequest(
                method="POST",
                path="/rest/v1/engine_changelog_entry",
                params={},
                json=changelog_rows,
                prefer="resolution=merge-duplicates",
            )
        )

    return requests


@dataclass
class PublishResult:
    ok: bool
    steps: int
    failed_step: int | None = None
    message: str = ""


def publish(state: EngineState, creds: PublishCredentials, http_client) -> PublishResult:
    """Ejecuta la publicación con un cliente HTTP inyectable (httpx.Client-compatible).

    `http_client` debe exponer `.request(method, url, params=..., json=..., headers=...)`
    devolviendo un objeto con `.status_code` y `.text` (contrato de httpx).
    No imprime la credencial; cualquier error se redacta con `_redact`.
    """
    base_headers = {
        "apikey": creds.service_role_key,
        "Authorization": f"Bearer {creds.service_role_key}",
        "Content-Type": "application/json",
    }
    requests = build_publish_requests(state)

    for idx, req in enumerate(requests):
        headers = dict(base_headers)
        if req.prefer:
            headers["Prefer"] = req.prefer
        url = f"{creds.url}{req.path}"
        resp = http_client.request(
            req.method, url, params=req.params or None, json=req.json, headers=headers
        )
        status = getattr(resp, "status_code", 0)
        if status < 200 or status >= 300:
            body = _redact(getattr(resp, "text", ""), creds.service_role_key)
            return PublishResult(
                ok=False,
                steps=len(requests),
                failed_step=idx,
                message=f"Paso {idx} ({req.method} {req.path}) falló con HTTP {status}: {body}",
            )

    return PublishResult(ok=True, steps=len(requests), message="Publicación completada")
