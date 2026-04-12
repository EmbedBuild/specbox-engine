"""Orchestrator — runs all 8 SQuaRE analyzers, collects tools_used, builds
the QualityReport and returns it. Does NOT write files (persistence.py does).
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any, Callable

from .analyzers import ALL_ANALYZERS, AnalyzerContext
from .schema import (
    CharacteristicResult,
    QualityReport,
    Severity,
    SquareCharacteristic,
    ToolUsage,
    TrafficLight,
    new_audit_id,
    now_iso,
)
from .scoring import global_score, ordered_characteristics, traffic_light


def _git_commit(project_path: Path) -> str:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(project_path),
            capture_output=True, text=True, timeout=5, check=False,
        )
        return res.stdout.strip() if res.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


SpecboxSignalFetcher = Callable[[Path, str], dict[str, Any]]
StackDetector = Callable[[Path], dict[str, Any]]


def run_audit(
    project_path: Path,
    project_name: str,
    *,
    detect_stack: StackDetector,
    fetch_specbox_signals: SpecboxSignalFetcher,
    engine_path: Path | None = None,
    scope: str = "full",
) -> QualityReport:
    """Run the full audit pipeline and return a QualityReport.

    The fetchers are injected so this module stays independent of the MCP
    server wiring (easier to test).
    """
    t0 = time.monotonic()
    audit_id = new_audit_id()
    generated_at = now_iso()
    commit = _git_commit(project_path)

    stack_info = detect_stack(project_path) or {}
    stack_name = str(stack_info.get("stack", "unknown"))
    infra = list(stack_info.get("infra", []))

    specbox_signals = fetch_specbox_signals(project_path, project_name) or {}

    ctx = AnalyzerContext(
        project_path=project_path,
        project_name=project_name,
        stack=stack_name,
        infra=infra,
        specbox_signals=specbox_signals,
        engine_path=engine_path,
        scope=scope,
    )

    results_by_id: dict[SquareCharacteristic, CharacteristicResult] = {}
    tools_used: list[ToolUsage] = []
    warnings: list[str] = []

    # Optional single-characteristic scope
    scope_filter: set[str] | None = None
    if scope and scope not in ("full", "all"):
        scope_filter = {scope}

    for analyzer_cls in ALL_ANALYZERS:
        analyzer = analyzer_cls()
        ch = analyzer.characteristic
        if scope_filter and ch.value not in scope_filter:
            results_by_id[ch] = CharacteristicResult(
                characteristic=ch,
                score=0.0,
                traffic_light=TrafficLight.AMBER,
                justification="Skipped by scope filter.",
                skipped=True,
                skipped_reason=f"scope={scope}",
            )
            continue
        try:
            result = analyzer.analyze(ctx)
        except Exception as exc:  # defensive: one analyzer must never break the audit
            warnings.append(f"{ch.value}: analyzer crashed — {exc}")
            result = CharacteristicResult(
                characteristic=ch,
                score=0.0,
                traffic_light=TrafficLight.RED,
                justification=f"Analyzer crashed: {exc}",
                skipped=True,
                skipped_reason=str(exc),
            )
        results_by_id[ch] = result
        tools_used.extend(analyzer.tools_used)

    ordered = ordered_characteristics(results_by_id)
    g_score = global_score(ordered)
    g_tl = traffic_light(g_score)

    duration_ms = int((time.monotonic() - t0) * 1000)

    report = QualityReport(
        audit_id=audit_id,
        project=project_name,
        project_path=str(project_path),
        commit=commit,
        generated_at=generated_at,
        stack={
            "detected": stack_name,
            "infra": infra,
            "analyzers_run": [c.value for c in results_by_id if not results_by_id[c].skipped],
            "analyzers_skipped": [c.value for c in results_by_id if results_by_id[c].skipped],
            "scope": scope,
        },
        global_score=g_score,
        global_traffic_light=g_tl,
        characteristics=ordered,
        tools_used=tools_used,
        meta={
            "duration_ms": duration_ms,
            "warnings": warnings,
            "engine_version": stack_info.get("engine_version", "unknown"),
        },
    )
    return report
