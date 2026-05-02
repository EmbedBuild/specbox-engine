"""Decisions queue — defer non-blocking gates instead of asking synchronously.

PR-6 (v5.29.0). Off-by-default: skills consult `autopilot.queue_enabled`
in `.claude/settings.local.json` and only enqueue when explicitly opted-in.
The user can review pending entries via `/queue review` (PR-14 work).

Storage: `doc/app/decisions_queue.md` — a Markdown file with two top-level
sections (Pendientes, Resueltas). Each entry is a `### [scope]` block with
metadata fields and a deterministic `Engine ID` for stable references.

The queue is intentionally line-oriented and human-friendly: the user can
read it, edit it, or commit it like any other doc. The engine writes it
through the helpers in this module so format drift is contained.

Inviolable: destructive actions, image_cost_over_budget, and AC quality
gates never enter the queue — those must always be synchronous.
"""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastmcp import FastMCP


QUEUE_FILE = "doc/app/decisions_queue.md"

# Decisions that must NEVER be queued — they require a synchronous human
# decision regardless of autopilot.queue_enabled.
INVIOLABLE_FOR_QUEUE: frozenset[str] = frozenset(
    {
        "destructive_action",
        "image_cost_over_budget",
        "branch_to_main_push",
        "definition_quality_gate",
        "feature_problem_definition",
        "feedback_field_classification",
    }
)


@dataclass
class QueueEntry:
    engine_id: str
    feature: str
    decision_key: str
    generated_at: str  # ISO 8601 UTC
    default_applied: str
    blocks: str  # short description of what this entry blocks
    action: str  # human-readable next step, e.g. "confirm | adjust | revert"
    evidence: str | None = None  # optional path or URL
    resolved_at: str | None = None
    resolution: str | None = None  # short text the user wrote when resolving
    auto_resolved: bool = False


# ── File I/O ─────────────────────────────────────────────────────────


def _queue_path(project_path: Path | str = ".") -> Path:
    return Path(project_path) / QUEUE_FILE


def _ensure_skeleton(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Decisions Queue\n\n"
        "Esta cola acumula decisiones que el engine pudo continuar con un default\n"
        "razonable pero que requieren tu visto bueno antes de marcar el UC como\n"
        "ACCEPTED. Las acciones destructivas y la calidad de specs nunca entran aquí.\n\n"
        "## Pendientes\n\n"
        "_(vacío)_\n\n"
        "## Resueltas\n\n"
        "_(vacío)_\n",
        encoding="utf-8",
    )


# ── Parsers ──────────────────────────────────────────────────────────


_HEADING_RE = re.compile(r"^### \[(?P<scope>[^\]]+)\]\s*(?P<title>.+?)\s*$")
_FIELD_RE = re.compile(r"^- \*\*(?P<key>[^:]+):\*\*\s*(?P<value>.*)$")


def _parse_entries(content: str) -> dict[str, list[QueueEntry]]:
    """Return {'pendientes': [...], 'resueltas': [...]}."""
    out: dict[str, list[QueueEntry]] = {"pendientes": [], "resueltas": []}
    section: str | None = None
    current: dict[str, str] | None = None

    for raw in content.splitlines():
        line = raw.rstrip()
        if line.startswith("## Pendientes"):
            section = "pendientes"
            current = None
            continue
        if line.startswith("## Resueltas"):
            if current is not None and section is not None:
                _commit_entry(out, section, current)
                current = None
            section = "resueltas"
            continue
        if section is None:
            continue
        m_head = _HEADING_RE.match(line)
        if m_head:
            if current is not None:
                _commit_entry(out, section, current)
            current = {
                "scope": m_head.group("scope"),
                "title": m_head.group("title"),
            }
            continue
        if current is None:
            continue
        m_field = _FIELD_RE.match(line)
        if m_field:
            key = m_field.group("key").strip().lower().replace(" ", "_")
            current[key] = m_field.group("value").strip()

    if current is not None and section is not None:
        _commit_entry(out, section, current)
    return out


def _commit_entry(out: dict[str, list[QueueEntry]], section: str, raw: dict[str, str]) -> None:
    scope = raw.get("scope", "")
    decision_key = raw.get("title", "").strip().split()[0] if raw.get("title") else ""
    feature = ""
    if "feature:" in scope:
        feature = scope.split("feature:", 1)[1].split("]")[0].split("[", 1)[0].strip()
    entry = QueueEntry(
        engine_id=raw.get("engine_id", ""),
        feature=feature or scope,
        decision_key=decision_key,
        generated_at=raw.get("generado", "") or raw.get("generated", ""),
        default_applied=raw.get("default_aplicado", "") or raw.get("default_applied", ""),
        blocks=raw.get("bloquea", "") or raw.get("blocks", ""),
        action=raw.get("acción", "") or raw.get("accion", "") or raw.get("action", ""),
        evidence=raw.get("evidencia") or raw.get("evidence"),
        resolved_at=raw.get("resuelto") or raw.get("resolved"),
        resolution=raw.get("resolución") or raw.get("resolucion") or raw.get("resolution"),
        auto_resolved=raw.get("auto_resolved", "false").lower() == "true",
    )
    out[section].append(entry)


# ── Renderers ────────────────────────────────────────────────────────


def _render(state: dict[str, list[QueueEntry]]) -> str:
    lines: list[str] = [
        "# Decisions Queue",
        "",
        "Esta cola acumula decisiones que el engine pudo continuar con un default",
        "razonable pero que requieren tu visto bueno antes de marcar el UC como",
        "ACCEPTED. Las acciones destructivas y la calidad de specs nunca entran aquí.",
        "",
        "## Pendientes",
        "",
    ]
    if not state["pendientes"]:
        lines.append("_(vacío)_")
    else:
        for entry in state["pendientes"]:
            lines.extend(_render_entry(entry, resolved=False))
    lines.extend(["", "## Resueltas", ""])
    if not state["resueltas"]:
        lines.append("_(vacío)_")
    else:
        for entry in state["resueltas"]:
            lines.extend(_render_entry(entry, resolved=True))
    return "\n".join(lines) + "\n"


def _render_entry(entry: QueueEntry, *, resolved: bool) -> list[str]:
    out = [f"### [feature: {entry.feature}] {entry.decision_key}", ""]
    out.append(f"- **Engine ID:** {entry.engine_id}")
    if entry.generated_at:
        out.append(f"- **Generado:** {entry.generated_at}")
    if entry.default_applied:
        out.append(f"- **Default aplicado:** {entry.default_applied}")
    if entry.blocks:
        out.append(f"- **Bloquea:** {entry.blocks}")
    if entry.action:
        out.append(f"- **Acción:** {entry.action}")
    if entry.evidence:
        out.append(f"- **Evidencia:** {entry.evidence}")
    if resolved:
        if entry.resolved_at:
            out.append(f"- **Resuelto:** {entry.resolved_at}")
        if entry.resolution:
            out.append(f"- **Resolución:** {entry.resolution}")
        if entry.auto_resolved:
            out.append("- **Auto_resolved:** true")
    out.append("")
    return out


# ── Public API ───────────────────────────────────────────────────────


def _new_engine_id(decision_key: str) -> str:
    short_key = decision_key.split("_")[0][:6]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    rand = secrets.token_hex(2)
    return f"dq-{stamp}-{rand}-{short_key}"


def enqueue_decision(
    decision_key: str,
    feature: str,
    *,
    default_applied: str,
    blocks: str = "",
    action: str = "confirm | adjust | revert",
    evidence: str | None = None,
    project_path: str | Path = ".",
) -> dict[str, Any]:
    """Append a pending entry to `doc/app/decisions_queue.md`.

    Returns the created QueueEntry as a dict, or an error dict if the
    decision_key is on the inviolable-for-queue list.
    """
    if decision_key in INVIOLABLE_FOR_QUEUE:
        return {
            "ok": False,
            "error": "queue_not_allowed_for_inviolable",
            "message": (
                f"decision_key {decision_key!r} cannot be queued — these gates "
                "must remain synchronous regardless of queue_enabled."
            ),
        }
    path = _queue_path(project_path)
    _ensure_skeleton(path)
    state = _parse_entries(path.read_text(encoding="utf-8"))
    entry = QueueEntry(
        engine_id=_new_engine_id(decision_key),
        feature=feature,
        decision_key=decision_key,
        generated_at=datetime.now(timezone.utc).isoformat(),
        default_applied=default_applied,
        blocks=blocks,
        action=action,
        evidence=evidence,
    )
    state["pendientes"].append(entry)
    path.write_text(_render(state), encoding="utf-8")
    return {"ok": True, "entry": entry.__dict__}


def list_queue(project_path: str | Path = ".") -> dict[str, Any]:
    """Return both pendientes and resueltas as lists of dicts."""
    path = _queue_path(project_path)
    if not path.exists():
        return {"exists": False, "pendientes": [], "resueltas": []}
    state = _parse_entries(path.read_text(encoding="utf-8"))
    return {
        "exists": True,
        "path": str(path),
        "pendientes": [e.__dict__ for e in state["pendientes"]],
        "resueltas": [e.__dict__ for e in state["resueltas"]],
        "pending_count": len(state["pendientes"]),
        "resolved_count": len(state["resueltas"]),
    }


def resolve_entry(
    engine_id: str,
    *,
    resolution: str,
    auto_resolved: bool = False,
    project_path: str | Path = ".",
) -> dict[str, Any]:
    """Move an entry from pendientes to resueltas with a resolution note."""
    path = _queue_path(project_path)
    if not path.exists():
        return {"ok": False, "error": "queue_file_not_found"}
    state = _parse_entries(path.read_text(encoding="utf-8"))
    target: QueueEntry | None = None
    for entry in state["pendientes"]:
        if entry.engine_id == engine_id:
            target = entry
            break
    if target is None:
        return {"ok": False, "error": "engine_id_not_found", "engine_id": engine_id}
    state["pendientes"].remove(target)
    target.resolved_at = datetime.now(timezone.utc).isoformat()
    target.resolution = resolution
    target.auto_resolved = auto_resolved
    state["resueltas"].insert(0, target)
    path.write_text(_render(state), encoding="utf-8")
    return {"ok": True, "entry": target.__dict__}


# ── MCP registration ─────────────────────────────────────────────────


def register_queue_tools(mcp: FastMCP, engine_path: Path) -> None:
    """Expose the decisions queue as MCP tools."""

    @mcp.tool
    def enqueue_decision_tool(
        decision_key: str,
        feature: str,
        default_applied: str,
        project_path: str = ".",
        blocks: str = "",
        action: str = "confirm | adjust | revert",
        evidence: str | None = None,
    ) -> dict[str, Any]:
        """Append a pending decision to doc/app/decisions_queue.md.

        Skills call this when the user has autopilot.queue_enabled=true and
        the decision falls in the deferrable category (not inviolable).
        Returns {ok, entry} or {ok: false, error: ...} for invalid keys.
        """
        return enqueue_decision(
            decision_key,
            feature,
            default_applied=default_applied,
            blocks=blocks,
            action=action,
            evidence=evidence,
            project_path=project_path,
        )

    @mcp.tool
    def list_decisions_queue(project_path: str = ".") -> dict[str, Any]:
        """List pendientes and resueltas in the decisions queue."""
        return list_queue(project_path)

    @mcp.tool
    def resolve_queue_entry(
        engine_id: str,
        resolution: str,
        project_path: str = ".",
        auto_resolved: bool = False,
    ) -> dict[str, Any]:
        """Move a queue entry from pendientes to resueltas.

        Args:
            engine_id: The dq-... id printed when the entry was enqueued.
            resolution: Short note describing what the user decided.
            auto_resolved: Set true when called by the auto-resolve job
                after queue_auto_resolve_days have passed.
        """
        return resolve_entry(
            engine_id,
            resolution=resolution,
            auto_resolved=auto_resolved,
            project_path=project_path,
        )
