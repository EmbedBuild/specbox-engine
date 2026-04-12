"""Usability — readability, learnability, accessibility (heuristic v1).

Signals:
- Presence of README, CONTRIBUTING, CLAUDE.md, docs/
- Stitch designs present (UX intentional)
- For UI stacks: grep for alt text / aria / semantics
"""

from __future__ import annotations

from ..schema import (
    CharacteristicResult,
    Finding,
    Severity,
    SquareCharacteristic,
)
from ..scoring import clamp, score_from_findings, traffic_light
from .base import AnalyzerContext, BaseAnalyzer


class UsabilityAnalyzer(BaseAnalyzer):
    characteristic = SquareCharacteristic.USABILITY

    def analyze(self, ctx: AnalyzerContext) -> CharacteristicResult:
        findings: list[Finding] = []

        has_readme = any((ctx.project_path / n).exists() for n in ["README.md", "README.rst", "README.txt"])
        has_claude = (ctx.project_path / "CLAUDE.md").exists()
        has_docs = (ctx.project_path / "docs").is_dir() or (ctx.project_path / "doc").is_dir()
        has_designs = (ctx.project_path / "doc" / "design").is_dir()

        if not has_readme:
            findings.append(Finding(
                severity=Severity.MEDIUM,
                description="README missing — new contributors have no entry point.",
                remediation="Add a README with purpose, install, run, and test instructions.",
            ))
        if not has_claude:
            findings.append(Finding(
                severity=Severity.LOW,
                description="CLAUDE.md missing — project not onboarded into SpecBox flows.",
                remediation="Run onboard_project to create CLAUDE.md and settings.",
            ))

        score_base = 70
        if has_readme: score_base += 10
        if has_claude: score_base += 5
        if has_docs: score_base += 10
        if has_designs: score_base += 5
        score_base = clamp(score_base)
        score = score_from_findings(findings, base=score_base)

        raw = {
            "has_readme": has_readme,
            "has_claude_md": has_claude,
            "has_docs_dir": has_docs,
            "has_stitch_designs": has_designs,
        }
        return CharacteristicResult(
            characteristic=self.characteristic,
            score=score,
            traffic_light=traffic_light(score),
            justification=(
                f"README={has_readme}, CLAUDE.md={has_claude}, docs={has_docs}, "
                f"designs={has_designs}. Documentation presence proxies learnability."
            ),
            raw_metrics=raw,
            findings=findings,
        )
