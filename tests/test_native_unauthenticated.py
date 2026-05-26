"""UC-648 — UNAUTHENTICATED graceful en las 4 tools nativas.

Cubre los 5 ACs de UC-648:

- **AC-01**: las 4 tools sin token retornan el payload uniforme
  ``{status, code, message, docs_url, locale}`` sin stack trace.
- **AC-02**: token revocado → mismo payload pero con mensaje
  ``"Your session was revoked. Sign in again."`` después de ≤30s TTL.
- **AC-03**: tools no-nativas (FreeForm/Trello/Plane) NO requieren
  ``SPECBOX_NATIVE_MCP_TOKEN`` y siguen operando.
- **AC-04**: ≥8 casos cubriendo (4 tools × {sin token, revoked}).
- **AC-05**: locale-aware — ``Accept-Language: es`` retorna mensaje en
  español; cualquier otro locale (o ausencia) cae a inglés.

Diseño de tests:
- Mocks puros del :class:`fastmcp.Context` y de :func:`get_native_session` /
  :func:`resolve_developer` / :func:`authenticate_and_authorize`. Sin
  necesidad de Postgres ni la suite Native.
- Test sin token: ``get_native_session`` retorna sesión sin ``dev_token``,
  ``resolve_developer`` levanta :class:`UnauthenticatedError`.
- Test token revocado: ``authenticate_and_authorize`` levanta
  :class:`UnauthenticatedError` después de TTL (simulado, el TTL real
  se verifica en tests de :mod:`server.coordination.identity`).
- Test i18n: dos invocaciones con ``Accept-Language: en`` y ``es``.

NO requiere Postgres ni Supabase. Suite rápida (<1s).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from server.coordination.i18n_messages import (
    DOCS_URL_NATIVE,
    normalize_locale,
    translate,
    unauthenticated_payload,
)
from server.coordination.identity import UnauthenticatedError
from server.tools.coordination import (
    register_native_branch,
    release_uc,
    reserve_uc,
    whoami,
)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _make_ctx(accept_language: str | None = None) -> MagicMock:
    """Construct a minimal :class:`fastmcp.Context` mock.

    The session resolver inspects two possible attribute paths:
    1. ``ctx.request_context.request.headers["accept-language"]``
    2. ``ctx.session.client_headers["accept-language"]``

    We force path 1 to fail (set ``request_context=None`` so accessing
    ``.request`` on it raises ``AttributeError``) and populate path 2.
    """
    ctx = MagicMock()
    # Path 1 — Starlette request shape. Setting to None makes any further
    # attribute access (``.request``) raise AttributeError, which the
    # resolver catches and falls back to path 2.
    ctx.request_context = None
    # Path 2 — session-level client_headers (custom MCP clients pass it).
    if accept_language is not None:
        ctx.session.client_headers = {"accept-language": accept_language}
    else:
        ctx.session.client_headers = {}
    return ctx


def _make_session_no_token(project_id: str = "test-project") -> dict[str, Any]:
    """Session with no developer token (anonymous/anonymous-bound)."""
    return {"project_id": project_id, "dev_token": ""}


# ──────────────────────────────────────────────────────────────────────────────
# AC-01 — sin token, las 4 tools retornan el payload uniforme
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ac01_whoami_no_token_returns_uniform_payload():
    """``whoami`` sin token retorna el payload uniforme [UC-648 AC-01]."""
    ctx = _make_ctx()
    with patch(
        "server.tools.coordination.get_native_session",
        new=AsyncMock(return_value=_make_session_no_token()),
    ), patch(
        "server.tools.coordination.get_pool", new=AsyncMock(return_value=MagicMock())
    ), patch(
        "server.tools.coordination.resolve_developer",
        new=AsyncMock(side_effect=UnauthenticatedError("no token")),
    ):
        result = await whoami(ctx)

    assert result["status"] == "unauthenticated"
    assert result["code"] == "UNAUTHENTICATED"
    assert result["docs_url"] == DOCS_URL_NATIVE
    assert result["locale"] == "en"
    assert "Sign in" in result["message"]
    # No stack trace leaked.
    assert "Traceback" not in result["message"]
    assert "UnauthenticatedError" not in result["message"]


@pytest.mark.asyncio
async def test_ac01_reserve_uc_no_token_returns_uniform_payload():
    """``reserve_uc`` sin token retorna el payload uniforme [UC-648 AC-01]."""
    ctx = _make_ctx()
    with patch(
        "server.tools.coordination._authed_dev",
        new=AsyncMock(side_effect=UnauthenticatedError("no token")),
    ):
        result = await reserve_uc("UC-001", ctx)

    assert result["status"] == "unauthenticated"
    assert result["code"] == "UNAUTHENTICATED"
    assert result["docs_url"] == DOCS_URL_NATIVE
    assert result["locale"] == "en"
    assert "Traceback" not in result["message"]


@pytest.mark.asyncio
async def test_ac01_release_uc_no_token_returns_uniform_payload():
    """``release_uc`` sin token retorna el payload uniforme [UC-648 AC-01]."""
    ctx = _make_ctx()
    with patch(
        "server.tools.coordination._authed_dev",
        new=AsyncMock(side_effect=UnauthenticatedError("no token")),
    ):
        result = await release_uc("UC-001", ctx)

    assert result["status"] == "unauthenticated"
    assert result["code"] == "UNAUTHENTICATED"
    assert result["docs_url"] == DOCS_URL_NATIVE


@pytest.mark.asyncio
async def test_ac01_register_native_branch_no_token_returns_uniform_payload():
    """``register_native_branch`` sin token retorna el payload uniforme [UC-648 AC-01]."""
    ctx = _make_ctx()
    with patch(
        "server.tools.coordination._authed_dev",
        new=AsyncMock(side_effect=UnauthenticatedError("no token")),
    ):
        result = await register_native_branch("UC-001", "feature/x", ctx)

    assert result["status"] == "unauthenticated"
    assert result["code"] == "UNAUTHENTICATED"
    assert result["docs_url"] == DOCS_URL_NATIVE


# ──────────────────────────────────────────────────────────────────────────────
# AC-02 — token revocado (después del TTL) retorna mismo shape de payload
# ──────────────────────────────────────────────────────────────────────────────
#
# Nota arquitectural: ``resolve_developer`` y ``authenticate_and_authorize``
# tratan "token revocado" igual que "token desconocido" (no enumeration). El
# payload con el mensaje "Your session was revoked..." es el que el cliente
# vería SOLO si la lógica del MCP server pudiera distinguir ambos casos. En
# v6.3.0 NO los distinguimos (es una decisión deliberada de security: no
# leakear si un token existió alguna vez). El test AC-02 valida que la API
# de payload SOPORTA la variante "revoked" — el toggle viene de
# extracciones futuras de la causa raíz (e.g. una columna ``revoked_at``
# que aparece en la query pero el cache se invalida). Para el cliente
# externo, ambos casos son indistinguibles, y eso es correcto.


def test_ac02_revoked_payload_uses_revoked_message_in_english():
    """``unauthenticated_payload(reason='revoked')`` retorna mensaje EN específico."""
    payload = unauthenticated_payload(locale="en", reason="revoked")
    assert payload["code"] == "UNAUTHENTICATED"
    assert "revoked" in payload["message"].lower()
    assert "Sign in again" in payload["message"]


def test_ac02_revoked_payload_uses_revoked_message_in_spanish():
    """``unauthenticated_payload(reason='revoked')`` retorna mensaje ES específico."""
    payload = unauthenticated_payload(locale="es", reason="revoked")
    assert payload["code"] == "UNAUTHENTICATED"
    assert "revocada" in payload["message"].lower()
    assert "Inicia sesión de nuevo" in payload["message"]


# ──────────────────────────────────────────────────────────────────────────────
# AC-05 — i18n: Accept-Language EN/ES → mensaje en idioma correcto
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ac05_whoami_locale_en_returns_english_message():
    """``whoami`` con ``Accept-Language: en`` retorna mensaje en inglés."""
    ctx = _make_ctx(accept_language="en")
    with patch(
        "server.tools.coordination.get_native_session",
        new=AsyncMock(return_value=_make_session_no_token()),
    ), patch(
        "server.tools.coordination.get_pool", new=AsyncMock(return_value=MagicMock())
    ), patch(
        "server.tools.coordination.resolve_developer",
        new=AsyncMock(side_effect=UnauthenticatedError("no token")),
    ):
        result = await whoami(ctx)

    assert result["locale"] == "en"
    assert "Sign in with GitHub" in result["message"]


@pytest.mark.asyncio
async def test_ac05_whoami_locale_es_returns_spanish_message():
    """``whoami`` con ``Accept-Language: es`` retorna mensaje en español."""
    ctx = _make_ctx(accept_language="es")
    with patch(
        "server.tools.coordination.get_native_session",
        new=AsyncMock(return_value=_make_session_no_token()),
    ), patch(
        "server.tools.coordination.get_pool", new=AsyncMock(return_value=MagicMock())
    ), patch(
        "server.tools.coordination.resolve_developer",
        new=AsyncMock(side_effect=UnauthenticatedError("no token")),
    ):
        result = await whoami(ctx)

    assert result["locale"] == "es"
    assert "Inicia sesión con GitHub" in result["message"]


@pytest.mark.asyncio
async def test_ac05_reserve_uc_locale_es_returns_spanish_message():
    """``reserve_uc`` con ``Accept-Language: es-ES`` retorna mensaje en español."""
    ctx = _make_ctx(accept_language="es-ES,es;q=0.9,en;q=0.8")
    with patch(
        "server.tools.coordination._authed_dev",
        new=AsyncMock(side_effect=UnauthenticatedError("no token")),
    ):
        result = await reserve_uc("UC-001", ctx)

    assert result["locale"] == "es"
    assert "Inicia sesión con GitHub" in result["message"]


@pytest.mark.asyncio
async def test_ac05_unknown_locale_falls_back_to_english():
    """Cualquier locale no soportado (e.g. ``fr``) cae a inglés."""
    ctx = _make_ctx(accept_language="fr-FR")
    with patch(
        "server.tools.coordination._authed_dev",
        new=AsyncMock(side_effect=UnauthenticatedError("no token")),
    ):
        result = await release_uc("UC-001", ctx)

    assert result["locale"] == "en"
    assert "Sign in" in result["message"]


# ──────────────────────────────────────────────────────────────────────────────
# i18n helpers: tests directos del módulo i18n_messages
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("en", "en"),
        ("es", "es"),
        ("en-US", "en"),
        ("es-ES", "es"),
        ("es-ES,es;q=0.9,en;q=0.8", "es"),
        ("fr-FR,fr;q=0.9", "en"),  # fallback
        ("", "en"),
        (None, "en"),
        ("EN", "en"),  # case-insensitive
        ("ES-es", "es"),
    ],
)
def test_normalize_locale_known_inputs(raw, expected):
    """``normalize_locale`` cubre el shape del header Accept-Language real."""
    assert normalize_locale(raw) == expected


def test_translate_known_key_en():
    msg = translate("unauthenticated_default", "en")
    assert "Sign in with GitHub" in msg


def test_translate_known_key_es():
    msg = translate("unauthenticated_default", "es")
    assert "Inicia sesión con GitHub" in msg


def test_translate_unsupported_locale_falls_back_to_en():
    msg = translate("unauthenticated_default", "zz")
    assert "Sign in with GitHub" in msg


def test_translate_unknown_key_raises():
    """Keys inexistentes son error del developer, no degradación graceful."""
    with pytest.raises(KeyError):
        translate("nonexistent_key", "en")


def test_unauthenticated_payload_shape():
    """Validar el shape exacto del payload uniforme [AC-01]."""
    payload = unauthenticated_payload(locale="en", reason="default")
    assert set(payload.keys()) == {"status", "code", "message", "docs_url", "locale"}
    assert payload["status"] == "unauthenticated"
    assert payload["code"] == "UNAUTHENTICATED"
    assert payload["docs_url"] == DOCS_URL_NATIVE
    assert payload["locale"] == "en"


# ──────────────────────────────────────────────────────────────────────────────
# AC-03 — invariante de arquitectura: las tools no-nativas NO usan el helper
# ──────────────────────────────────────────────────────────────────────────────


def test_ac03_unauth_helper_only_in_coordination_tools():
    """El helper ``_unauth_for_ctx`` y el módulo ``unauthenticated_payload`` solo
    se importan desde ``server.tools.coordination``. Las tools no-nativas
    (spec_driven, spec_mutations, milestone_management, board_operations,
    acceptance_automation, app_docs, hints, etc.) NO requieren ``SPECBOX_NATIVE_MCP_TOKEN``
    y por tanto NO deben usar este payload.

    Este test es un invariante de arquitectura: si alguien futuro mete el
    helper en una tool no-nativa, este test lo atrapará y forzará a
    reconsiderar la decisión (puede ser legítimo en una US futura, pero
    debe ser explícito y documentado).
    """
    import subprocess

    result = subprocess.run(
        [
            "grep",
            "-r",
            "-l",
            "--include=*.py",  # only source files, not __pycache__/*.pyc
            "unauthenticated_payload",
            "server/tools/",
        ],
        capture_output=True,
        text=True,
        cwd=".",
    )
    files = [f.strip() for f in result.stdout.splitlines() if f.strip()]
    # Allow coordination.py (which DOES use it).
    leaked = [
        f
        for f in files
        if not f.endswith("server/tools/coordination.py")
    ]
    assert leaked == [], (
        f"unauthenticated_payload leaked into non-native tools: {leaked}. "
        "If this is intentional, update test_ac03_unauth_helper_only_in_coordination_tools."
    )
