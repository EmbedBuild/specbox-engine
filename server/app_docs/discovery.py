"""Backend auto-discovery for v5.29.0 (PR-8).

Skills consult `detect_backend(project_path)` in their Paso 0 to know
which spec backend the project uses without asking the user. The detector
applies a 5-level priority chain that mirrors the v5.28 mental model but
makes FreeForm the default when nothing else is configured.

Priority (highest to lowest):
  1. .claude/settings.local.json -> specbox.backend_type (freeform/trello/plane/native)
  2. doc/tracking/items.json present (filesystem signal)
  3. .claude/settings.local.json -> trello.boardId / plane.projectId
  4. doc/app/app_spec.md zone "tracking_backend" body
  5. Default: "freeform" (v5.29.0 recommended default)
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fastmcp import FastMCP


def detect_backend(project_path: str | Path = ".") -> dict[str, Any]:
    """Detect the spec backend a project uses.

    Returns:
        {
          "backend_type": "freeform" | "trello" | "plane" | "native",
          "source": "settings_specbox" | "tracking_dir" | "settings_legacy" |
                     "app_spec" | "default_v5_29",
          "freeform_root_absolute": str | None,  # populated only for freeform
          "trello_board_id": str | None,
          "plane_project_id": str | None,
          "native_project_id": str | None,  # populated only for native
          "warnings": [str, ...],
        }
    """
    root = Path(project_path).resolve()
    warnings: list[str] = []

    settings_path = root / ".claude" / "settings.local.json"
    settings: dict[str, Any] = {}
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            warnings.append(f"settings.local.json invalid JSON: {e}")

    specbox = settings.get("specbox") or {}

    # 1. Explicit specbox.backend_type wins.
    declared = specbox.get("backend_type")
    if declared in {"freeform", "trello", "plane", "native"}:
        return {
            "backend_type": declared,
            "source": "settings_specbox",
            "freeform_root_absolute": specbox.get("freeform_root_absolute"),
            "trello_board_id": specbox.get("trello_board_id"),
            "plane_project_id": specbox.get("plane_project_id"),
            "native_project_id": specbox.get("native_project_id")
            or specbox.get("project_id"),
            "warnings": warnings,
        }

    # 2. doc/tracking/items.json present → strong filesystem signal for FreeForm.
    items_path = root / "doc" / "tracking" / "items.json"
    if items_path.exists():
        return {
            "backend_type": "freeform",
            "source": "tracking_dir",
            "freeform_root_absolute": str(root / "doc" / "tracking"),
            "trello_board_id": None,
            "plane_project_id": None,
            "warnings": warnings,
        }

    # 3. Legacy: settings declares trello.boardId or plane.projectId.
    legacy_trello = (settings.get("trello") or {}).get("boardId") or (settings.get("trello") or {}).get("board_id")
    legacy_plane = (settings.get("plane") or {}).get("projectId")
    if legacy_trello:
        return {
            "backend_type": "trello",
            "source": "settings_legacy",
            "freeform_root_absolute": None,
            "trello_board_id": legacy_trello,
            "plane_project_id": None,
            "warnings": warnings,
        }
    if legacy_plane:
        return {
            "backend_type": "plane",
            "source": "settings_legacy",
            "freeform_root_absolute": None,
            "trello_board_id": None,
            "plane_project_id": legacy_plane,
            "warnings": warnings,
        }

    # 4. doc/app/app_spec.md tracking_backend zone — best-effort text match.
    spec_path = root / "doc" / "app" / "app_spec.md"
    if spec_path.exists():
        backend_from_spec = _extract_backend_from_spec(spec_path)
        if backend_from_spec:
            return {
                "backend_type": backend_from_spec,
                "source": "app_spec",
                "freeform_root_absolute": str(root / "doc" / "tracking")
                if backend_from_spec == "freeform"
                else None,
                "trello_board_id": None,
                "plane_project_id": None,
                "warnings": warnings,
            }

    # 5. Default: freeform — the recommended v5.29.0 default for projects
    # without external client reporting requirements.
    return {
        "backend_type": "freeform",
        "source": "default_v5_29",
        "freeform_root_absolute": str(root / "doc" / "tracking"),
        "trello_board_id": None,
        "plane_project_id": None,
        "warnings": warnings,
    }


_TIPO_LINE = re.compile(r"-\s*\*\*Tipo:\*\*\s*\{?(?P<value>[^|}\n]+?)(?:\s*\||\s*\}|\s*$)", re.MULTILINE)
_TIPO_LINE_PLAIN = re.compile(r"^\s*-\s*Tipo:\s*(?P<value>[^|\n]+?)\s*$", re.MULTILINE)


def _extract_backend_from_spec(spec_path: Path) -> str | None:
    try:
        content = spec_path.read_text(encoding="utf-8")
    except OSError:
        return None
    # Try both common formattings: "- **Tipo:** ..." and "- Tipo: ..."
    for pattern in (_TIPO_LINE, _TIPO_LINE_PLAIN):
        m = pattern.search(content)
        if not m:
            continue
        value = m.group("value").strip()
        if value in {"freeform", "trello", "plane"}:
            return value
    return None


# ── MCP registration ─────────────────────────────────────────────────


def register_discovery_tools(mcp: FastMCP, engine_path: Path) -> None:
    """Expose backend auto-discovery as an MCP tool."""

    @mcp.tool
    def detect_project_backend(project_path: str = ".") -> dict[str, Any]:
        """Auto-detect the spec backend (freeform/trello/plane) for a project.

        Returns the backend type and the source it was inferred from. Skills
        call this in Paso 0 before deciding whether to ask the user about
        backend choice (they shouldn't have to, in v5.29.0 onwards).
        """
        return detect_backend(project_path)
