"""Lazy audit-tool availability check.

Called at the start of `run_quality_audit` so the skill `/audit` can offer
the user to install missing tools BEFORE running the audit. Nothing is ever
installed automatically — this module only reports.
"""

from __future__ import annotations

import platform
from dataclasses import dataclass, asdict
from typing import Any

from .tool_runner import detect_version, which


@dataclass
class AuditTool:
    name: str          # binary name on PATH
    purpose: str       # what SQuaRE block uses it
    installer: str     # shell command the user (or the installer script) runs
    optional: bool = True
    stack_hint: str | None = None  # only relevant for stacks with this marker

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _is_macos() -> bool:
    return platform.system() == "Darwin"


def audit_tools_catalog() -> list[AuditTool]:
    """Return the canonical list of external tools used by the audit.

    Installer commands are OS-aware where it matters (gitleaks).
    """
    gitleaks_installer = (
        "brew install gitleaks" if _is_macos()
        else "go install github.com/gitleaks/gitleaks/v8@latest"
    )
    return [
        AuditTool(
            name="semgrep",
            purpose="SAST (Security) — OWASP Top 10 rules",
            installer="uv pip install semgrep",
        ),
        AuditTool(
            name="gitleaks",
            purpose="Secret scanning (Security)",
            installer=gitleaks_installer,
        ),
        AuditTool(
            name="pip-audit",
            purpose="Python dependency vulnerabilities (Security)",
            installer="uv pip install pip-audit",
            stack_hint="python",
        ),
        AuditTool(
            name="npm",
            purpose="Node/JS dependency audit (Security)",
            installer="install Node.js (https://nodejs.org)",
            stack_hint="react",
        ),
        AuditTool(
            name="checkov",
            purpose="IaC security scan (Security, only if Dockerfile/Terraform present)",
            installer="uv pip install checkov",
        ),
        AuditTool(
            name="lizard",
            purpose="Cyclomatic complexity (Maintainability — classic 60%)",
            installer="uv pip install lizard",
        ),
        AuditTool(
            name="jscpd",
            purpose="Code duplication (Maintainability — classic 60%)",
            installer="npm install -g jscpd",
        ),
    ]


def check_audit_tools(stack: str | None = None) -> dict[str, Any]:
    """Check which audit tools are installed.

    Args:
        stack: Current project stack. Used to filter stack-specific tools
               (e.g. npm only relevant for react/node projects).

    Returns a dict with `installed`, `missing`, `all_present`, and a
    ready-to-run `install_command` for the missing tools when available.
    """
    catalog = audit_tools_catalog()
    installed: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []

    for tool in catalog:
        # Skip stack-specific tools that don't apply
        if tool.stack_hint and stack and tool.stack_hint != stack:
            continue
        if which(tool.name):
            installed.append({
                "name": tool.name,
                "purpose": tool.purpose,
                "version": detect_version(tool.name) or "unknown",
            })
        else:
            missing.append(tool.to_dict())

    install_commands = [t["installer"] for t in missing]

    return {
        "all_present": len(missing) == 0,
        "installed": installed,
        "missing": missing,
        "missing_count": len(missing),
        "installed_count": len(installed),
        "install_commands": install_commands,
        "install_script": ".quality/scripts/install-audit-tools.sh",
        "os": platform.system(),
    }
