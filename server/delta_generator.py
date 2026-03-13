"""Implementation Delta Generator — UC-001 of US-01 Spec-Code Sync Layer.

Generates structured Markdown delta blocks after each /implement phase,
capturing what was built, how it diverged from the plan, and any healing events.

Pure Python module — no FastMCP or backend dependencies.
"""

from __future__ import annotations

from datetime import datetime, timezone

MAX_PHASE_TOKENS = 500
MAX_FILES_PER_CATEGORY = 10
MAX_DECISIONS = 3
MAX_ERROR_CHARS = 150


def generate_phase_delta(
    phase_number: int,
    phase_name: str,
    phase_status: str,
    files_created: list[str] | None = None,
    files_modified: list[str] | None = None,
    plan_files_expected: list[str] | None = None,
    decisions: list[str] | None = None,
    healing_events: list[dict] | None = None,
    error_summary: str | None = None,
) -> str:
    """Generate a Markdown delta block for a completed phase.

    Args:
        phase_number: Sequential phase number (1-based).
        phase_name: Human-readable phase name (e.g. "DB Schema", "Feature Logic").
        phase_status: One of "complete", "failed", "needs_healing".
        files_created: List of file paths created in this phase.
        files_modified: List of file paths modified in this phase.
        plan_files_expected: Files the plan expected (for delta detection). None = skip comparison.
        decisions: Key decisions made by the sub-agent during this phase.
        healing_events: List of healing event dicts with keys: type, resolved (bool).
        error_summary: Error description if phase failed.

    Returns:
        Markdown string, kept within ~500 token budget.
    """
    files_created = files_created or []
    files_modified = files_modified or []
    decisions = decisions or []
    healing_events = healing_events or []

    lines: list[str] = []
    lines.append(f"#### Fase {phase_number}: {phase_name}")
    lines.append(f"- **Estado:** {phase_status}")

    # Files created
    lines.append(f"- **Archivos creados:** {_format_file_list(files_created)}")

    # Files modified
    lines.append(f"- **Archivos modificados:** {_format_file_list(files_modified)}")

    # Deltas vs plan
    deltas_text = _compute_deltas(files_created, files_modified, plan_files_expected)
    lines.append(f"- **Deltas vs plan:** {deltas_text}")

    # Decisions
    if decisions:
        truncated = decisions[:MAX_DECISIONS]
        decisions_text = "; ".join(truncated)
        if len(decisions) > MAX_DECISIONS:
            decisions_text += f" ... y {len(decisions) - MAX_DECISIONS} más"
        lines.append(f"- **Decisiones:** {decisions_text}")
    else:
        lines.append("- **Decisiones:** ninguna")

    # Self-healing (AC-04)
    if healing_events:
        for event in healing_events:
            h_type = event.get("type", "unknown")
            resolved = "resuelto" if event.get("resolved", False) else "no resuelto"
            lines.append(f"- **Self-healing:** {h_type} — {resolved}")

    # Error (AC-05)
    if phase_status == "failed":
        error_text = error_summary or "Error no especificado"
        if len(error_text) > MAX_ERROR_CHARS:
            error_text = error_text[:MAX_ERROR_CHARS] + "..."
        lines.append(f"- **Error:** {error_text}")

    result = "\n".join(lines)

    # Token budget enforcement (AC-02): approximate with word count
    return _enforce_token_budget(result)


def compile_uc_status(
    uc_id: str,
    branch: str,
    phase_deltas: list[str],
    timestamp: str | None = None,
) -> str:
    """Compile all phase deltas into an Implementation Status section for a UC.

    Args:
        uc_id: Use Case identifier (e.g. "UC-001").
        branch: Git branch name (e.g. "feature/spec-code-sync").
        phase_deltas: List of Markdown delta blocks from generate_phase_delta().
        timestamp: ISO 8601 timestamp. Auto-generated if None.

    Returns:
        Complete Markdown section with header and all phase deltas.
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    lines: list[str] = []
    lines.append(f"### Implementation Status — {uc_id}")
    lines.append(f"**Timestamp:** {timestamp}")
    lines.append(f"**Branch:** {branch}")
    lines.append("")

    for delta in phase_deltas:
        lines.append(delta)
        lines.append("")

    return "\n".join(lines).rstrip()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _format_file_list(files: list[str]) -> str:
    """Format a list of file paths, truncating if too many."""
    if not files:
        return "ninguno"
    if len(files) <= MAX_FILES_PER_CATEGORY:
        return ", ".join(f"`{f}`" for f in files)
    shown = files[:MAX_FILES_PER_CATEGORY]
    return ", ".join(f"`{f}`" for f in shown) + f" ... y {len(files) - MAX_FILES_PER_CATEGORY} más"


def _compute_deltas(
    files_created: list[str],
    files_modified: list[str],
    plan_files_expected: list[str] | None,
) -> str:
    """Compute delta description between actual files and plan expectation (AC-03)."""
    if plan_files_expected is None:
        return "Comparación no disponible — archivos listados sin referencia al plan"

    actual_set = set(files_created) | set(files_modified)
    expected_set = set(plan_files_expected)

    if actual_set == expected_set:
        return "Sin deltas — implementación conforme al plan"

    parts: list[str] = []
    extra = actual_set - expected_set
    missing = expected_set - actual_set

    if extra:
        extra_list = ", ".join(f"`{f}`" for f in sorted(extra)[:5])
        parts.append(f"Archivos adicionales: {extra_list}")
    if missing:
        missing_list = ", ".join(f"`{f}`" for f in sorted(missing)[:5])
        parts.append(f"Archivos esperados no tocados: {missing_list}")

    return "; ".join(parts) if parts else "Sin deltas — implementación conforme al plan"


def _enforce_token_budget(text: str) -> str:
    """Truncate text to stay within ~500 token budget (word-count proxy)."""
    words = text.split()
    if len(words) <= MAX_PHASE_TOKENS:
        return text
    # Truncate to budget, keeping complete lines where possible
    truncated_words = words[:MAX_PHASE_TOKENS]
    truncated = " ".join(truncated_words)
    # Find last newline to avoid cutting mid-line
    last_nl = truncated.rfind("\n")
    if last_nl > len(truncated) // 2:
        truncated = truncated[:last_nl]
    return truncated + "\n- **[truncado por budget de 500 tokens]**"
