"""Portability — adaptability, installability, replaceability.

Signals:
- Containerization (Dockerfile, docker-compose)
- Hardcoded absolute paths in source (grep heuristic)
- Platform targets (Flutter platforms, browser targets)
- Environment config (.env.example, config files)
"""

from __future__ import annotations

import re

from ..schema import (
    CharacteristicResult,
    Finding,
    Severity,
    SquareCharacteristic,
)
from ..scoring import clamp, score_from_findings, traffic_light
from .base import AnalyzerContext, BaseAnalyzer


HARDCODED_PATH_RE = re.compile(r"(/Users/|/home/|C:\\\\)[A-Za-z0-9_.\-/\\]+")
SCAN_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx", ".dart", ".go"}


class PortabilityAnalyzer(BaseAnalyzer):
    characteristic = SquareCharacteristic.PORTABILITY

    def analyze(self, ctx: AnalyzerContext) -> CharacteristicResult:
        has_dockerfile = (ctx.project_path / "Dockerfile").exists()
        has_compose = (ctx.project_path / "docker-compose.yml").exists() or (ctx.project_path / "compose.yaml").exists()
        has_env_example = (ctx.project_path / ".env.example").exists() or (ctx.project_path / ".env.sample").exists()

        hardcoded_hits: list[tuple[str, int]] = []
        scanned = 0
        for p in ctx.project_path.rglob("*"):
            if scanned >= 500:
                break
            if not p.is_file() or p.suffix.lower() not in SCAN_EXTS:
                continue
            if any(part in {"node_modules", ".git", "build", "dist", ".venv", ".dart_tool"} for part in p.parts):
                continue
            scanned += 1
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for m in HARDCODED_PATH_RE.finditer(text):
                line = text[:m.start()].count("\n") + 1
                try:
                    rel = str(p.relative_to(ctx.project_path))
                except ValueError:
                    rel = str(p)
                hardcoded_hits.append((rel, line))
                if len(hardcoded_hits) >= 20:
                    break
            if len(hardcoded_hits) >= 20:
                break

        findings: list[Finding] = []
        for rel, line in hardcoded_hits[:10]:
            findings.append(Finding(
                severity=Severity.MEDIUM,
                description=f"Hardcoded filesystem path in {rel}:{line}",
                remediation="Move to env var or config file; avoid absolute paths in source.",
                file=rel,
                line=line,
            ))
        if not has_dockerfile and not has_compose:
            findings.append(Finding(
                severity=Severity.LOW,
                description="No Dockerfile or docker-compose found — project is not containerized.",
                remediation="Add a Dockerfile to enable reproducible deployment.",
            ))
        if not has_env_example:
            findings.append(Finding(
                severity=Severity.LOW,
                description="No .env.example — contributors can't discover required env vars.",
                remediation="Commit a .env.example with all required keys (empty values).",
            ))

        base = 85.0
        if has_dockerfile: base += 5
        if has_compose: base += 3
        if has_env_example: base += 2
        base = clamp(base)
        score = score_from_findings(findings, base=base)

        raw = {
            "has_dockerfile": has_dockerfile,
            "has_compose": has_compose,
            "has_env_example": has_env_example,
            "hardcoded_paths_found": len(hardcoded_hits),
            "files_scanned": scanned,
        }
        return CharacteristicResult(
            characteristic=self.characteristic,
            score=score,
            traffic_light=traffic_light(score),
            justification=(
                f"Containerization={has_dockerfile or has_compose}, "
                f"env template={has_env_example}, hardcoded paths={len(hardcoded_hits)}."
            ),
            raw_metrics=raw,
            findings=findings,
        )
