"""Functional Suitability — completeness, correctness, appropriateness.

Evidence sources:
- SpecBox AC status (completed vs total)
- Acceptance reports (AG-09) if available
- PRD / implementation status divergence
"""

from __future__ import annotations

from ..schema import (
    CharacteristicResult,
    Finding,
    Severity,
    SquareCharacteristic,
    TrafficLight,
)
from ..scoring import clamp, score_from_findings, traffic_light
from .base import AnalyzerContext, BaseAnalyzer


class FunctionalSuitabilityAnalyzer(BaseAnalyzer):
    characteristic = SquareCharacteristic.FUNCTIONAL_SUITABILITY

    def analyze(self, ctx: AnalyzerContext) -> CharacteristicResult:
        signals = ctx.specbox_signals or {}
        ac = signals.get("ac_status", {})
        ac_total = int(ac.get("total", 0))
        ac_done = int(ac.get("completed", 0))
        completion_ratio = (ac_done / ac_total) if ac_total else 1.0

        findings: list[Finding] = []
        if ac_total and completion_ratio < 0.5:
            findings.append(Finding(
                severity=Severity.HIGH,
                description=f"Only {ac_done}/{ac_total} acceptance criteria completed ({completion_ratio:.0%}).",
                remediation="Complete remaining ACs via /implement before shipping.",
            ))
        elif ac_total and completion_ratio < 0.8:
            findings.append(Finding(
                severity=Severity.MEDIUM,
                description=f"{ac_done}/{ac_total} ACs completed — functional gaps remain.",
                remediation="Review pending ACs; confirm they are still required.",
            ))

        acceptance = signals.get("acceptance", {})
        rejected = int(acceptance.get("rejected", 0))
        if rejected:
            findings.append(Finding(
                severity=Severity.HIGH,
                description=f"{rejected} acceptance validations rejected (AG-09b).",
                remediation="Inspect AG-09b evidence and fix root causes.",
            ))

        # Score: start from completion_ratio, then apply finding penalties
        base = completion_ratio * 100
        score = score_from_findings(findings, base=base) if findings else clamp(base)

        raw = {
            "ac_total": ac_total,
            "ac_completed": ac_done,
            "ac_completion_ratio": round(completion_ratio, 3),
            "acceptance_rejected": rejected,
            "acceptance_accepted": int(acceptance.get("accepted", 0)),
        }

        justification = (
            f"Score derived from AC completion ratio ({ac_done}/{ac_total}) "
            f"minus severity-weighted penalties from {len(findings)} finding(s)."
        )

        return CharacteristicResult(
            characteristic=self.characteristic,
            score=score,
            traffic_light=traffic_light(score),
            justification=justification,
            raw_metrics=raw,
            findings=findings,
        )
