"""The project's design system as the engine sees it (US-49).

- :mod:`.tokens` — parse ``design-system.tokens.json`` (pure).
- :mod:`.conformance` — which values of a document are outside the system.
- :mod:`.provenance` — visual-provider output is a candidate; notice for
  projects without tokens.
"""

from __future__ import annotations

from .conformance import Deviation, allowed_values, find_values_outside
from .provenance import (
    DESIGN_ROLE_CANDIDATE,
    candidate_html_banner,
    candidate_marker,
    mark_html_as_candidate,
    system_tokens_notice,
)
from .tokens import (
    SYSTEM_TOKENS_CANDIDATE_PATHS,
    SYSTEM_TOKENS_FILENAME,
    SYSTEM_TOKENS_GUIDE_URL,
    SystemTokens,
    SystemTokensError,
    parse_system_tokens,
)

__all__ = [
    "DESIGN_ROLE_CANDIDATE",
    "SYSTEM_TOKENS_CANDIDATE_PATHS",
    "SYSTEM_TOKENS_FILENAME",
    "SYSTEM_TOKENS_GUIDE_URL",
    "Deviation",
    "SystemTokens",
    "SystemTokensError",
    "allowed_values",
    "candidate_html_banner",
    "candidate_marker",
    "find_values_outside",
    "mark_html_as_candidate",
    "parse_system_tokens",
    "system_tokens_notice",
]
