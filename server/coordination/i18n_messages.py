"""Server-side i18n for MCP tool error messages.

v6.3.0 (UC-648) — introduces a server-side translation layer for the
``UNAUTHENTICATED`` payload returned by the 4 native coordination tools
(``whoami``, ``reserve_uc``, ``release_uc``, ``register_native_branch``).

The client (e.g. the VSCode extension's MCP wrapper) may pass an
``Accept-Language`` header in the MCP handshake. The server reads it
from ``ctx.session.client_headers`` (when available) and returns the
message in the requested locale, falling back to English.

This module is intentionally minimal — only the languages and messages
that are actually surfaced to the end user are kept here. Anything more
complex (gettext, Babel) is overkill for ~5 messages × 2 locales.
"""

from __future__ import annotations

from typing import Any

# Two-letter ISO 639-1 codes — anything else falls back to "en".
SupportedLocale = str  # "en" | "es"

DEFAULT_LOCALE: SupportedLocale = "en"
SUPPORTED_LOCALES: frozenset[SupportedLocale] = frozenset({"en", "es"})

# Public docs URL surfaced in every UNAUTHENTICATED payload so the user
# can self-resolve without a stack trace.
DOCS_URL_NATIVE = "https://github.com/EmbedBuild/specbox-engine#native-backend"


#: Codes that the server may surface in an UNAUTHENTICATED payload.
#: ``unauthenticated_default``  — token missing / malformed / unknown.
#: ``unauthenticated_revoked``  — token was valid but has been revoked.
_MESSAGES: dict[str, dict[SupportedLocale, str]] = {
    "unauthenticated_default": {
        "en": "Sign in with GitHub via the VSCode extension or run /onboard.",
        "es": "Inicia sesión con GitHub desde la extensión de VSCode o ejecuta /onboard.",
    },
    "unauthenticated_revoked": {
        "en": "Your session was revoked. Sign in again.",
        "es": "Tu sesión fue revocada. Inicia sesión de nuevo.",
    },
}


def normalize_locale(raw: str | None) -> SupportedLocale:
    """Normalize an ``Accept-Language`` value to a supported locale.

    Accepts a full header value (``"es-ES,es;q=0.9,en;q=0.8"``), a single
    tag (``"es"``), or ``None``. Returns ``"en"`` when no supported locale
    is found.

    Examples:
        >>> normalize_locale("es-ES,es;q=0.9,en;q=0.8")
        'es'
        >>> normalize_locale("en-US")
        'en'
        >>> normalize_locale("fr")
        'en'
        >>> normalize_locale(None)
        'en'
    """
    if not raw:
        return DEFAULT_LOCALE
    # Take the first token of the first language tag.
    # "es-ES,es;q=0.9" → "es-ES" → "es"
    first_tag = raw.split(",", 1)[0].strip()
    base = first_tag.split("-", 1)[0].split(";", 1)[0].strip().lower()
    return base if base in SUPPORTED_LOCALES else DEFAULT_LOCALE


def translate(key: str, locale: SupportedLocale = DEFAULT_LOCALE) -> str:
    """Translate a message key to the requested locale.

    Falls back to English if the key exists but the locale is not
    supported for that key. Raises ``KeyError`` if the key itself is
    unknown (developer error — there is no graceful fallback for typos
    in code paths).
    """
    locale = locale if locale in SUPPORTED_LOCALES else DEFAULT_LOCALE
    entries = _MESSAGES[key]
    return entries.get(locale) or entries[DEFAULT_LOCALE]


def unauthenticated_payload(
    *,
    locale: SupportedLocale = DEFAULT_LOCALE,
    reason: str = "default",
) -> dict[str, Any]:
    """Build the canonical ``UNAUTHENTICATED`` payload for native tools.

    Args:
        locale: Resolved locale (use :func:`normalize_locale` on the raw
            ``Accept-Language`` header before calling).
        reason: ``"default"`` (token absent/malformed) or ``"revoked"``
            (token previously valid but revoked).

    Returns:
        A dict with the exact shape expected by AC-01 of UC-648:
        ``{status, code, message, docs_url, locale}``. No stack trace.
        Callers should set the MCP ``isError`` envelope flag themselves
        — this helper only produces the payload body.
    """
    key = f"unauthenticated_{reason}"
    return {
        "status": "unauthenticated",
        "code": "UNAUTHENTICATED",
        "message": translate(key, locale),
        "docs_url": DOCS_URL_NATIVE,
        "locale": locale,
    }


def extract_locale_from_ctx(ctx: Any) -> SupportedLocale:
    """Best-effort locale extraction from an MCP ``Context``.

    FastMCP's ``Context`` exposes the underlying request through
    ``ctx.request_context.request`` (Starlette ``Request``) in HTTP
    transports, and may not expose headers at all in stdio. This helper
    handles every shape we have seen and falls back to ``"en"``.

    Looks at these attribute paths in order:
        1. ``ctx.request_context.request.headers["accept-language"]``
        2. ``ctx.session.client_headers["accept-language"]``
        3. nothing — fallback to ``"en"``.
    """
    # Path 1 — Starlette request through request_context (HTTP transports)
    try:
        request = ctx.request_context.request  # type: ignore[union-attr]
        headers = request.headers
        raw = headers.get("accept-language") or headers.get("Accept-Language")
        if raw:
            return normalize_locale(raw)
    except (AttributeError, KeyError, TypeError):
        pass

    # Path 2 — custom session-level client_headers (some MCP clients pass it)
    try:
        client_headers = ctx.session.client_headers  # type: ignore[union-attr]
        raw = client_headers.get("accept-language") or client_headers.get(
            "Accept-Language"
        )
        if raw:
            return normalize_locale(raw)
    except (AttributeError, KeyError, TypeError):
        pass

    return DEFAULT_LOCALE
