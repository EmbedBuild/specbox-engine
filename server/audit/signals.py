"""Gather SpecBox-specific signals for the Maintainability 60/40 mix and
related characteristics.

Reads directly from the project's `.quality/` tree and from the engine state
registry when available. Never raises — returns empty dicts on failure.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def fetch_specbox_signals(project_path: Path, project_name: str, state_path: Path | None = None) -> dict[str, Any]:
    signals: dict[str, Any] = {
        "ac_status": {"total": 0, "completed": 0},
        "evidence": {"uc_total": 0, "uc_with_evidence": 0},
        "healing": {"total_events": 0, "resolved": 0, "failed": 0},
        "board": {"us_total": 0, "us_blocked": 0},
        "acceptance": {"accepted": 0, "rejected": 0},
        "tests": {"total": 0, "passed": 0},
        "prd_divergence_ratio": 0.0,
    }

    quality_dir = project_path / ".quality"
    if not quality_dir.exists():
        return signals

    # Evidence + healing from .quality/evidence/*/
    evidence_dir = quality_dir / "evidence"
    if evidence_dir.is_dir():
        ucs = [d for d in evidence_dir.iterdir() if d.is_dir()]
        signals["evidence"]["uc_total"] = len(ucs)
        with_evidence = 0
        total_healing = 0
        resolved = 0
        failed = 0
        for uc in ucs:
            has_any = any(f.is_file() for f in uc.iterdir())
            if has_any:
                with_evidence += 1
            healing_file = uc / "healing.jsonl"
            if healing_file.exists():
                for line in healing_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    total_healing += 1
                    if event.get("result") == "resolved":
                        resolved += 1
                    elif event.get("result") == "failed":
                        failed += 1
        signals["evidence"]["uc_with_evidence"] = with_evidence
        signals["healing"] = {
            "total_events": total_healing,
            "resolved": resolved,
            "failed": failed,
        }

    # Baseline for tests total/passed
    baseline_dir = quality_dir / "baselines"
    if baseline_dir.is_dir():
        for bf in baseline_dir.glob("*.json"):
            try:
                data = json.loads(bf.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            metrics = data.get("metrics", {})
            signals["tests"]["total"] = int(metrics.get("tests_total", signals["tests"]["total"]))
            signals["tests"]["passed"] = int(metrics.get("tests_passed", signals["tests"]["passed"]))

    # Acceptance + AC + board from state registry (if state_path provided)
    if state_path:
        project_state = state_path / "projects" / project_name
        ac_file = project_state / "ac_status.json"
        if ac_file.exists():
            try:
                data = json.loads(ac_file.read_text(encoding="utf-8"))
                signals["ac_status"] = {
                    "total": int(data.get("total", 0)),
                    "completed": int(data.get("completed", 0)),
                }
            except (OSError, json.JSONDecodeError):
                pass
        board_file = project_state / "board_status.json"
        if board_file.exists():
            try:
                data = json.loads(board_file.read_text(encoding="utf-8"))
                signals["board"] = {
                    "us_total": int(data.get("us_total", 0)),
                    "us_blocked": int(data.get("us_blocked", 0)),
                }
            except (OSError, json.JSONDecodeError):
                pass
        acc_file = project_state / "acceptance_summary.json"
        if acc_file.exists():
            try:
                data = json.loads(acc_file.read_text(encoding="utf-8"))
                signals["acceptance"] = {
                    "accepted": int(data.get("accepted", 0)),
                    "rejected": int(data.get("rejected", 0)),
                }
            except (OSError, json.JSONDecodeError):
                pass

    return signals
