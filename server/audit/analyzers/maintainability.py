"""Maintainability — 60/40 mix:
- 60% classic: cyclomatic complexity (lizard), duplication (jscpd), file size, test ratio
- 40% SpecBox: AC pending, UCs without evidence, healing ratio, US blocked, PRD divergence

The breakdown MUST appear in the report (RF-3).
"""

from __future__ import annotations

import json

from ..schema import (
    CharacteristicResult,
    Finding,
    Severity,
    SquareCharacteristic,
    ToolUsage,
)
from ..scoring import clamp, maintainability_score, score_from_findings, traffic_light
from ..tool_runner import detect_version, run_tool
from .base import AnalyzerContext, BaseAnalyzer


SOURCE_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx", ".dart", ".go"}
TEST_HINTS = {"test", "tests", "__tests__", "spec"}


class MaintainabilityAnalyzer(BaseAnalyzer):
    characteristic = SquareCharacteristic.MAINTAINABILITY

    def analyze(self, ctx: AnalyzerContext) -> CharacteristicResult:
        classic_score, classic_raw, classic_findings = self._classic(ctx)
        specbox_score, specbox_raw = self._specbox(ctx)

        final, breakdown = maintainability_score(classic_score, specbox_score)
        findings = list(classic_findings)

        # Score already combines both; apply finding penalties lightly.
        final = score_from_findings(findings, base=final)

        raw = {"classic": classic_raw, "specbox": specbox_raw}
        justification = (
            f"Maintainability = 0.60*classic({classic_score:.1f}) + "
            f"0.40*specbox({specbox_score:.1f}) = {final:.1f}. "
            "Breakdown documented to make the score auditable."
        )

        return CharacteristicResult(
            characteristic=self.characteristic,
            score=clamp(final),
            traffic_light=traffic_light(final),
            justification=justification,
            raw_metrics=raw,
            findings=findings,
            breakdown=breakdown,
        )

    # ---- classic 60% ----

    def _classic(self, ctx: AnalyzerContext) -> tuple[float, dict, list[Finding]]:
        raw: dict = {}
        findings: list[Finding] = []

        # File size / LOC heuristic
        src_files = 0
        test_files = 0
        total_bytes = 0
        for p in ctx.project_path.rglob("*"):
            if not p.is_file():
                continue
            if any(part in {"node_modules", ".git", "build", "dist", ".venv", "venv", ".dart_tool", "__pycache__"} for part in p.parts):
                continue
            if p.suffix.lower() not in SOURCE_EXTS:
                continue
            try:
                total_bytes += p.stat().st_size
            except OSError:
                continue
            parts_lc = {part.lower() for part in p.parts}
            if parts_lc & TEST_HINTS:
                test_files += 1
            else:
                src_files += 1

        total_files = src_files + test_files
        test_ratio = (test_files / src_files) if src_files else 0.0
        avg_size_kb = (total_bytes / total_files / 1024) if total_files else 0.0
        raw.update({
            "source_files": src_files,
            "test_files": test_files,
            "test_to_source_ratio": round(test_ratio, 3),
            "avg_file_size_kb": round(avg_size_kb, 2),
            "total_source_bytes": total_bytes,
        })

        if src_files and test_ratio < 0.2:
            findings.append(Finding(
                severity=Severity.MEDIUM,
                description=f"Low test ratio: {test_files}/{src_files} test:source files.",
                remediation="Increase test coverage toward ≥ 0.3 test/source ratio.",
            ))
        if avg_size_kb > 10:
            findings.append(Finding(
                severity=Severity.LOW,
                description=f"Average source file size {avg_size_kb:.1f} KB — consider splitting large modules.",
                remediation="Refactor large files into cohesive sub-modules.",
            ))

        # lizard (cyclomatic complexity) — optional
        lizard_res = run_tool(["lizard", "-C", "15", str(ctx.project_path)], timeout=120.0)
        complex_funcs = 0
        if lizard_res.available:
            self.record_tool(ToolUsage(
                name="lizard", status="ok" if not lizard_res.timed_out else "timeout",
                version=detect_version("lizard"),
            ))
            # lizard default output: lines mentioning "warnings" at bottom
            for line in (lizard_res.stdout or "").splitlines():
                if "warnings" in line.lower() and "nloc" not in line.lower():
                    try:
                        complex_funcs = int(line.strip().split()[0])
                    except (ValueError, IndexError):
                        pass
                    break
            raw["complex_functions_cc_gt_15"] = complex_funcs
            if complex_funcs > 0:
                findings.append(Finding(
                    severity=Severity.MEDIUM if complex_funcs > 10 else Severity.LOW,
                    description=f"{complex_funcs} functions exceed cyclomatic complexity 15 (lizard).",
                    remediation="Refactor complex functions; target CC ≤ 10.",
                ))
        else:
            self.record_tool(ToolUsage(
                name="lizard", status="missing",
                message="install via `pip install lizard`",
            ))
            raw["lizard"] = "missing"

        # jscpd (duplication) — optional
        dup_res = run_tool(
            ["jscpd", "--reporters", "json", "--output", str(ctx.project_path / ".quality" / "jscpd-tmp"), str(ctx.project_path)],
            timeout=120.0,
        )
        dup_percent = 0.0
        if dup_res.available:
            self.record_tool(ToolUsage(
                name="jscpd", status="ok" if not dup_res.timed_out else "timeout",
                version=detect_version("jscpd"),
            ))
            dup_report = ctx.project_path / ".quality" / "jscpd-tmp" / "jscpd-report.json"
            if dup_report.exists():
                try:
                    data = json.loads(dup_report.read_text(encoding="utf-8"))
                    dup_percent = float(data.get("statistics", {}).get("total", {}).get("percentage", 0.0))
                except (OSError, json.JSONDecodeError, TypeError, ValueError):
                    pass
            raw["duplication_percent"] = round(dup_percent, 2)
            if dup_percent > 5:
                findings.append(Finding(
                    severity=Severity.MEDIUM if dup_percent > 10 else Severity.LOW,
                    description=f"Code duplication {dup_percent:.1f}% (jscpd).",
                    remediation="Extract shared utilities to reduce duplication.",
                ))
        else:
            self.record_tool(ToolUsage(name="jscpd", status="missing", message="install via `npm i -g jscpd`"))
            raw["jscpd"] = "missing"

        # Score formula for classic (all normalized to 0-100)
        size_score = 100 - min(50, max(0, (avg_size_kb - 6) * 5))  # penalty above 6KB avg
        test_score = clamp(test_ratio * 250)  # ratio 0.4 → 100
        cc_score = clamp(100 - complex_funcs * 3)
        dup_score = clamp(100 - dup_percent * 4)
        classic = (size_score + test_score + cc_score + dup_score) / 4
        raw["classic_components"] = {
            "size_score": round(size_score, 1),
            "test_score": round(test_score, 1),
            "cc_score": round(cc_score, 1),
            "dup_score": round(dup_score, 1),
        }
        return clamp(classic), raw, findings

    # ---- specbox 40% ----

    def _specbox(self, ctx: AnalyzerContext) -> tuple[float, dict]:
        sig = ctx.specbox_signals or {}
        ac = sig.get("ac_status", {}) or {}
        ac_total = int(ac.get("total", 0))
        ac_done = int(ac.get("completed", 0))
        ac_ratio = (ac_done / ac_total) if ac_total else 1.0

        evidence = sig.get("evidence", {}) or {}
        uc_total = int(evidence.get("uc_total", 0))
        uc_with_evidence = int(evidence.get("uc_with_evidence", 0))
        evidence_ratio = (uc_with_evidence / uc_total) if uc_total else 1.0

        healing = sig.get("healing", {}) or {}
        h_total = int(healing.get("total_events", 0))
        h_resolved = int(healing.get("resolved", 0))
        healing_ratio = (h_resolved / h_total) if h_total else 1.0

        board = sig.get("board", {}) or {}
        us_total = int(board.get("us_total", 0))
        us_blocked = int(board.get("us_blocked", 0))
        block_penalty = (us_blocked / us_total) if us_total else 0.0

        divergence = float(sig.get("prd_divergence_ratio", 0.0))

        score = (
            ac_ratio * 100 * 0.30
            + evidence_ratio * 100 * 0.25
            + healing_ratio * 100 * 0.20
            + (1 - block_penalty) * 100 * 0.15
            + (1 - divergence) * 100 * 0.10
        )
        raw = {
            "ac_completion_ratio": round(ac_ratio, 3),
            "uc_evidence_ratio": round(evidence_ratio, 3),
            "healing_resolution_ratio": round(healing_ratio, 3),
            "us_blocked_ratio": round(block_penalty, 3),
            "prd_code_divergence_ratio": round(divergence, 3),
            "weights": {
                "ac": 0.30, "evidence": 0.25, "healing": 0.20,
                "blocked": 0.15, "divergence": 0.10,
            },
        }
        return clamp(score), raw
