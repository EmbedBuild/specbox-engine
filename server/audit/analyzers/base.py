"""Analyzer base class + execution context passed to every analyzer.

Each analyzer is responsible for ONE SQuaRE characteristic. It inspects the
project, produces Findings, a raw_metrics dict, and a score 0-100.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..schema import CharacteristicResult, SquareCharacteristic, ToolUsage


@dataclass
class AnalyzerContext:
    project_path: Path
    project_name: str
    stack: str  # e.g. "python", "flutter", "react", "unknown"
    infra: list[str] = field(default_factory=list)
    specbox_signals: dict[str, Any] = field(default_factory=dict)
    engine_path: Path | None = None
    scope: str = "full"

    def is_stack(self, *names: str) -> bool:
        return self.stack.lower() in {n.lower() for n in names}


class BaseAnalyzer(ABC):
    """All analyzers subclass this and implement `analyze`."""

    characteristic: SquareCharacteristic

    def __init__(self) -> None:
        self.tools_used: list[ToolUsage] = []

    @abstractmethod
    def analyze(self, ctx: AnalyzerContext) -> CharacteristicResult:
        """Run the analysis and return a CharacteristicResult."""
        raise NotImplementedError

    def record_tool(self, usage: ToolUsage) -> None:
        self.tools_used.append(usage)
