"""Standard response envelope shared by all tools.

Format (from PRD §4, D4):
    {
      "success": bool,
      "data": T | None,
      "error": {"code": str, "message": str, "remediation": str | None} | None,
      "warnings": list[str],
      "evidence": {"engram_observation_id": str | None, ...},
    }
"""

from __future__ import annotations

from typing import Any


def ok(
    data: Any,
    *,
    warnings: list[str] | None = None,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {"success": True, "data": data}
    if warnings:
        out["warnings"] = warnings
    if evidence:
        out["evidence"] = evidence
    return out


def err(
    *,
    code: str,
    message: str,
    remediation: str | None = None,
    data: Any = None,
) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if remediation:
        error["remediation"] = remediation
    out: dict[str, Any] = {"success": False, "error": error}
    if data is not None:
        out["data"] = data
    return out
