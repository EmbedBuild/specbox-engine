"""The /implement context as MCP tools (UC-11202).

``/implement`` used to run Python that imported ``server.implement_context``
from the engine clone to write ``execution_context.json`` (Paso 0.4b) and to
aggregate ``phase_outputs.jsonl`` (Spec-Code Sync). Someone on the hosted MCP
has neither the clone nor that Python, so these two tools compute the same
thing from content the client passes and return content the client writes:
the server never touches a disk. Both go through the same functions the
local Python path uses, so the result is the same byte for byte.
"""

from __future__ import annotations

import re
from dataclasses import asdict
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from ..delta_generator import NO_PLAN_COMPARISON, generate_phase_delta
from ..plan_contract import PlanContract, expected_files, parse_plan_contract
from ..implement_context import (
    PhaseOutput,
    aggregate_phase_entries,
    context_relpath,
    execution_context_content,
    parse_phase_outputs,
    plan_hash_of,
)

# One path segment: the slug becomes .quality/evidence/<slug>/ on the client.
_FEATURE_SLUG = re.compile(r"^(?!\.{1,2}$)[A-Za-z0-9._-]{1,120}$")


_DELTA_STATUS = {"ok": "complete", "error": "failed", "partial": "needs_healing"}


def _phase_delta(entry: PhaseOutput, expected: list[str] | None = None) -> str:
    """The Markdown block of one phase, as ``write_implementation_status`` expects it.

    ``expected`` (UC-12601) are the files the plan's phase of the same number declares; None when
    the plan does not say (an older plan, or no plan passed).
    """

    healing = (
        [{"type": f"{entry.healing_attempts} intento(s)", "resolved": entry.status == "ok"}]
        if entry.healing_attempts
        else []
    )
    return generate_phase_delta(
        phase_number=entry.phase_index,
        phase_name=entry.phase,
        phase_status=_DELTA_STATUS.get(entry.status, entry.status),
        files_created=entry.files_created,
        files_modified=entry.files_modified,
        files_deleted=entry.files_deleted,
        plan_files_expected=expected,
        decisions=[entry.summary] if entry.summary else None,
        healing_events=healing,
        error_summary=entry.error,
    )


def _expected_for(contract: PlanContract, entry: PhaseOutput) -> list[str] | None:
    """Los ficheros de la fase N del plan para la fase con ``phase_index`` N, o None si el plan no
    tiene esa fase o la fase no trae su línea **Ficheros:** (no se compara con lo que no se dijo)."""
    if contract.contract_version == 0 or not 1 <= entry.phase_index <= len(contract.phases):
        return None
    phase = contract.phases[entry.phase_index - 1]
    return list(phase.files) if phase.has_files_line else None


def _plan_comparison(contract: PlanContract, entries: list[PhaseOutput]) -> dict[str, Any]:
    """Toda la ejecución frente a todo lo que el plan esperaba (UC-12601 AC-01)."""
    if contract.contract_version == 0 or not any(p.has_files_line for p in contract.phases):
        return {"available": False, "reason": NO_PLAN_COMPARISON}
    expected = set(expected_files(contract))
    # Solo cuenta lo tocado en fases que el plan describe con ficheros: lo de una fase que no los
    # declara no es «de más», es que no hay con qué compararlo.
    compared = [e for e in entries if _expected_for(contract, e) is not None]
    touched = {f for e in compared for f in (*e.files_created, *e.files_modified, *e.files_deleted)}
    return {
        "available": True,
        "expected": sorted(expected),
        "extra": sorted(touched - expected),
        "missing": sorted(expected - touched),
    }


def _invalid_slug(feature_slug: str) -> dict[str, Any] | None:
    if _FEATURE_SLUG.match(feature_slug or ""):
        return None
    return {
        "error": "INVALID_FEATURE_SLUG",
        "message": "feature_slug must be one path segment of letters, digits, '.', '_' or '-'.",
    }


def register_implement_context_tools(mcp, engine_path: Path) -> None:
    """Register ``build_execution_context`` and ``aggregate_phase_outputs``."""

    def _engine_version() -> str:
        try:
            data = yaml.safe_load((engine_path / "ENGINE_VERSION.yaml").read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            return "unknown"
        return str(data.get("version") or "unknown")

    @mcp.tool
    def build_execution_context(
        feature_slug: str,
        branch: str,
        stack: str,
        project_name: str,
        project_root_absolute: str,
        uc_id: str | None = None,
        us_id: str | None = None,
        base_branch: str = "main",
        backend_type: str = "freeform",
        board_id: str | None = None,
        plan_path: str | None = None,
        plan_hash: str | None = None,
        plan_content: str | None = None,
        autopilot_level: str | None = None,
        engine_version: str | None = None,
        existing_content: str | None = None,
    ) -> dict[str, Any]:
        """Build the content of /implement's execution_context.json (Paso 0.4b).

        Use from /implement instead of running the engine's Python: works with
        the hosted MCP and without an engine clone. Write the returned
        ``content`` to ``path`` (relative to the project root) with the Write
        tool. Nothing is written on the server.

        Args:
            feature_slug: The feature folder under .quality/evidence/.
            branch, stack, project_name, project_root_absolute: The run's values.
            uc_id, us_id, base_branch, backend_type, board_id, autopilot_level:
                Optional run values, as in the local file.
            plan_path: Path of the plan, relative to the project.
            plan_hash: SHA-256 of the plan. Or pass ``plan_content`` and the
                tool computes it; omit both if you have neither (nothing reads it).
            engine_version: Defaults to this server's engine version.
            existing_content: The current execution_context.json, if any. When
                only its timestamps would change, it comes back unchanged
                (``changed: false``) and keeps ``started_at``.

        Returns:
            ``{path, content, changed}``, or ``{error, message}``.
        """
        invalid = _invalid_slug(feature_slug)
        if invalid:
            return invalid
        if plan_hash is None and plan_content is not None:
            plan_hash = plan_hash_of(plan_content)
        try:
            content, changed = execution_context_content(
                feature_slug,
                branch=branch,
                base_branch=base_branch,
                stack=stack,
                backend_type=backend_type,
                board_id=board_id,
                uc_id=uc_id,
                us_id=us_id,
                project_name=project_name,
                project_root_absolute=project_root_absolute,
                plan_path=plan_path,
                plan_hash=plan_hash,
                engine_version=engine_version or _engine_version(),
                autopilot_level=autopilot_level,
                existing_content=existing_content,
            )
        except ValidationError as exc:
            return {"error": "INVALID_EXECUTION_CONTEXT", "message": str(exc)}
        return {"path": context_relpath(feature_slug), "content": content, "changed": changed}

    @mcp.tool
    def aggregate_phase_outputs(
        feature_slug: str, phase_outputs_content: str = "", plan_content: str = "",
    ) -> dict[str, Any]:
        """Aggregate /implement's phase_outputs.jsonl for Spec-Code Sync.

        Use from /implement (Pasos 5.1.1b and 8.5.1a) instead of running the
        engine's Python. Pass the content of
        ``.quality/evidence/<feature_slug>/phase_outputs.jsonl`` (empty if the
        file does not exist yet). Corrupt lines are skipped.

        ``plan_content`` (UC-12601) is the plan's text: with **Ficheros:** lines in its phases
        (contract 1, ``check_plan_contract``), the phase whose ``phase_index`` is N is compared
        with the plan's phase N and each block lists every file that is extra or missing;
        ``plan_comparison`` adds the whole run against everything the plan expected. Without it,
        or with an older plan, each block says the comparison is not available.

        Returns:
            ``{feature_slug, overall_status, delta_count, files_created,
            files_modified, files_deleted, phases, phase_deltas,
            total_duration_s, total_healing_attempts}`` — ``overall_status`` is
            ``ok``, ``partial``, ``error`` or ``empty``; ``phase_deltas`` holds
            one Markdown block per phase, ready for ``write_implementation_status``.
        """
        invalid = _invalid_slug(feature_slug)
        if invalid:
            return invalid
        entries = parse_phase_outputs(phase_outputs_content)
        result = asdict(aggregate_phase_entries(feature_slug, entries))
        contract = parse_plan_contract(plan_content or "")
        result["phase_deltas"] = [_phase_delta(entry, _expected_for(contract, entry)) for entry in entries]
        result["plan_comparison"] = _plan_comparison(contract, entries)
        return result
