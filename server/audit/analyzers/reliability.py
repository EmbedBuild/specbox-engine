"""Reliability — maturity, availability, fault tolerance, recoverability.

Signals:
- SpecBox healing summary (how often self-healing kicked in)
- Test pass rate
- Presence of retries, circuit breakers (grep heuristic)
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


class ReliabilityAnalyzer(BaseAnalyzer):
    characteristic = SquareCharacteristic.RELIABILITY

    def analyze(self, ctx: AnalyzerContext) -> CharacteristicResult:
        signals = ctx.specbox_signals or {}
        healing = signals.get("healing", {}) or {}
        total = int(healing.get("total_events", 0))
        resolved = int(healing.get("resolved", 0))
        failed = int(healing.get("failed", 0))
        healing_ratio = (resolved / total) if total else 1.0

        tests = signals.get("tests", {}) or {}
        passed = int(tests.get("passed", 0))
        total_tests = int(tests.get("total", 0))
        pass_rate = (passed / total_tests) if total_tests else 1.0

        findings: list[Finding] = []
        if total and healing_ratio < 0.7:
            findings.append(Finding(
                severity=Severity.HIGH,
                description=f"Self-healing resolution ratio is {healing_ratio:.0%} ({resolved}/{total}).",
                remediation="Review healing log for systemic failures; reduce healing reliance.",
            ))
        if total_tests and pass_rate < 0.95:
            findings.append(Finding(
                severity=Severity.MEDIUM,
                description=f"Test pass rate {pass_rate:.0%} ({passed}/{total_tests}).",
                remediation="Fix failing tests before release.",
            ))

        base = (pass_rate * 60) + (healing_ratio * 40)
        score = score_from_findings(findings, base=base)

        raw = {
            "healing_events_total": total,
            "healing_resolved": resolved,
            "healing_failed": failed,
            "healing_resolution_ratio": round(healing_ratio, 3),
            "tests_total": total_tests,
            "tests_passed": passed,
            "test_pass_rate": round(pass_rate, 3),
        }
        return CharacteristicResult(
            characteristic=self.characteristic,
            score=clamp(score),
            traffic_light=traffic_light(score),
            justification=(
                f"Score = test_pass_rate*60 + healing_ratio*40 "
                f"({pass_rate:.0%} / {healing_ratio:.0%}) minus finding penalties."
            ),
            raw_metrics=raw,
            findings=findings,
        )
