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
    files_deleted: list[str] | None = None,
    comparison_note: str | None = None,
) -> str:
    """Generate a Markdown delta block for a completed phase.

    Args:
        phase_number: Sequential phase number (1-based).
        phase_name: Human-readable phase name (e.g. "DB Schema", "Feature Logic").
        phase_status: One of "complete", "failed", "needs_healing".
        files_created: List of file paths created in this phase.
        files_modified: List of file paths modified in this phase.
        plan_files_expected: Files the plan expected for this phase (UC-12601: from the plan's
            **Ficheros:** line, ``server/plan_contract.py``). None = the plan does not say.
        files_deleted: Files deleted in this phase; they count as touched in the comparison.
        comparison_note: Why there is nothing to compare when ``plan_files_expected`` is None
            (UC-12601); by default the plan does not declare files per phase.
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
    deltas_text = _compute_deltas(files_created, files_modified, plan_files_expected, files_deleted or [])
    if plan_files_expected is None and comparison_note:
        deltas_text = comparison_note
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
    behaviors: dict[str, str] | None = None,
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

    # UC-12211: lo que hace cada criterio entregado, en una frase, además de ficheros y decisiones.
    if behaviors:
        lines.append("#### Comportamiento entregado")
        lines.append("")
        for ac_id in sorted(behaviors):
            text = " ".join(str(behaviors[ac_id]).split())
            if text:
                lines.append(f"- **{ac_id}**: {text}")
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


#: UC-12601: lo que dice el bloque cuando el plan no declara ficheros por fase.
NO_PLAN_COMPARISON = "Comparación no disponible: el plan no declara ficheros por fase"
NO_PLAN_PHASE = "Comparación no disponible: la tarea no dice qué «Fase N» del plan hizo (plan_phase)"
PLAN_PHASE_NOT_FOUND = "Comparación no disponible: el plan no tiene una única «Fase {n}»"
NO_PLAN_GIVEN = "Comparación no disponible: no llegó el plan (plan_content)"
NO_DELTAS = "Sin deltas — implementación conforme al plan"
#: Los que caben en el bloque de una fase; la lista entera va en ``plan_comparison``.
MAX_DELTA_FILES = 50


def normalize_repo_path(path: str) -> str:
    """``./server\\x.py`` → ``server/x.py``: como se comparan lo hecho y lo previsto."""
    clean = (path or "").strip().replace("\\", "/")
    while clean.startswith("./"):
        clean = clean[2:]
    return clean


def compare_files(touched: list[str], expected: list[str]) -> tuple[list[str], list[str]]:
    """``(sobran, faltan)`` (UC-12601). Un previsto que acaba en «/» es una carpeta: la cubre
    cualquier fichero de dentro. Rutas normalizadas, sin repetir, en orden."""
    done = sorted({normalize_repo_path(f) for f in touched if normalize_repo_path(f)})
    plan = sorted({normalize_repo_path(f) for f in expected if normalize_repo_path(f)})

    def covers(entry: str, path: str) -> bool:
        return path == entry or (entry.endswith("/") and path.startswith(entry))

    extra = [p for p in done if not any(covers(e, p) for e in plan)]
    missing = [e for e in plan if not any(covers(e, p) for p in done)]
    return extra, missing


def _listed(files: list[str]) -> str:
    shown = ", ".join(f"`{f}`" for f in files[:MAX_DELTA_FILES])
    return shown + (f" y {len(files) - MAX_DELTA_FILES} más" if len(files) > MAX_DELTA_FILES else "")


def _compute_deltas(
    files_created: list[str],
    files_modified: list[str],
    plan_files_expected: list[str] | None,
    files_deleted: list[str] | None = None,
) -> str:
    """Lo hecho frente a lo que el plan esperaba en la fase (UC-12601): los que sobran y los que
    faltan (hasta 50 de cada, con el total; la lista entera va en ``plan_comparison``); un fichero
    borrado cuenta como tocado."""
    if plan_files_expected is None:
        return NO_PLAN_COMPARISON

    extra, missing = compare_files([*files_created, *files_modified, *(files_deleted or [])], plan_files_expected)
    parts: list[str] = []
    if extra:
        parts.append(f"Archivos adicionales ({len(extra)}): " + _listed(extra))
    if missing:
        parts.append(f"Archivos esperados no tocados ({len(missing)}): " + _listed(missing))
    return "; ".join(parts) if parts else NO_DELTAS


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
