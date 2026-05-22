"""Evidence regeneration after a backend switch (UC-405, AC-14/AC-15/AC-16).

After a project migrates from one spec backend to another, the acceptance
evidence stored under ``.quality/evidence/{feature}/acceptance/results.json``
is indexed by the **logical** ``uc_id`` (see ``doc/specs/results-json-spec.md``),
not by any backend-specific id — so the link survives the migration. But the
evidence can become *stale* relative to the current code.

``regenerate_evidence`` is an **opt-in** tool that:

1. Scans every ``.quality/evidence/*/acceptance/results.json`` and deduces the
   logical ``uc_id`` of each one (the UCs that already had evidence).
2. For each such UC (optionally filtered by the ``ucs`` argument), it re-runs
   acceptance via an injected ``acceptance_runner`` callable, which rewrites the
   ``results.json`` (and HTML report) against the current code.
3. Reports progress per UC in the exact format
   ``[X/N] UC-XXX: {PASS|FAIL|SKIP} ({n} ACs con evidencia)``.
4. Persists a Markdown summary to
   ``doc/migrations/evidence_regeneration_{timestamp}.md``.

The ``acceptance_runner`` is injected (default ``None``) so tests can supply a
fake; the registered MCP tool resolves it to the real
:func:`server.tools.acceptance.run_acceptance_check_impl`. This mirrors the
``*_writer`` injection pattern used by ``server/migration/transactional_switch.py``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

# A runner takes (project_path, uc_id, branch) and returns a dict carrying a
# "verdict" key (ACCEPTED / CONDITIONAL / REJECTED). It is responsible for
# rewriting the relevant results.json with a fresh timestamp.
AcceptanceRunner = Callable[[str, str, str], dict]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _scan_ucs_with_evidence(project_path: str) -> dict[str, dict]:
    """Find the logical UCs that already have acceptance evidence.

    Scans ``.quality/evidence/*/acceptance/results.json`` and reads the
    ``uc_id`` from each one.

    Returns:
        Mapping ``{uc_id: {"feature": str, "results_path": str, "n_acs": int}}``.
        ``n_acs`` is the number of AC entries in the results file
        (``results`` array length, falling back to ``criteria``), or 0.
        If two evidence dirs reference the same ``uc_id``, the first found wins.
    """
    pp = Path(project_path)
    evidence_base = pp / ".quality" / "evidence"
    found: dict[str, dict] = {}
    if not evidence_base.is_dir():
        return found

    for feature_dir in sorted(evidence_base.iterdir()):
        if not feature_dir.is_dir():
            continue
        results_path = feature_dir / "acceptance" / "results.json"
        if not results_path.is_file():
            continue
        try:
            data = json.loads(results_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, dict):
            continue
        uc_id = str(data.get("uc_id", "")).upper().strip()
        if not uc_id:
            continue
        if uc_id in found:
            continue
        n_acs = 0
        results = data.get("results")
        if isinstance(results, list):
            n_acs = len(results)
        elif isinstance(data.get("criteria"), list):
            n_acs = len(data["criteria"])
        found[uc_id] = {
            "feature": feature_dir.name,
            "results_path": str(results_path),
            "n_acs": n_acs,
        }
    return found


def _verdict_to_status(verdict: str) -> str:
    """Map an acceptance verdict to PASS / FAIL.

    PASS only when ACCEPTED; REJECTED and CONDITIONAL are FAIL. SKIP is decided
    by the caller (runner failed / unavailable), not here.
    """
    return "PASS" if str(verdict).upper().strip() == "ACCEPTED" else "FAIL"


def _write_regen_report(
    project_path: str,
    summary: dict,
    progress_lines: list[str],
    timestamp: str,
) -> str:
    """Write ``doc/migrations/evidence_regeneration_{timestamp}.md``.

    Creates ``doc/migrations/`` if missing. ``timestamp`` is expected to be a
    filesystem-safe token (no colons). Returns the absolute path written.
    """
    migrations_dir = Path(project_path) / "doc" / "migrations"
    migrations_dir.mkdir(parents=True, exist_ok=True)
    report_path = migrations_dir / f"evidence_regeneration_{timestamp}.md"

    regenerated = summary.get("regenerated", [])
    failed = summary.get("failed", [])
    pending = summary.get("pending", [])
    total = len(regenerated) + len(failed) + len(pending)

    lines: list[str] = [
        "# Regeneración de evidencias de acceptance",
        "",
        f"**Generado**: {timestamp}",
        f"**Total UCs procesados**: {total}",
        "",
        "## Resumen",
        "",
        f"- Regenerados (PASS): {len(regenerated)} — {', '.join(regenerated) or '—'}",
        f"- Fallidos (FAIL): {len(failed)} — {', '.join(failed) or '—'}",
        f"- Omitidos (SKIP): {len(pending)} — {', '.join(pending) or '—'}",
        "",
        "## Detalle por UC",
        "",
    ]
    # One line per UC processed (progress_lines already has the exact format).
    for pline in progress_lines:
        lines.append(f"- {pline}")
    lines.append("")
    lines.append("---")
    lines.append("*SpecBox Engine — regenerate_evidence (UC-405)*")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(report_path)


def regenerate_evidence_impl(
    project_path: str,
    ucs: list[str] | None = None,
    acceptance_runner: AcceptanceRunner | None = None,
    branch: str = "",
    now: Callable[[], datetime] | None = None,
) -> dict:
    """Re-run acceptance for every UC that already had evidence (AC-14/15/16).

    Args:
        project_path: Absolute path to the project root.
        ucs: Optional list of UC ids to restrict to. If ``None``, all UCs that
            have prior evidence are processed. UC ids are matched case-insensitively.
        acceptance_runner: Callable ``(project_path, uc_id, branch) -> dict`` that
            re-runs acceptance and rewrites the UC's ``results.json`` with a fresh
            timestamp; the returned dict must carry a ``"verdict"`` key. Required
            (the registered MCP tool injects the real runner). Raising / returning
            a non-dict marks the UC as SKIP.
        branch: Git branch passed through to the runner. Empty = current branch.
        now: Injectable clock for deterministic timestamps in tests.

    Returns:
        ``{"total": N, "progress_lines": [...], "summary": {"regenerated": [...],
        "failed": [...], "pending": [...]}, "report_path": str}``.
    """
    clock = now or _utcnow
    started_at = clock()

    if acceptance_runner is None:
        return {
            "error": "acceptance_runner is required (the MCP tool injects the real one)",
            "total": 0,
            "progress_lines": [],
            "summary": {"regenerated": [], "failed": [], "pending": []},
        }

    discovered = _scan_ucs_with_evidence(project_path)

    # Determine the target UC order (sorted for deterministic progress numbering).
    if ucs is not None:
        wanted = {str(u).upper().strip() for u in ucs}
        target_ucs = [uc for uc in sorted(discovered) if uc in wanted]
    else:
        target_ucs = sorted(discovered)

    total = len(target_ucs)
    progress_lines: list[str] = []
    regenerated: list[str] = []
    failed: list[str] = []
    pending: list[str] = []

    for idx, uc_id in enumerate(target_ucs, start=1):
        meta = discovered[uc_id]
        n_acs = meta.get("n_acs", 0)
        status = "SKIP"
        try:
            result = acceptance_runner(project_path, uc_id, branch)
        except Exception:  # noqa: BLE001 — any runner failure → SKIP
            result = None

        if isinstance(result, dict) and not result.get("error"):
            verdict = result.get("verdict")
            if verdict:
                status = _verdict_to_status(verdict)
        # else: runner could not run / returned error / None → SKIP

        if status == "PASS":
            regenerated.append(uc_id)
        elif status == "FAIL":
            failed.append(uc_id)
        else:
            pending.append(uc_id)

        progress_lines.append(f"[{idx}/{total}] {uc_id}: {status} ({n_acs} ACs con evidencia)")

    summary = {
        "regenerated": regenerated,
        "failed": failed,
        "pending": pending,
    }

    # Filesystem-safe timestamp token (no colons) for the report filename.
    ts_token = started_at.strftime("%Y%m%dT%H%M%SZ")
    report_path = _write_regen_report(project_path, summary, progress_lines, ts_token)

    return {
        "total": total,
        "progress_lines": progress_lines,
        "summary": summary,
        "report_path": report_path,
        "started_at": started_at.isoformat(),
    }


def register_evidence_regen_tools(mcp, engine_path: Path, state_path: Path):
    """Register the ``regenerate_evidence`` MCP tool (UC-405)."""

    @mcp.tool
    def regenerate_evidence(
        project_path: str,
        ucs: list[str] | None = None,
        branch: str = "",
    ) -> dict:
        """Re-run acceptance for UCs that already had evidence, refreshing results.json.

        Opt-in tool intended to run after a backend switch, when acceptance
        evidence may have gone stale relative to the current code. Scans
        ``.quality/evidence/*/acceptance/results.json`` to find the logical UCs
        with prior evidence and re-runs acceptance for each, regenerating
        ``results.json`` + HTML report with a fresh timestamp. Reports progress
        per UC and persists a Markdown summary under ``doc/migrations/``.

        Args:
            project_path: Absolute path to the project root.
            ucs: Optional list of UC ids to restrict to. If omitted, every UC with
                prior evidence is regenerated.
            branch: Git branch to check (passed to the acceptance runner).

        Returns:
            JSON with ``total``, ``progress_lines``, ``summary``
            (regenerated/failed/pending), and the ``report_path``.
        """
        from .acceptance import run_acceptance_check_impl

        def _runner(pp: str, uc_id: str, br: str) -> dict:
            return run_acceptance_check_impl(pp, uc_id, br)

        return regenerate_evidence_impl(
            project_path,
            ucs=ucs,
            acceptance_runner=_runner,
            branch=branch,
        )
