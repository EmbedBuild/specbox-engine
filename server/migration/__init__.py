"""Reusable migration foundations for N×N backend migration (UC-401).

This package extracts the backend-construction dispatch and the generic
write logic from ``server/tools/migration.py`` so that they can be reused
across all four backends (FreeForm / Trello / Plane / Native).

The full ``migrate_backend`` tool that wires these together lives in UC-404.
"""

from __future__ import annotations

from .backend_dispatch import VALID_BACKENDS, build_backend
from .writer import write_target

__all__ = ["VALID_BACKENDS", "build_backend", "write_target"]
