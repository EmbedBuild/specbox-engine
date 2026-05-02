"""Stitch orchestration: batching + fallback chain (v5.31.0).

Pure orchestration logic over a minimal ``StitchOps`` Protocol so that
unit tests can run without network or MCP transport. The MCP tools in
``server/tools/stitch_v2.py`` adapt the real ``StitchClient`` into this
protocol at the boundary.
"""

from __future__ import annotations

from .batching import (
    BatchPlan,
    BatchResult,
    ScreenSpec,
    build_site_batched,
    partition_screens,
)
from .fallback import (
    FallbackOutcome,
    FallbackResult,
    FallbackStrategy,
    StitchOps,
    generate_screen_with_fallback,
)

__all__ = [
    "BatchPlan",
    "BatchResult",
    "ScreenSpec",
    "build_site_batched",
    "partition_screens",
    "FallbackOutcome",
    "FallbackResult",
    "FallbackStrategy",
    "StitchOps",
    "generate_screen_with_fallback",
]
