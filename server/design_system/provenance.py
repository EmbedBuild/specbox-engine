"""Where a design comes from and what it is worth (US-49 · UC-4901 AC-02, AC-03).

- Every screen a visual provider produces (Stitch, Claude Design) is a
  **candidate**: it helps decide layout, hierarchy and flow, and is never a
  production source. Tool responses carry :func:`candidate_marker`; the HTML a
  skill saves starts with :func:`candidate_html_banner`.
- A project without system tokens gets :func:`system_tokens_notice`: what is
  missing, how to adopt the tokens, and the link to the guide.
"""

from __future__ import annotations

from typing import Any

from ..coordination.i18n_messages import DEFAULT_LOCALE, SupportedLocale, translate
from .tokens import SYSTEM_TOKENS_CANDIDATE_PATHS, SYSTEM_TOKENS_FILENAME, SYSTEM_TOKENS_GUIDE_URL

DESIGN_ROLE_CANDIDATE = "candidate"
PRODUCTION_SOURCE = "system_tokens"
CANDIDATE_BANNER_MARK = "specbox:design-role=candidate"

_PROVIDER_NAMES = {"stitch": "Stitch", "claude_design": "Claude Design"}


def _provider_name(provider: str) -> str:
    return _PROVIDER_NAMES.get(provider, provider)


def candidate_note(provider: str, locale: SupportedLocale = DEFAULT_LOCALE) -> str:
    return translate("design_candidate_note", locale).format(provider=_provider_name(provider))


def candidate_html_banner(provider: str, locale: SupportedLocale = DEFAULT_LOCALE) -> str:
    """HTML comment to put first in a saved design file."""
    note = candidate_note(provider, locale).replace("--", "—")
    return f"<!-- {CANDIDATE_BANNER_MARK} · {note} -->"


def mark_html_as_candidate(html: str, provider: str, locale: SupportedLocale = DEFAULT_LOCALE) -> str:
    """Prepend the candidate banner once (idempotent)."""
    if CANDIDATE_BANNER_MARK in html[:2048]:
        return html
    return f"{candidate_html_banner(provider, locale)}\n{html}"


def candidate_marker(provider: str, locale: SupportedLocale = DEFAULT_LOCALE) -> dict[str, Any]:
    """Fields every visual-provider response carries."""
    return {
        "design_role": DESIGN_ROLE_CANDIDATE,
        "production_source": PRODUCTION_SOURCE,
        "design_role_note": candidate_note(provider, locale),
        "html_banner": candidate_html_banner(provider, locale),
    }


def system_tokens_notice(locale: SupportedLocale = DEFAULT_LOCALE) -> dict[str, Any]:
    """What a project without system tokens is told (AC-03)."""
    return {
        "code": "SYSTEM_TOKENS_MISSING",
        "message": translate("system_tokens_missing", locale).format(guide_url=SYSTEM_TOKENS_GUIDE_URL),
        "guide_url": SYSTEM_TOKENS_GUIDE_URL,
        "file": SYSTEM_TOKENS_FILENAME,
        "looked_in": list(SYSTEM_TOKENS_CANDIDATE_PATHS),
        "locale": locale,
    }
