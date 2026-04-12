"""SQuaRE analyzers — one per ISO/IEC 25010 characteristic."""

from .base import AnalyzerContext, BaseAnalyzer
from .functional_suitability import FunctionalSuitabilityAnalyzer
from .performance_efficiency import PerformanceEfficiencyAnalyzer
from .compatibility import CompatibilityAnalyzer
from .usability import UsabilityAnalyzer
from .reliability import ReliabilityAnalyzer
from .security import SecurityAnalyzer
from .maintainability import MaintainabilityAnalyzer
from .portability import PortabilityAnalyzer

ALL_ANALYZERS: list[type[BaseAnalyzer]] = [
    FunctionalSuitabilityAnalyzer,
    PerformanceEfficiencyAnalyzer,
    CompatibilityAnalyzer,
    UsabilityAnalyzer,
    ReliabilityAnalyzer,
    SecurityAnalyzer,
    MaintainabilityAnalyzer,
    PortabilityAnalyzer,
]

__all__ = [
    "AnalyzerContext",
    "BaseAnalyzer",
    "ALL_ANALYZERS",
    "FunctionalSuitabilityAnalyzer",
    "PerformanceEfficiencyAnalyzer",
    "CompatibilityAnalyzer",
    "UsabilityAnalyzer",
    "ReliabilityAnalyzer",
    "SecurityAnalyzer",
    "MaintainabilityAnalyzer",
    "PortabilityAnalyzer",
]
