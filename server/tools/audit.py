"""MCP tools for Quality Audit ISO/IEC 25010 v1 (on-demand)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from ..audit.orchestrator import run_audit
from ..audit.persistence import audit_dir, build_summary, update_project_meta
from ..audit.reporters import load_brand, write_json_report, write_pdf_report
from ..audit.schema import QualityReport
from ..audit.signals import fetch_specbox_signals
from ..audit.tool_check import check_audit_tools
from .onboarding import _detect_infra, _detect_stack


def _detect_stack_adapter(project_path: Path) -> dict[str, Any]:
    stack_info = _detect_stack(project_path)
    infra = _detect_infra(project_path)
    return {
        "stack": stack_info.get("stack", "unknown"),
        "files_found": stack_info.get("files_found", []),
        "architecture_pattern": stack_info.get("architecture_pattern", "unknown"),
        "infra": infra,
    }


def register_audit_tools(mcp: FastMCP, engine_path: Path, state_path: Path) -> None:

    @mcp.tool
    def check_audit_tools_status(project_path: str = "") -> dict:
        """Check which external audit tools are installed on this machine.

        Args:
            project_path: Optional project root; used to detect stack and
                          skip stack-irrelevant tools (e.g. npm for non-JS).

        Returns installed/missing lists plus ready-to-run install commands.
        The `/audit` skill calls this BEFORE running an audit and offers
        the user to install missing tools via `.quality/scripts/install-audit-tools.sh`.

        Nothing is installed automatically — this tool is read-only.
        """
        stack: str | None = None
        if project_path:
            try:
                info = _detect_stack(Path(project_path))
                stack = info.get("stack") or None
            except Exception:
                stack = None
        return check_audit_tools(stack=stack)

    @mcp.tool
    def run_quality_audit(
        project: str,
        scope: str = "full",
        project_path: str = "",
    ) -> dict:
        """Run an ISO/IEC 25010 (SQuaRE) quality audit on a project.

        Args:
            project: Project name (used for evidence directory naming).
            scope: 'full' (default) or one of the 8 SQuaRE characteristic ids
                   (e.g. 'security', 'maintainability') to run just that block.
            project_path: Absolute path to the project root. Defaults to
                          STATE_PATH/projects/<project> if empty.

        Returns the full QualityReport as a dict. The report is NOT persisted
        by this tool — call attach_audit_evidence with the returned report
        (optionally enriched by AG-10 with justifications/recommendations).

        Analyses 8 ISO/IEC 25010 characteristics: functional_suitability,
        performance_efficiency, compatibility, usability, reliability,
        security, maintainability (60/40 mix — classic + SpecBox), portability.
        External tools (semgrep, gitleaks, pip-audit, npm audit, checkov, lizard,
        jscpd) degrade gracefully when missing — reported in tools_used without
        aborting the audit.
        """
        pp = Path(project_path) if project_path else (state_path / "projects" / project)
        if not pp.exists():
            return {"error": f"project_path does not exist: {pp}"}

        def _stack_fetcher(path: Path) -> dict[str, Any]:
            return _detect_stack_adapter(path)

        def _signal_fetcher(path: Path, name: str) -> dict[str, Any]:
            return fetch_specbox_signals(path, name, state_path=state_path)

        # Lazy tool check — informs the caller but never blocks the audit.
        stack_info = _detect_stack_adapter(pp)
        tool_status = check_audit_tools(stack=stack_info.get("stack"))

        report = run_audit(
            project_path=pp,
            project_name=project,
            detect_stack=_stack_fetcher,
            fetch_specbox_signals=_signal_fetcher,
            engine_path=engine_path,
            scope=scope,
        )
        data = report.to_dict()
        data["audit_tools_status"] = tool_status
        if not tool_status["all_present"]:
            data["meta"].setdefault("warnings", []).append(
                f"{tool_status['missing_count']} audit tool(s) missing — "
                "some findings may be incomplete. Run "
                ".quality/scripts/install-audit-tools.sh to install them."
            )
        return data

    @mcp.tool
    def attach_audit_evidence(
        project: str,
        report: dict,
    ) -> dict:
        """Persist a QualityReport as PDF + JSON under STATE_PATH evidence.

        Args:
            project: Project name — determines target directory.
            report: The QualityReport dict (possibly enriched by AG-10 with
                    justifications and recommendations).

        Returns paths of the persisted files and the updated project summary.
        """
        try:
            parsed = QualityReport.from_dict(report)
        except (KeyError, ValueError, TypeError) as exc:
            return {"error": f"Invalid report payload: {exc}"}

        out_dir = audit_dir(state_path, project)
        json_path = out_dir / f"{parsed.audit_id}.json"
        pdf_path = out_dir / f"{parsed.audit_id}.pdf"

        brand = load_brand(engine_path)
        if brand.warning:
            parsed.meta.setdefault("warnings", []).append(brand.warning)

        write_json_report(parsed, json_path)
        try:
            write_pdf_report(parsed, pdf_path, brand)
            pdf_status = "ok"
            pdf_error: str | None = None
        except Exception as exc:  # noqa: BLE001
            pdf_status = "error"
            pdf_error = str(exc)

        summary = build_summary(parsed, pdf_path, json_path)
        update_project_meta(state_path, project, summary)

        return {
            "project": project,
            "audit_id": parsed.audit_id,
            "json_path": str(json_path),
            "pdf_path": str(pdf_path) if pdf_status == "ok" else None,
            "pdf_status": pdf_status,
            "pdf_error": pdf_error,
            "global_score": parsed.global_score,
            "global_traffic_light": parsed.global_traffic_light.value,
            "summary": summary,
        }

    @mcp.tool
    def get_last_audit(project: str) -> dict:
        """Return the latest audit summary stored in the project's meta.json."""
        meta_file = state_path / "projects" / project / "meta.json"
        if not meta_file.exists():
            return {"error": f"No meta for project '{project}'"}
        try:
            data = json.loads(meta_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return {"error": f"Could not read meta.json: {exc}"}
        return data.get("last_audit") or {"error": "No audits recorded yet"}
