"""Spec-Code Sync tools — US-01 of v5.0 Self-Evolution.

MCP tools for querying Implementation Status from PRDs.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from fastmcp import FastMCP

from ..prd_parser import parse_implementation_status, UCImplementationStatus
from ..prd_writer import find_prd_path


def register_sync_tools(mcp_instance: FastMCP, engine_path: Path) -> None:
    """Register Spec-Code Sync MCP tools."""

    @mcp_instance.tool(
        description=(
            "Get Implementation Status for a US or UC from a project's PRD. "
            "Returns structured deltas between plan and actual implementation. "
            "Pass a US-id (e.g. 'US-01') to get status of all its UCs, "
            "or a UC-id (e.g. 'UC-001') for a specific UC."
        )
    )
    async def get_implementation_status(
        project_path: str,
        item_id: str,
        feature: str = "",
    ) -> dict:
        """Query Implementation Status from a project's PRD.

        Args:
            project_path: Absolute path to the project root directory.
            item_id: US-id (e.g. "US-01") or UC-id (e.g. "UC-001").
            feature: Optional feature name to help locate the PRD file.

        Returns:
            JSON dict with implementation status data.
        """
        # Derive us_id for PRD lookup
        us_id = item_id if item_id.upper().startswith("US-") else None

        # Find the PRD file
        prd_path = find_prd_path(
            project_path,
            feature=feature or None,
            us_id=us_id,
        )

        if prd_path is None:
            return {
                "error": (
                    f"No se encontró PRD para {item_id} en {project_path}. "
                    "Verifica que el PRD existe en doc/prds/ y contiene "
                    "Implementation Status para este item."
                ),
                "item_id": item_id,
                "project_path": project_path,
            }

        try:
            prd_content = prd_path.read_text(encoding="utf-8")
        except OSError as exc:
            return {"error": f"No se pudo leer el PRD: {exc}", "item_id": item_id}

        statuses = parse_implementation_status(prd_content, item_id)

        # Format response based on target type
        if item_id.upper().startswith("US-"):
            return _format_us_response(item_id, statuses, str(prd_path))
        else:
            if statuses:
                return _format_uc_response(statuses[0], str(prd_path))
            return _format_uc_response(
                UCImplementationStatus(uc_id=item_id, overall_status="not_implemented"),
                str(prd_path),
            )

    @mcp_instance.tool(
        description=(
            "Generate and write Implementation Status to a project's PRD. "
            "Called after completing a UC implementation to record what was built. "
            "Appends structured delta information to the PRD (append-only, never modifies existing content)."
        )
    )
    async def write_implementation_status(
        project_path: str,
        uc_id: str,
        branch: str,
        phase_deltas: list[str],
        feature: str = "",
        us_id: str = "",
    ) -> dict:
        """Write Implementation Status section to a project's PRD.

        Args:
            project_path: Absolute path to the project root directory.
            uc_id: Use Case identifier (e.g. "UC-001").
            branch: Git branch name (e.g. "feature/spec-code-sync").
            phase_deltas: List of Markdown delta blocks (from delta_generator).
            feature: Optional feature name to help locate the PRD file.
            us_id: Optional US-id to help locate the PRD file.

        Returns:
            Dict with success status and PRD path.
        """
        from ..prd_writer import append_implementation_status

        prd_path = find_prd_path(
            project_path,
            feature=feature or None,
            us_id=us_id or None,
        )

        if prd_path is None:
            return {
                "success": False,
                "error": f"No se encontró PRD en {project_path}/doc/prds/",
                "uc_id": uc_id,
            }

        success = append_implementation_status(prd_path, uc_id, branch, phase_deltas)

        return {
            "success": success,
            "prd_path": str(prd_path),
            "uc_id": uc_id,
            "branch": branch,
            "phases_written": len(phase_deltas),
        }


# ---------------------------------------------------------------------------
# Response formatters
# ---------------------------------------------------------------------------


def _format_uc_response(status: UCImplementationStatus, prd_path: str) -> dict:
    """Format a single UC status as JSON response (AC-11, AC-12, AC-14)."""
    return {
        "uc_id": status.uc_id,
        "timestamp": status.timestamp,
        "branch": status.branch,
        "phases": [asdict(p) for p in status.phases],
        "overall_status": status.overall_status,
        "delta_count": status.delta_count,
        "prd_path": prd_path,
    }


def _format_us_response(
    us_id: str,
    statuses: list[UCImplementationStatus],
    prd_path: str,
) -> dict:
    """Format US-level response with all UC statuses (AC-13)."""
    total_deltas = sum(s.delta_count for s in statuses)
    return {
        "us_id": us_id,
        "ucs": [_format_uc_response(s, prd_path) for s in statuses],
        "total_delta_count": total_deltas,
        "prd_path": prd_path,
    }
