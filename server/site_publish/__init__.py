"""Site publish (US-16): publica el estado del engine al schema público de Supabase.

El site público (`specbox.embed.build`, satélite `site`) refleja el estado real del
engine leyendo tablas `public.engine_*` en Supabase. La única fuente de verdad sigue
siendo el repo (`ENGINE_VERSION.yaml` + `CHANGELOG.md`); este paquete los parsea
(UC-1601) y publica vía UPSERT idempotente (UC-1602), invocado desde `/release`
(UC-1603). Así el site no puede divergir del engine: la única vía de liberar es
también la única vía de publicar.
"""

from server.site_publish.parser import (
    EngineState,
    ReleaseInfo,
    FeatureInfo,
    ChangelogEntry,
    parse_engine_version,
    parse_changelog_md,
    derive_public_highlights,
    build_engine_state,
)
from server.site_publish.publisher import (
    PublishCredentials,
    PublishRequest,
    PublishResult,
    MissingCredentialsError,
    build_publish_requests,
    publish,
)

__all__ = [
    "EngineState",
    "ReleaseInfo",
    "FeatureInfo",
    "ChangelogEntry",
    "parse_engine_version",
    "parse_changelog_md",
    "derive_public_highlights",
    "build_engine_state",
    "PublishCredentials",
    "PublishRequest",
    "PublishResult",
    "MissingCredentialsError",
    "build_publish_requests",
    "publish",
]
