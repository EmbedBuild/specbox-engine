"""Fire-and-forget Engram observation writer.

If engram is not available (not installed, offline, any error), silently swallow so
the tool call succeeds. Engram is auxiliary evidence, not a blocker.
"""

from __future__ import annotations

import logging
import subprocess
from typing import Any

logger = logging.getLogger("specbox_stripe_mcp.engram")


def write_config_observation(
    *,
    project: str,
    title: str,
    content: str,
) -> str | None:
    """Best-effort call to `engram save` CLI. Returns observation id if detectable, else None.

    Never raises. Silent on failure.
    """
    try:
        result = subprocess.run(
            [
                "engram",
                "save",
                "--project",
                project,
                "--type",
                "config",
                title,
                content,
            ],
            capture_output=True,
            text=True,
            timeout=3.0,
            check=False,
        )
        if result.returncode != 0:
            logger.debug("engram save non-zero rc=%s", result.returncode)
            return None
        # Engram prints the observation id on success; tolerate any format.
        out = (result.stdout or "").strip()
        if out.startswith("obs_"):
            return out.split()[0]
        return out or None
    except FileNotFoundError:
        logger.debug("engram CLI not found; skipping observation")
        return None
    except subprocess.TimeoutExpired:
        logger.debug("engram save timed out; skipping observation")
        return None
    except Exception as exc:
        logger.debug("engram save failed silently: %s", exc)
        return None


def format_config_content(
    *,
    tool: str,
    project: str,
    mode: str,
    result_summary: str,
    ids_created: list[str] | None = None,
    ids_reused: list[str] | None = None,
    duration_ms: float | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    """Build the Markdown body of a config observation for a Stripe MCP tool call."""
    lines = [
        f"**Tool**: {tool}",
        f"**Project**: {project}",
        f"**Mode**: {mode}",
        f"**Result**: {result_summary}",
    ]
    if ids_created:
        lines.append(f"**IDs created**: {', '.join(ids_created)}")
    if ids_reused:
        lines.append(f"**IDs reused**: {', '.join(ids_reused)}")
    if duration_ms is not None:
        lines.append(f"**Duration**: {duration_ms:.0f} ms")
    if extra:
        for key, value in extra.items():
            lines.append(f"**{key}**: {value}")
    return "\n".join(lines)
