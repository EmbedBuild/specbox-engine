"""Stitch migration tools (v6.5.0).

Two MCP tools that orchestrate the move from the v5.31 ``inline-prefix``
contract to the v6.4.0 ``native_v2`` chain. Both follow the
content-passing convention (v6.0.1 MCP Path Contract): the **client**
reads project files from its filesystem, passes the contents as strings,
and writes back whatever the tool returns.

Tools:
    - ``detect_stitch_migration_case`` — classifies a project into one of
      6 cases (A-F) so the caller knows which migration recipe to invoke.
    - ``migrate_project_to_native_v2`` — given a case classification +
      the project's design.md + settings, produces the recipe (file
      contents + Stitch API calls) the client must apply. The tool is
      **planning-only** — it does not write to the client's filesystem
      and does not call Stitch on behalf of the client. The skill
      ``/visual-setup --migrate-stitch`` is the orchestrator that
      actually executes the recipe.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Literal

import structlog
from fastmcp import FastMCP

logger = structlog.get_logger(__name__)


MigrationCase = Literal["A", "B", "C", "D", "E", "F"]


# ── Detection ────────────────────────────────────────────────────────


_HEX_RE = re.compile(r"#([0-9A-Fa-f]{6,8})")
# Markers that suggest the file already follows the Material 3 frontmatter
# layout SpecBox emits when contract=native_v2.
_M3_FRONTMATTER_MARKERS = (
    "colorMode",
    "headlineFont",
    "bodyFont",
    "customColor",
    "colorVariant",
    "roundness",
)
# Markers that suggest the legacy SpecBox-native frontmatter (v5.31).
_LEGACY_FRONTMATTER_MARKERS = (
    "fontFamily:",
    "fontSize:",
    "text_primary:",
    "primary_hover:",
)


@dataclass
class DesignMdShape:
    """Coarse classification of a DESIGN.md frontmatter."""

    has_frontmatter: bool
    is_material3: bool
    is_legacy_specbox: bool
    is_custom: bool  # neither shape — user-edited


def _classify_design_md(content: str | None) -> DesignMdShape:
    if not content or "---" not in content:
        return DesignMdShape(False, False, False, False)
    parts = content.split("---", 2)
    if len(parts) < 3:
        return DesignMdShape(False, False, False, False)
    front = parts[1]
    m3_hits = sum(1 for m in _M3_FRONTMATTER_MARKERS if m in front)
    legacy_hits = sum(1 for m in _LEGACY_FRONTMATTER_MARKERS if m in front)
    is_m3 = m3_hits >= 2
    is_legacy = legacy_hits >= 2 and not is_m3
    return DesignMdShape(
        has_frontmatter=True,
        is_material3=is_m3,
        is_legacy_specbox=is_legacy,
        is_custom=not is_m3 and not is_legacy,
    )


@dataclass
class SettingsView:
    """Parsed view of ``.claude/settings.local.json`` slices we care about."""

    contract: str | None  # stitch.contract
    stitch_project_id: str | None
    multirepo_role: str | None  # multirepo.role (orchestrator|satellite)


def _parse_settings(settings_content: str | None) -> SettingsView:
    if not settings_content:
        return SettingsView(None, None, None)
    try:
        data = json.loads(settings_content)
    except (json.JSONDecodeError, TypeError):
        return SettingsView(None, None, None)
    stitch = data.get("stitch") or {}
    multirepo = data.get("multirepo") or {}
    return SettingsView(
        contract=stitch.get("contract"),
        stitch_project_id=stitch.get("projectId"),
        multirepo_role=multirepo.get("role"),
    )


def _classify_case(
    settings: SettingsView,
    design_shape: DesignMdShape,
    *,
    generated_screens_count: int,
) -> tuple[MigrationCase, str]:
    """Return ``(case, rationale)`` for the migration classifier."""

    # F — multirepo orchestrator/satellite topology
    if settings.multirepo_role in {"orchestrator", "satellite"}:
        return "F", (
            f"multirepo role={settings.multirepo_role!r} — migration is "
            "driven by the orchestrator; satellites inherit"
        )

    # A — already on native_v2
    if settings.contract == "native_v2":
        return "A", "stitch.contract is already 'native_v2' — no-op"

    # B — Stitch settings present but never used
    if settings.stitch_project_id and generated_screens_count == 0 and not design_shape.has_frontmatter:
        return "B", (
            "Stitch project configured but no DESIGN.md and 0 screens "
            "generated — flip the marker, no data migration needed"
        )

    # E — custom DESIGN.md (user edited, not following SpecBox conventions)
    if design_shape.has_frontmatter and design_shape.is_custom:
        return "E", (
            "DESIGN.md has a frontmatter that is neither Material 3 nor "
            "legacy SpecBox v5.31 — user customisation detected; mapping "
            "proposal required before migration"
        )

    # D — Stitch project with screens but DS not bound
    if settings.stitch_project_id and generated_screens_count > 0:
        return "D", (
            f"Stitch project with {generated_screens_count} generated "
            "screen(s); migration must retroactively apply the new DS "
            "(default: D.2 assisted retroactive)"
        )

    # C — DESIGN.md exists but no Stitch project bound
    if design_shape.has_frontmatter:
        return "C", (
            "DESIGN.md present but no Stitch projectId in settings — "
            "regenerate DESIGN.md as Material 3, bootstrap the Stitch "
            "project + DS"
        )

    # Fallthrough: nothing to migrate.
    return "B", (
        "no Stitch artefacts detected — safe to mark native_v2 on next "
        "/visual-setup run"
    )


def _recipe_for_case(
    case: MigrationCase,
    *,
    project_name: str,
    has_design_md: bool,
    settings_view: SettingsView,
) -> dict:
    """Construct the recipe payload the client (skill) will execute."""

    base = {
        "case": case,
        "project": project_name,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "actions": [],
        "files_to_write": [],
        "stitch_calls": [],
        "settings_patch": {},
        "confirmation_required": None,
        "notes": [],
    }
    if case == "A":
        base["actions"].append("noop")
        base["notes"].append("Project already on native_v2 — nothing to do.")
        return base
    if case == "B":
        base["actions"].append("set_contract_native_v2")
        base["settings_patch"] = {"stitch": {"contract": "native_v2"}}
        base["notes"].append(
            "No DESIGN.md and no screens — purely a settings flip. "
            "Subsequent /visual-setup runs will produce native_v2 output."
        )
        return base
    if case == "C":
        base["actions"].extend([
            "backup_design_md_if_present",
            "regenerate_design_md_as_native_v2",
            "create_stitch_project_if_missing",
            "upload_design_md_via_rest_batch_create",
            "create_design_system_from_design_md",
            "list_design_systems",
            "set_contract_native_v2",
        ])
        base["settings_patch"] = {"stitch": {"contract": "native_v2"}}
        base["files_to_write"].append({
            "path": "doc/design/DESIGN.md.pre-migration.bak",
            "from": "doc/design/DESIGN.md",
            "if_exists": True,
            "rationale": "Always keep the pre-migration original",
        })
        base["stitch_calls"].extend([
            {"tool": "stitch_create_project", "args_template": {"title": project_name}},
            {"tool": "stitch_upload_design_md", "args_template": {"design_md_content": "<regenerated>"}},
            {"tool": "stitch_create_design_system_from_design_md", "args_template": {}},
            {"tool": "stitch_list_design_systems", "args_template": {}},
        ])
        return base
    if case == "D":
        base["actions"].extend([
            "backup_design_md",
            "regenerate_design_md_as_native_v2",
            "upload_design_md_via_rest_batch_create",
            "create_design_system_from_design_md",
            "list_design_systems",
            "list_screens",
            "preview_apply_design_system",
            "WAIT_FOR_LITERAL_CONFIRMATION",
            "apply_design_system_to_all_screens",
            "set_contract_native_v2",
        ])
        base["settings_patch"] = {"stitch": {"contract": "native_v2"}}
        base["files_to_write"].append({
            "path": "doc/design/DESIGN.md.pre-migration.bak",
            "from": "doc/design/DESIGN.md",
            "if_exists": True,
            "rationale": "Always keep the pre-migration original",
        })
        base["confirmation_required"] = {
            "literal": "MIGRATE-RETROACTIVE",
            "after_step": "preview_apply_design_system",
            "rationale": (
                "apply_design_system rewrites visual output of existing "
                "screens. The maintainer chose D.2 retroactive as default "
                "but every project may produce regressions — block until "
                "the user types the exact literal."
            ),
        }
        base["notes"].append(
            f"Stitch project {settings_view.stitch_project_id!r} has screens "
            "that will be re-themed in place."
        )
        return base
    if case == "E":
        base["actions"].extend([
            "generate_mapping_proposal_material3",
            "WRITE_PROPOSAL_FOR_REVIEW",
        ])
        base["files_to_write"].append({
            "path": "doc/design/migration_proposal_material3.md",
            "from": "<derived from current DESIGN.md>",
            "rationale": "Custom DESIGN.md must be reviewed before overwrite",
        })
        base["confirmation_required"] = {
            "literal": "APPLY-PROPOSAL",
            "after_step": "WRITE_PROPOSAL_FOR_REVIEW",
            "rationale": (
                "User edited DESIGN.md by hand; we must not overwrite "
                "without their explicit approval of the new mapping."
            ),
        }
        return base
    if case == "F":
        base["actions"].append("delegate_to_orchestrator")
        base["notes"].append(
            "Multirepo: only the orchestrator runs the migration. "
            "Satellites inherit via the engine's orchestratorRoot path "
            "resolution."
        )
        return base
    return base


# ── Telemetry ────────────────────────────────────────────────────────


def aggregate_migration_log(jsonl_lines: list[str]) -> dict:
    """Pure aggregator over migration jsonl entries.

    Input lines are arbitrary JSONL coming from the client's
    ``.quality/logs/stitch-migration.jsonl``. Anything that doesn't
    parse is silently skipped — telemetry must not fail loud on bad
    rows. Returns counts per case + per action + per outcome.
    """
    by_case: dict[str, int] = {}
    by_action: dict[str, int] = {}
    by_outcome: dict[str, int] = {}
    total = 0
    for line in jsonl_lines:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        total += 1
        case = row.get("case")
        if isinstance(case, str):
            by_case[case] = by_case.get(case, 0) + 1
        action = row.get("action")
        if isinstance(action, str):
            by_action[action] = by_action.get(action, 0) + 1
        outcome = row.get("outcome")
        if isinstance(outcome, str):
            by_outcome[outcome] = by_outcome.get(outcome, 0) + 1
    return {
        "total_events": total,
        "by_case": by_case,
        "by_action": by_action,
        "by_outcome": by_outcome,
    }


# ── MCP tool registration ────────────────────────────────────────────


def register_stitch_migration_tools(mcp: FastMCP) -> None:
    """Register the migration MCP tools on the FastMCP server."""

    @mcp.tool
    async def detect_stitch_migration_case(
        project: str,
        settings_local_json: str | None = None,
        design_md_content: str | None = None,
        generated_screens_count: int = 0,
    ) -> dict:
        """Classify a project into one of 6 Stitch migration cases.

        Follows the v6.0.1 MCP Path Contract: the client reads its own
        ``.claude/settings.local.json`` and ``doc/design/DESIGN.md`` and
        passes their text contents here, plus a count of how many screens
        the project has already produced.

        Args:
            project: SpecBox project slug (for telemetry only).
            settings_local_json: Contents of
                ``.claude/settings.local.json`` if it exists, else None.
            design_md_content: Contents of ``doc/design/DESIGN.md`` if it
                exists, else None.
            generated_screens_count: How many screens are currently in
                the Stitch project. Used to decide between cases B and D.
                Pass 0 when unknown.

        Returns:
            ``{case, rationale, evidence}`` where ``case`` is one of
            "A".."F" and ``evidence`` echoes the parsed inputs that
            informed the classification (no secrets — settings hex
            colors only).
        """
        settings = _parse_settings(settings_local_json)
        shape = _classify_design_md(design_md_content)
        case, rationale = _classify_case(
            settings, shape, generated_screens_count=generated_screens_count
        )
        return {
            "case": case,
            "rationale": rationale,
            "evidence": {
                "settings": {
                    "contract": settings.contract,
                    "stitch_project_id_present": bool(settings.stitch_project_id),
                    "multirepo_role": settings.multirepo_role,
                },
                "design_md": {
                    "has_frontmatter": shape.has_frontmatter,
                    "is_material3": shape.is_material3,
                    "is_legacy_specbox": shape.is_legacy_specbox,
                    "is_custom": shape.is_custom,
                },
                "generated_screens_count": generated_screens_count,
            },
            "recommended_action": _recommendation_for(case),
        }

    @mcp.tool
    async def migrate_project_to_native_v2(
        project: str,
        case: str,
        settings_local_json: str | None = None,
        design_md_content: str | None = None,
    ) -> dict:
        """Produce a step-by-step migration recipe for the client to execute.

        Planning-only: this tool **does not** call Stitch, write files,
        or mutate the project. The caller (typically the
        ``/visual-setup --migrate-stitch`` skill) is responsible for
        executing each ``action`` in order, using the
        ``stitch_*`` MCP tools and standard file I/O.

        Args:
            project: SpecBox project slug.
            case: One of "A".."F" — usually the value returned by
                ``detect_stitch_migration_case``.
            settings_local_json: Same as
                ``detect_stitch_migration_case``.
            design_md_content: Same as
                ``detect_stitch_migration_case``.

        Returns:
            A recipe dict with:
              * ``actions``: ordered list of step identifiers
              * ``files_to_write``: file backup + write plans
              * ``stitch_calls``: which Stitch MCP tools to invoke
              * ``settings_patch``: JSON patch for
                ``.claude/settings.local.json``
              * ``confirmation_required``: literal-string gate, if any
              * ``notes``: human-readable rationale
        """
        if case not in {"A", "B", "C", "D", "E", "F"}:
            return {
                "error": (
                    f"unknown case {case!r}. Use detect_stitch_migration_case "
                    "first or pass one of A, B, C, D, E, F."
                )
            }
        settings_view = _parse_settings(settings_local_json)
        # design_md_content is not directly used in the recipe today,
        # but kept in the signature for parity with the detector and
        # future use (case E proposal generation will need it).
        _ = design_md_content
        recipe = _recipe_for_case(
            case,  # type: ignore[arg-type]
            project_name=project,
            has_design_md=bool(design_md_content),
            settings_view=settings_view,
        )
        return recipe

    @mcp.tool
    async def get_stitch_migration_stats(
        project: str,
        migration_jsonl_content: str | None = None,
    ) -> dict:
        """Aggregate the project's Stitch migration telemetry.

        Content-passing per v6.0.1 MCP Path Contract: the client reads
        ``.quality/logs/stitch-migration.jsonl`` from its own filesystem
        and passes the full text here. The tool returns counts per
        case, per action and per outcome plus a derived ``status``
        verdict useful for v7.0-cutover readiness dashboards.

        Args:
            project: SpecBox project slug (telemetry only).
            migration_jsonl_content: Raw contents of
                ``.quality/logs/stitch-migration.jsonl``. May be None
                or empty — both yield zero counts.

        Returns:
            ``{project, total_events, by_case, by_action, by_outcome,
              status}``. ``status`` is one of:
              * ``"no_data"`` — log empty / missing
              * ``"in_progress"`` — events exist but no ``success``
                outcome for ``set_contract_native_v2``
              * ``"completed"`` — at least one successful contract flip
              * ``"failed"`` — last outcome is ``fail``
        """
        lines = (migration_jsonl_content or "").splitlines()
        agg = aggregate_migration_log(lines)
        outcomes = agg["by_outcome"]
        actions = agg["by_action"]
        if agg["total_events"] == 0:
            status = "no_data"
        elif outcomes.get("fail", 0) > outcomes.get("ok", 0):
            status = "failed"
        elif (
            actions.get("set_contract_native_v2", 0) > 0
            and outcomes.get("ok", 0) > 0
        ):
            status = "completed"
        else:
            status = "in_progress"
        return {
            "project": project,
            "status": status,
            **agg,
        }


def _recommendation_for(case: MigrationCase) -> str:
    return {
        "A": "no_op",
        "B": "mark_native_v2_no_data_migration",
        "C": "migrate_design_md_then_bootstrap_ds",
        "D": "d2_retroactive_assisted",
        "E": "generate_mapping_proposal_for_review",
        "F": "migrate_orchestrator_only",
    }[case]


__all__ = [
    "DesignMdShape",
    "MigrationCase",
    "SettingsView",
    "aggregate_migration_log",
    "register_stitch_migration_tools",
]
