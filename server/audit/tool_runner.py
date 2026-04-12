"""Subprocess wrapper for external audit tools (semgrep, gitleaks, lizard, …).

Design goals:
- Never abort the audit if a tool is missing → return a ToolUsage(status="missing")
- Never hang → hard timeout per invocation
- Normalize stdout/stderr so analyzers can parse without special-casing
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .schema import ToolUsage


@dataclass
class ToolResult:
    tool: str
    available: bool
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    version: str | None = None

    def to_usage(self, stack: str | None = None) -> ToolUsage:
        if not self.available:
            return ToolUsage(
                name=self.tool, status="missing", stack=stack,
                message="binary not found on PATH",
            )
        if self.timed_out:
            return ToolUsage(name=self.tool, status="timeout", stack=stack)
        if self.returncode not in (0, 1):  # many linters exit 1 on findings
            return ToolUsage(
                name=self.tool, status="error", stack=stack, version=self.version,
                message=f"exit {self.returncode}: {self.stderr[:200]}",
            )
        return ToolUsage(name=self.tool, status="ok", version=self.version, stack=stack)


def which(tool: str) -> str | None:
    return shutil.which(tool)


def run_tool(
    argv: list[str],
    *,
    cwd: Path | None = None,
    timeout: float = 120.0,
    env: dict[str, str] | None = None,
) -> ToolResult:
    """Execute `argv` with a timeout. Never raises; returns a ToolResult."""
    tool = argv[0]
    if which(tool) is None:
        return ToolResult(tool=tool, available=False)

    try:
        proc = subprocess.run(
            argv,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            check=False,
        )
        return ToolResult(
            tool=tool,
            available=True,
            returncode=proc.returncode,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
        )
    except subprocess.TimeoutExpired:
        return ToolResult(tool=tool, available=True, timed_out=True, returncode=-1)
    except (OSError, ValueError) as exc:
        return ToolResult(
            tool=tool, available=True, returncode=-1, stderr=str(exc),
        )


def detect_version(tool: str, version_arg: str = "--version", timeout: float = 5.0) -> str | None:
    """Best-effort tool version detection — never raises."""
    if which(tool) is None:
        return None
    try:
        proc = subprocess.run(
            [tool, version_arg], capture_output=True, text=True, timeout=timeout, check=False,
        )
        raw = (proc.stdout or proc.stderr or "").strip().splitlines()
        return raw[0][:120] if raw else None
    except (subprocess.TimeoutExpired, OSError):
        return None
