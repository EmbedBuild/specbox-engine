"""Compatibility — co-existence and interoperability with target environments.

v1 heuristics:
- Declared engines / Python / Dart / Node versions
- Presence of lockfiles (indicates reproducible builds)
- Platform targets (e.g. Flutter platforms, browser targets)
"""

from __future__ import annotations

import json

from ..schema import (
    CharacteristicResult,
    Finding,
    Severity,
    SquareCharacteristic,
)
from ..scoring import score_from_findings, traffic_light
from .base import AnalyzerContext, BaseAnalyzer


class CompatibilityAnalyzer(BaseAnalyzer):
    characteristic = SquareCharacteristic.COMPATIBILITY

    def analyze(self, ctx: AnalyzerContext) -> CharacteristicResult:
        findings: list[Finding] = []
        raw: dict = {}

        pyproject = ctx.project_path / "pyproject.toml"
        package_json = ctx.project_path / "package.json"
        pubspec = ctx.project_path / "pubspec.yaml"

        has_lockfile = any(
            (ctx.project_path / name).exists()
            for name in ["poetry.lock", "uv.lock", "requirements.txt", "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "pubspec.lock", "go.sum"]
        )
        raw["has_lockfile"] = has_lockfile
        if not has_lockfile:
            findings.append(Finding(
                severity=Severity.MEDIUM,
                description="No dependency lockfile found — builds are not reproducible.",
                remediation="Commit a lockfile appropriate to the stack (poetry.lock, package-lock.json, pubspec.lock, …).",
            ))

        declared_versions: dict[str, str] = {}
        if pyproject.exists():
            declared_versions["python_pyproject"] = "present"
        if package_json.exists():
            try:
                data = json.loads(package_json.read_text(encoding="utf-8"))
                if "engines" in data:
                    declared_versions["engines"] = json.dumps(data["engines"])[:200]
                else:
                    findings.append(Finding(
                        severity=Severity.LOW,
                        description="package.json has no `engines` field — Node version not pinned.",
                        remediation='Add `"engines": {"node": ">=20"}` (or appropriate) to package.json.',
                    ))
            except (OSError, json.JSONDecodeError):
                pass
        if pubspec.exists():
            declared_versions["flutter_pubspec"] = "present"

        raw["declared_versions"] = declared_versions
        raw["infra_services"] = ctx.infra

        base = 85.0 if has_lockfile else 75.0
        score = score_from_findings(findings, base=base)

        return CharacteristicResult(
            characteristic=self.characteristic,
            score=score,
            traffic_light=traffic_light(score),
            justification=(
                f"Lockfile present: {has_lockfile}. Declared version manifests: "
                f"{sorted(declared_versions.keys()) or 'none'}."
            ),
            raw_metrics=raw,
            findings=findings,
        )
