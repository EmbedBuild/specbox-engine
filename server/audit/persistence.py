"""Persist audit artifacts under STATE_PATH/projects/<p>/evidence/audits/ and
update project meta so Sala de Máquinas can surface the latest audit.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schema import QualityReport


def audit_dir(state_path: Path, project: str) -> Path:
    d = state_path / "projects" / project / "evidence" / "audits"
    d.mkdir(parents=True, exist_ok=True)
    return d


def update_project_meta(state_path: Path, project: str, summary: dict[str, Any]) -> None:
    meta_file = state_path / "projects" / project / "meta.json"
    meta_file.parent.mkdir(parents=True, exist_ok=True)
    data: dict = {}
    if meta_file.exists():
        try:
            data = json.loads(meta_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    data["last_audit"] = summary
    meta_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def build_summary(report: QualityReport, pdf_path: Path, json_path: Path) -> dict[str, Any]:
    return {
        "audit_id": report.audit_id,
        "global_score": round(report.global_score, 2),
        "global_traffic_light": report.global_traffic_light.value,
        "generated_at": report.generated_at,
        "pdf_path": str(pdf_path),
        "json_path": str(json_path),
        "stack": report.stack.get("detected", "unknown"),
    }
