"""Security — SAST + dependency audit + secret scan + IaC.

External tools (all optional; missing → reported, never abort):
- semgrep (SAST, OWASP Top 10 rules)
- pip-audit / npm audit / …    (deps per stack)
- gitleaks                     (secrets)
- checkov                      (IaC — only if terraform/k8s/cloudformation found)
"""

from __future__ import annotations

import json
from pathlib import Path

from ..schema import (
    CharacteristicResult,
    Finding,
    Severity,
    SquareCharacteristic,
    ToolUsage,
)
from ..scoring import score_from_findings, traffic_light
from ..tool_runner import detect_version, run_tool
from .base import AnalyzerContext, BaseAnalyzer


SEMGREP_SEVERITY_MAP = {
    "ERROR": Severity.HIGH,
    "WARNING": Severity.MEDIUM,
    "INFO": Severity.LOW,
}


class SecurityAnalyzer(BaseAnalyzer):
    characteristic = SquareCharacteristic.SECURITY

    def analyze(self, ctx: AnalyzerContext) -> CharacteristicResult:
        findings: list[Finding] = []
        raw: dict = {}

        self._run_semgrep(ctx, findings, raw)
        self._run_gitleaks(ctx, findings, raw)
        self._run_dep_audit(ctx, findings, raw)
        self._run_checkov_if_iac(ctx, findings, raw)

        score = score_from_findings(findings, base=100.0)

        return CharacteristicResult(
            characteristic=self.characteristic,
            score=score,
            traffic_light=traffic_light(score),
            justification=(
                f"SAST + dependency + secret + IaC scan. "
                f"{len(findings)} issue(s) detected across the stack '{ctx.stack}'. "
                "Missing tools are reported in tools_used but do not fail the audit."
            ),
            raw_metrics=raw,
            findings=findings,
        )

    # ---- semgrep ----

    def _run_semgrep(self, ctx: AnalyzerContext, findings: list[Finding], raw: dict) -> None:
        res = run_tool(
            ["semgrep", "--config", "p/owasp-top-ten", "--json", "--quiet", "--error", str(ctx.project_path)],
            cwd=ctx.project_path, timeout=240.0,
        )
        if not res.available:
            self.record_tool(ToolUsage(name="semgrep", status="missing",
                                       message="install via `pip install semgrep`"))
            raw["semgrep"] = "missing"
            return
        res.version = detect_version("semgrep")
        self.record_tool(res.to_usage(stack="multi"))
        raw["semgrep"] = {"returncode": res.returncode}
        if res.timed_out:
            return
        try:
            data = json.loads(res.stdout or "{}")
        except json.JSONDecodeError:
            return
        results = data.get("results", [])
        raw["semgrep"]["findings"] = len(results)
        for r in results[:50]:
            sev = r.get("extra", {}).get("severity", "INFO").upper()
            cwe_list = r.get("extra", {}).get("metadata", {}).get("cwe") or []
            cwe = cwe_list[0] if isinstance(cwe_list, list) and cwe_list else None
            findings.append(Finding(
                severity=SEMGREP_SEVERITY_MAP.get(sev, Severity.LOW),
                description=r.get("extra", {}).get("message", r.get("check_id", "semgrep finding")),
                remediation=r.get("extra", {}).get("metadata", {}).get("fix", "Review and patch per OWASP guidance."),
                cwe=str(cwe) if cwe else None,
                file=r.get("path"),
                line=r.get("start", {}).get("line"),
                source_tool="semgrep",
            ))

    # ---- gitleaks ----

    def _run_gitleaks(self, ctx: AnalyzerContext, findings: list[Finding], raw: dict) -> None:
        res = run_tool(
            ["gitleaks", "detect", "--no-banner", "--report-format", "json", "--report-path", "-", "--source", str(ctx.project_path)],
            cwd=ctx.project_path, timeout=120.0,
        )
        if not res.available:
            self.record_tool(ToolUsage(name="gitleaks", status="missing",
                                       message="install via https://github.com/gitleaks/gitleaks"))
            raw["gitleaks"] = "missing"
            return
        res.version = detect_version("gitleaks", "version")
        self.record_tool(res.to_usage(stack="multi"))
        raw["gitleaks"] = {"returncode": res.returncode}
        if res.timed_out or not res.stdout:
            return
        try:
            leaks = json.loads(res.stdout)
        except json.JSONDecodeError:
            return
        if isinstance(leaks, list):
            raw["gitleaks"]["leaks"] = len(leaks)
            for leak in leaks[:20]:
                findings.append(Finding(
                    severity=Severity.CRITICAL,
                    description=f"Secret detected: {leak.get('Description', 'unknown')}",
                    remediation="Rotate the secret immediately and purge from git history.",
                    file=leak.get("File"),
                    line=leak.get("StartLine"),
                    source_tool="gitleaks",
                ))

    # ---- dep audit per stack ----

    def _run_dep_audit(self, ctx: AnalyzerContext, findings: list[Finding], raw: dict) -> None:
        if ctx.is_stack("python") or (ctx.project_path / "pyproject.toml").exists() or (ctx.project_path / "requirements.txt").exists():
            self._run_pip_audit(ctx, findings, raw)
        if ctx.is_stack("react", "node", "typescript") or (ctx.project_path / "package.json").exists():
            self._run_npm_audit(ctx, findings, raw)

    def _run_pip_audit(self, ctx: AnalyzerContext, findings: list[Finding], raw: dict) -> None:
        res = run_tool(["pip-audit", "--format", "json"], cwd=ctx.project_path, timeout=120.0)
        if not res.available:
            self.record_tool(ToolUsage(name="pip-audit", status="missing",
                                       message="install via `pip install pip-audit`"))
            raw["pip_audit"] = "missing"
            return
        res.version = detect_version("pip-audit")
        self.record_tool(res.to_usage(stack="python"))
        raw["pip_audit"] = {"returncode": res.returncode}
        try:
            data = json.loads(res.stdout or "[]")
        except json.JSONDecodeError:
            return
        vulns = data if isinstance(data, list) else data.get("dependencies", [])
        vuln_count = 0
        for entry in vulns:
            vs = entry.get("vulns") or entry.get("vulnerabilities") or []
            for v in vs:
                vuln_count += 1
                findings.append(Finding(
                    severity=Severity.HIGH,
                    description=f"Vulnerable dep {entry.get('name')}@{entry.get('version')}: {v.get('id', 'CVE')}",
                    remediation=f"Upgrade to {', '.join(v.get('fix_versions', [])) or 'patched version'}.",
                    cwe=v.get("id"),
                    source_tool="pip-audit",
                ))
        raw["pip_audit"]["vulns"] = vuln_count

    def _run_npm_audit(self, ctx: AnalyzerContext, findings: list[Finding], raw: dict) -> None:
        res = run_tool(["npm", "audit", "--json"], cwd=ctx.project_path, timeout=120.0)
        if not res.available:
            self.record_tool(ToolUsage(name="npm", status="missing", message="install Node/npm"))
            raw["npm_audit"] = "missing"
            return
        res.version = detect_version("npm")
        self.record_tool(ToolUsage(name="npm-audit", status="ok", version=res.version, stack="node"))
        try:
            data = json.loads(res.stdout or "{}")
        except json.JSONDecodeError:
            return
        meta = data.get("metadata", {}).get("vulnerabilities", {})
        raw["npm_audit"] = meta
        for level, severity in [("critical", Severity.CRITICAL), ("high", Severity.HIGH), ("moderate", Severity.MEDIUM), ("low", Severity.LOW)]:
            count = int(meta.get(level, 0))
            if count:
                findings.append(Finding(
                    severity=severity,
                    description=f"{count} {level} vulnerability(ies) in npm dependencies.",
                    remediation="Run `npm audit fix`, then review remaining advisories manually.",
                    source_tool="npm-audit",
                ))

    # ---- checkov (only if IaC present) ----

    def _run_checkov_if_iac(self, ctx: AnalyzerContext, findings: list[Finding], raw: dict) -> None:
        iac_markers = [".tf", "Dockerfile", "docker-compose.yml", "k8s", "cloudformation"]
        found = any(
            any(str(p).endswith(m) or m in p.name for m in iac_markers)
            for p in ctx.project_path.rglob("*")
            if p.is_file() and all(part not in {"node_modules", ".git", ".venv"} for part in p.parts)
        )
        if not found:
            return
        res = run_tool(["checkov", "-d", str(ctx.project_path), "-o", "json", "--quiet"], timeout=180.0)
        if not res.available:
            self.record_tool(ToolUsage(name="checkov", status="missing",
                                       message="install via `pip install checkov`"))
            raw["checkov"] = "missing"
            return
        res.version = detect_version("checkov")
        self.record_tool(res.to_usage(stack="iac"))
        try:
            data = json.loads(res.stdout or "{}")
        except json.JSONDecodeError:
            return
        failed = 0
        if isinstance(data, dict):
            results = data.get("results", {}).get("failed_checks", [])
            failed = len(results)
            for f in results[:20]:
                findings.append(Finding(
                    severity=Severity.MEDIUM,
                    description=f"IaC misconfig: {f.get('check_name', f.get('check_id'))}",
                    remediation=f.get("guideline") or "Review IaC resource per CIS benchmark.",
                    file=f.get("file_path"),
                    line=(f.get("file_line_range") or [None])[0],
                    source_tool="checkov",
                ))
        raw["checkov"] = {"failed_checks": failed}
