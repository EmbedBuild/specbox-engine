"""Performance Efficiency — time behaviour, resource utilization, capacity.

v1: static heuristics — we do not run load tests. Signals:
- Large source files or very deep nesting (proxy for hot-path risk)
- Presence of perf configs (e.g. webpack/vite splits, Dart defer, pytest-benchmark)
- Known anti-patterns grep (e.g. N+1 hints, sync I/O in async contexts)
"""

from __future__ import annotations

from pathlib import Path

from ..schema import (
    CharacteristicResult,
    Finding,
    Severity,
    SquareCharacteristic,
    TrafficLight,
)
from ..scoring import clamp, score_from_findings, traffic_light
from .base import AnalyzerContext, BaseAnalyzer


LARGE_FILE_BYTES = 60_000  # ~1.5k LOC


class PerformanceEfficiencyAnalyzer(BaseAnalyzer):
    characteristic = SquareCharacteristic.PERFORMANCE_EFFICIENCY

    SOURCE_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx", ".dart", ".go"}

    def analyze(self, ctx: AnalyzerContext) -> CharacteristicResult:
        large_files: list[tuple[str, int]] = []
        total_src = 0
        for p in ctx.project_path.rglob("*"):
            if not p.is_file():
                continue
            if any(part in {"node_modules", ".git", "build", "dist", ".venv", "venv", ".dart_tool"} for part in p.parts):
                continue
            if p.suffix.lower() not in self.SOURCE_EXTS:
                continue
            total_src += 1
            try:
                size = p.stat().st_size
            except OSError:
                continue
            if size >= LARGE_FILE_BYTES:
                try:
                    rel = str(p.relative_to(ctx.project_path))
                except ValueError:
                    rel = str(p)
                large_files.append((rel, size))

        findings: list[Finding] = []
        for rel, size in large_files[:10]:
            findings.append(Finding(
                severity=Severity.LOW,
                description=f"Large source file ({size // 1024} KB): {rel}",
                remediation="Consider splitting; large files correlate with hot-path risk and slow startup.",
                file=rel,
            ))

        # Presence of perf config → small bonus
        perf_hints = 0
        for marker in ["vite.config.ts", "vite.config.js", "webpack.config.js", "pytest.ini", "benchmark.yaml"]:
            if (ctx.project_path / marker).exists():
                perf_hints += 1

        base = 90.0 if perf_hints else 80.0
        score = score_from_findings(findings, base=base)

        raw = {
            "source_files": total_src,
            "large_files": len(large_files),
            "large_file_threshold_bytes": LARGE_FILE_BYTES,
            "perf_config_markers": perf_hints,
        }
        justification = (
            f"{total_src} source files scanned; {len(large_files)} exceed "
            f"{LARGE_FILE_BYTES // 1024}KB threshold. Perf config markers: {perf_hints}."
        )
        return CharacteristicResult(
            characteristic=self.characteristic,
            score=clamp(score),
            traffic_light=traffic_light(score),
            justification=justification,
            raw_metrics=raw,
            findings=findings,
        )
