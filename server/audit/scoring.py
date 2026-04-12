"""Scoring utilities — normalize metrics to 0-100, pick traffic light,
compute maintainability 60/40 mix, aggregate global score.
"""

from __future__ import annotations

from typing import Iterable

from .schema import (
    CharacteristicResult,
    Finding,
    Severity,
    SquareCharacteristic,
    TrafficLight,
)


# Traffic light thresholds (score out of 100)
GREEN_MIN = 80.0
AMBER_MIN = 60.0


def traffic_light(score: float) -> TrafficLight:
    if score >= GREEN_MIN:
        return TrafficLight.GREEN
    if score >= AMBER_MIN:
        return TrafficLight.AMBER
    return TrafficLight.RED


def clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


# Severity → points deducted from a starting score of 100
SEVERITY_PENALTY: dict[Severity, float] = {
    Severity.CRITICAL: 25.0,
    Severity.HIGH: 12.0,
    Severity.MEDIUM: 5.0,
    Severity.LOW: 2.0,
    Severity.INFO: 0.5,
}


def score_from_findings(findings: Iterable[Finding], base: float = 100.0) -> float:
    """Deduct points from `base` per finding severity. Floor at 0."""
    score = base
    for f in findings:
        score -= SEVERITY_PENALTY.get(f.severity, 1.0)
    return clamp(score)


def ratio_to_score(ratio: float, invert: bool = False) -> float:
    """Normalize a 0..1 ratio to 0..100. If `invert`, higher ratio is worse."""
    r = max(0.0, min(1.0, ratio))
    return clamp((1 - r) * 100 if invert else r * 100)


# ------ Maintainability 60/40 mix ------

CLASSIC_WEIGHT = 0.60
SPECBOX_WEIGHT = 0.40


def maintainability_score(classic_score: float, specbox_score: float) -> tuple[float, dict]:
    """Combine classic industry metrics (60%) with SpecBox MCP signals (40%).

    Returns (final_score, breakdown_dict). The breakdown MUST appear in the
    report so readers can see exactly how the score was computed.
    """
    final = (classic_score * CLASSIC_WEIGHT) + (specbox_score * SPECBOX_WEIGHT)
    breakdown = {
        "classic_60": {
            "score": round(classic_score, 2),
            "weight": CLASSIC_WEIGHT,
            "contribution": round(classic_score * CLASSIC_WEIGHT, 2),
        },
        "specbox_40": {
            "score": round(specbox_score, 2),
            "weight": SPECBOX_WEIGHT,
            "contribution": round(specbox_score * SPECBOX_WEIGHT, 2),
        },
        "formula": "0.60 * classic + 0.40 * specbox",
    }
    return clamp(final), breakdown


# ------ Global aggregation ------

def global_score(results: list[CharacteristicResult]) -> float:
    """Simple mean of non-skipped characteristic scores.

    Skipped characteristics do not penalize the project (reported in meta).
    """
    active = [r.score for r in results if not r.skipped]
    if not active:
        return 0.0
    return clamp(sum(active) / len(active))


def ordered_characteristics(
    results_by_id: dict[SquareCharacteristic, CharacteristicResult],
) -> list[CharacteristicResult]:
    """Return characteristics in the canonical SQuaRE order for reports."""
    from .schema import SQUARE_ORDER

    out: list[CharacteristicResult] = []
    for c in SQUARE_ORDER:
        if c in results_by_id:
            out.append(results_by_id[c])
    return out
