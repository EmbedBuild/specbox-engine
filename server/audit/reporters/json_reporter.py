"""Emit QualityReport as versioned JSON (audit_schema_version: 1.0)."""

from __future__ import annotations

import json
from pathlib import Path

from ..schema import AUDIT_SCHEMA_VERSION, QualityReport


def write_json_report(report: QualityReport, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    data = report.to_dict()
    assert data["audit_schema_version"] == AUDIT_SCHEMA_VERSION
    out_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False),
        encoding="utf-8",
    )
    return out_path
