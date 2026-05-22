"""Centralized backend construction for the 4 SpecBox backends.

Extracts the dispatch pattern from ``server/auth_gateway.py`` (the canonical
place that already builds the four backends from session credentials) into a
single reusable factory. UC-401 needs this so migration code can build a
*target* backend from arbitrary credentials, independent of the session.

The four valid backend types are FreeForm, Trello, Plane and Native.
"""

from __future__ import annotations

from typing import Any

from ..spec_backend import SpecBackend

#: The four backend types accepted as both migration source and target.
VALID_BACKENDS: tuple[str, ...] = ("freeform", "trello", "plane", "native")


def build_backend(backend_type: str, creds: dict[str, Any]) -> SpecBackend:
    """Construct a :class:`SpecBackend` for one of the four backend types.

    Mirrors the dispatch in ``auth_gateway.get_session_backend`` so the four
    backends are built identically wherever they are needed.

    Args:
        backend_type: One of ``VALID_BACKENDS`` (freeform / trello / plane / native).
        creds: Credential dict. Required keys per backend:
            - ``plane``: ``base_url``, ``api_key``, ``workspace_slug``
            - ``freeform``: ``root_path``
            - ``native``: ``project_id``
            - ``trello``: ``api_key``, ``token``

    Returns:
        A constructed (not yet validated) backend instance.

    Raises:
        ValueError: If ``backend_type`` is not one of the four valid values.
        KeyError: If a required credential for the chosen backend is missing.
    """
    if backend_type not in VALID_BACKENDS:
        valid = ", ".join(VALID_BACKENDS)
        raise ValueError(f"Invalid backend_type {backend_type!r}. Must be one of: {valid}.")

    if backend_type == "plane":
        from ..backends.plane_backend import PlaneBackend

        return PlaneBackend(
            base_url=creds["base_url"],
            api_key=creds["api_key"],
            workspace_slug=creds["workspace_slug"],
        )

    if backend_type == "freeform":
        from ..backends.freeform_backend import FreeformBackend

        return FreeformBackend(root=creds["root_path"])

    if backend_type == "native":
        # FRONTIER 2: only the project_id is passed — never a DSN.
        # The DB credential is read from SPECBOX_NATIVE_DSN by the pool.
        from ..backends.native_backend import NativeBackend

        return NativeBackend(project_id=creds["project_id"])

    # backend_type == "trello"
    from ..backends.trello_backend import TrelloBackend

    return TrelloBackend(api_key=creds["api_key"], token=creds["token"])
