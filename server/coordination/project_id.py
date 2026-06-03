"""Canonical ``project_id`` contract — single source of truth (UC-818).

The Native backend stores ``projects.project_id`` as free TEXT and historically
uses the GitHub ``owner/repo`` shape (e.g. ``EmbedBuild/specbox_cloud``). The
Cloud panel, by contrast, slugifies project ids (``^[a-z0-9][a-z0-9-]*$``,
lowercase, ``/``→``-``) so the same project would surface as
``embedbuild-specbox-cloud``. The two sides never agreed on a format, which
broke "upload my project to SpecBox Cloud" at the membership gate.

**Decision D1 (discovery ``provision_native_project_id_contract``)**: the
canonical, stored identifier is ``owner/repo`` (case-preserving). The slug is a
**derived, URL-safe projection** used only for display/URLs — never the
identity key. This module is the single point of normalization shared
engine↔panel:

- :func:`canonical_project_id` builds the canonical id from ``owner`` + ``repo``.
- :func:`display_slug` derives the URL-safe slug from a canonical id.
- :func:`validate_project_id` accepts a well-formed ``owner/repo`` id and
  rejects malformed ones with an explicit, identifiable error.

Pure functions, no I/O — safe to call from any layer and trivially testable.
"""

from __future__ import annotations

import re

__all__ = [
    "InvalidProjectIdError",
    "canonical_project_id",
    "display_slug",
    "humanize_project_name",
    "validate_project_id",
]

#: A single non-empty ``owner`` segment, a single ``/`` and a single non-empty
#: ``repo`` segment. Neither segment may itself contain a ``/`` — exactly one
#: separator is allowed. Surrounding whitespace is rejected (callers normalize).
_OWNER_REPO_RE = re.compile(r"^[^/\s]+/[^/\s]+$")

#: Characters allowed verbatim in a display slug. Everything else collapses to
#: a single ``-``. Mirrors the panel's ``^[a-z0-9][a-z0-9-]*$`` target shape.
_SLUG_STRIP_RE = re.compile(r"[^a-z0-9]+")


class InvalidProjectIdError(ValueError):
    """Raised when a string is not a well-formed ``owner/repo`` project id.

    Subclasses :class:`ValueError` so existing ``except ValueError`` paths keep
    working, while callers that care can catch this precise type.
    """


def canonical_project_id(owner: str, repo: str) -> str:
    """Build the canonical ``owner/repo`` project id (case-preserving).

    Joins ``owner`` and ``repo`` with a single ``/`` and validates the result.
    Case is preserved — ``EmbedBuild/specbox_cloud`` stays exactly that; the
    canonical id is the identity key, not a display string.

    Args:
        owner: The GitHub-style owner segment (e.g. ``"EmbedBuild"``).
        repo: The repository segment (e.g. ``"specbox_cloud"``).

    Returns:
        ``"{owner}/{repo}"``.

    Raises:
        InvalidProjectIdError: if either segment is empty/whitespace or itself
            contains a ``/`` (which would produce more than one separator).
    """
    owner_clean = (owner or "").strip()
    repo_clean = (repo or "").strip()
    candidate = f"{owner_clean}/{repo_clean}"
    return validate_project_id(candidate)


def validate_project_id(project_id: str) -> str:
    """Return ``project_id`` unchanged if it is a well-formed ``owner/repo``.

    The canonical form is exactly one non-empty owner segment, one ``/`` and
    one non-empty repo segment. An id already in this shape is accepted
    verbatim (no mutation, case preserved). Anything else — empty, no owner,
    multiple slashes, embedded whitespace — raises.

    Args:
        project_id: The candidate id to validate.

    Returns:
        The same string, confirmed canonical.

    Raises:
        InvalidProjectIdError: when the id is not a single ``owner/repo`` pair.
    """
    if not project_id or not project_id.strip():
        raise InvalidProjectIdError("project_id must be a non-empty 'owner/repo' string")
    if project_id != project_id.strip():
        raise InvalidProjectIdError(
            f"project_id must not have surrounding whitespace: {project_id!r}"
        )
    if not _OWNER_REPO_RE.match(project_id):
        raise InvalidProjectIdError(
            f"project_id must be exactly 'owner/repo' (one '/', no empty segment): "
            f"{project_id!r}"
        )
    return project_id


def humanize_project_name(project_id: str) -> str:
    """Derive a human-readable display name from a canonical ``owner/repo`` id.

    UC-504 (US-05): the Native backend historically defaulted ``projects.name``
    to the raw ``owner/repo`` id, so the Cloud panel showed a cryptic slug as the
    project title. This derives a friendlier default: take the ``repo`` segment,
    split on ``-``/``_``/whitespace, and Capitalize Each Word.

    ``EmbedBuild/specbox-manager`` → ``"Specbox Manager"``
    ``acme/web``                   → ``"Web"``
    ``acme/my_cool_api``           → ``"My Cool Api"``

    Pure, no I/O. The first letter of every word is uppercased (the rest of each
    word is left as-is to preserve intentional casing like ``API`` if a word was
    already uppercase — only the leading char is forced up).

    Args:
        project_id: A canonical ``owner/repo`` id (or a bare repo segment).

    Returns:
        A human display name. Never empty for a non-empty input.
    """
    raw = (project_id or "").strip()
    repo = raw.rsplit("/", 1)[-1] if "/" in raw else raw
    words = [w for w in re.split(r"[-_\s]+", repo) if w]
    if not words:
        return repo
    return " ".join(w[0].upper() + w[1:] for w in words)


def display_slug(project_id: str) -> str:
    """Derive the URL-safe display slug from a canonical ``owner/repo`` id.

    Lowercases and replaces every run of non-``[a-z0-9]`` characters (including
    the ``/`` separator and any ``_``) with a single ``-``, trimming leading and
    trailing ``-``. ``EmbedBuild/specbox_cloud`` → ``embedbuild-specbox-cloud``.

    Idempotent: applying it to an already-derived slug returns the same slug,
    so a caller can safely re-slugify without drift.

    The slug is for display/URLs only — it is **not** an identity key and must
    never be written to ``projects.project_id``.

    Args:
        project_id: A canonical ``owner/repo`` id, or an already-derived slug.

    Returns:
        The URL-safe slug.

    Raises:
        InvalidProjectIdError: when the input slugifies to the empty string
            (e.g. all-separator input), which can never be a usable slug.
    """
    lowered = (project_id or "").lower()
    slug = _SLUG_STRIP_RE.sub("-", lowered).strip("-")
    if not slug:
        raise InvalidProjectIdError(
            f"project_id does not yield a usable display slug: {project_id!r}"
        )
    return slug
