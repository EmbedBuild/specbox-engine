"""Quality Audit schema — single source of truth for JSON + PDF reports.

Versioned via AUDIT_SCHEMA_VERSION so v2 can diff against v1 snapshots.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any

AUDIT_SCHEMA_VERSION = "1.0"


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class TrafficLight(str, Enum):
    GREEN = "green"
    AMBER = "amber"
    RED = "red"


class SquareCharacteristic(str, Enum):
    FUNCTIONAL_SUITABILITY = "functional_suitability"
    PERFORMANCE_EFFICIENCY = "performance_efficiency"
    COMPATIBILITY = "compatibility"
    USABILITY = "usability"
    RELIABILITY = "reliability"
    SECURITY = "security"
    MAINTAINABILITY = "maintainability"
    PORTABILITY = "portability"


SQUARE_ORDER: list[SquareCharacteristic] = [
    SquareCharacteristic.FUNCTIONAL_SUITABILITY,
    SquareCharacteristic.PERFORMANCE_EFFICIENCY,
    SquareCharacteristic.COMPATIBILITY,
    SquareCharacteristic.USABILITY,
    SquareCharacteristic.RELIABILITY,
    SquareCharacteristic.SECURITY,
    SquareCharacteristic.MAINTAINABILITY,
    SquareCharacteristic.PORTABILITY,
]


@dataclass
class Finding:
    severity: Severity
    description: str
    remediation: str
    cwe: str | None = None
    file: str | None = None
    line: int | None = None
    source_tool: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["severity"] = self.severity.value
        return {k: v for k, v in d.items() if v is not None}


@dataclass
class Recommendation:
    priority: Severity
    action: str
    rationale: str
    finding_ref: str | None = None
    files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["priority"] = self.priority.value
        return d


@dataclass
class ToolUsage:
    name: str
    status: str  # ok | missing | timeout | error
    version: str | None = None
    stack: str | None = None
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class CharacteristicResult:
    characteristic: SquareCharacteristic
    score: float  # 0-100
    traffic_light: TrafficLight
    justification: str = ""
    raw_metrics: dict[str, Any] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    recommendations: list[Recommendation] = field(default_factory=list)
    breakdown: dict[str, Any] | None = None  # maintainability only
    skipped: bool = False
    skipped_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = {
            "id": self.characteristic.value,
            "score": round(self.score, 2),
            "traffic_light": self.traffic_light.value,
            "justification": self.justification,
            "raw_metrics": self.raw_metrics,
            "findings": [f.to_dict() for f in self.findings],
            "recommendations": [r.to_dict() for r in self.recommendations],
            "skipped": self.skipped,
        }
        if self.breakdown is not None:
            d["breakdown"] = self.breakdown
        if self.skipped_reason:
            d["skipped_reason"] = self.skipped_reason
        return d


@dataclass
class QualityReport:
    audit_id: str
    project: str
    project_path: str
    commit: str
    generated_at: str
    stack: dict[str, Any]
    global_score: float
    global_traffic_light: TrafficLight
    characteristics: list[CharacteristicResult]
    tools_used: list[ToolUsage] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)
    audit_schema_version: str = AUDIT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "audit_schema_version": self.audit_schema_version,
            "audit_id": self.audit_id,
            "project": self.project,
            "project_path": self.project_path,
            "commit": self.commit,
            "generated_at": self.generated_at,
            "stack": self.stack,
            "global_score": round(self.global_score, 2),
            "global_traffic_light": self.global_traffic_light.value,
            "characteristics": [c.to_dict() for c in self.characteristics],
            "tools_used": [t.to_dict() for t in self.tools_used],
            "meta": self.meta,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QualityReport":
        """Parse a persisted JSON report back into a QualityReport."""
        chars: list[CharacteristicResult] = []
        for c in data.get("characteristics", []):
            findings = [
                Finding(
                    severity=Severity(f["severity"]),
                    description=f["description"],
                    remediation=f["remediation"],
                    cwe=f.get("cwe"),
                    file=f.get("file"),
                    line=f.get("line"),
                    source_tool=f.get("source_tool"),
                )
                for f in c.get("findings", [])
            ]
            recs = [
                Recommendation(
                    priority=Severity(r["priority"]),
                    action=r["action"],
                    rationale=r["rationale"],
                    finding_ref=r.get("finding_ref"),
                    files=r.get("files", []),
                )
                for r in c.get("recommendations", [])
            ]
            chars.append(
                CharacteristicResult(
                    characteristic=SquareCharacteristic(c["id"]),
                    score=float(c["score"]),
                    traffic_light=TrafficLight(c["traffic_light"]),
                    justification=c.get("justification", ""),
                    raw_metrics=c.get("raw_metrics", {}),
                    findings=findings,
                    recommendations=recs,
                    breakdown=c.get("breakdown"),
                    skipped=c.get("skipped", False),
                    skipped_reason=c.get("skipped_reason"),
                )
            )
        tools = [
            ToolUsage(
                name=t["name"],
                status=t["status"],
                version=t.get("version"),
                stack=t.get("stack"),
                message=t.get("message"),
            )
            for t in data.get("tools_used", [])
        ]
        return cls(
            audit_id=data["audit_id"],
            project=data["project"],
            project_path=data["project_path"],
            commit=data["commit"],
            generated_at=data["generated_at"],
            stack=data.get("stack", {}),
            global_score=float(data["global_score"]),
            global_traffic_light=TrafficLight(data["global_traffic_light"]),
            characteristics=chars,
            tools_used=tools,
            meta=data.get("meta", {}),
            audit_schema_version=data.get("audit_schema_version", AUDIT_SCHEMA_VERSION),
        )


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_audit_id() -> str:
    return "audit_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
