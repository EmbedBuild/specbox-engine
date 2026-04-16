"""
SpecBox Engine MCP Server v5.22.2

Unified MCP endpoint: 114 tools (engine + spec-driven + migration + telemetry + stitch + quality-audit).
Soporta stdio (Claude Code local) y streamable-http (remoto).

Architecture:
  - Engine (repo root): Read-only. Skills, plans, architecture, templates.
  - State  (/data/state): Read-write. Project registry, sessions, checkpoints, healing.
"""

import os
from pathlib import Path

import structlog
from fastmcp import FastMCP

from .tools.plans import register_plan_tools
from .tools.quality import register_quality_tools
from .tools.skills import register_skill_tools
from .tools.features import register_feature_tools
from .tools.engine import register_engine_tools
from .tools.telemetry import register_telemetry_tools
from .tools.hooks import register_hook_tools
from .tools.onboarding import register_onboarding_tools
from .tools.state import register_state_tools
from .tools.spec_driven import register_spec_driven_tools
from .tools.spec_mutations import register_spec_mutations_tools
from .tools.milestone_management import register_milestone_management_tools
from .tools.board_operations import register_board_operations_tools
from .tools.acceptance_automation import register_acceptance_automation_tools
from .tools.migration import register_migration_tools
from .tools.sync import register_sync_tools
from .tools.acceptance import register_acceptance_tools
from .tools.benchmark import register_benchmark_tools
from .tools.hints import register_hint_tools
from .tools.skill_registry import register_skill_registry_tools
from .tools.live_state import register_live_state_tools
from .tools.heartbeat_stats import register_heartbeat_stats_tools
from .tools.stitch import register_stitch_tools
from .tools.audit import register_audit_tools
from .resources.engine_resources import register_resources
from .dashboard_api import register_dashboard_routes

# Configure structlog
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
        if os.getenv("LOG_FORMAT") == "json"
        else structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

# ENGINE_PATH: In monorepo, engine content is at the repo root (parent of server/)
ENGINE_PATH = Path(os.getenv("ENGINE_PATH", Path(__file__).parent.parent)).resolve()
STATE_PATH = Path(os.getenv("STATE_PATH", "/data/state"))
STATE_PATH.mkdir(parents=True, exist_ok=True)

mcp = FastMCP(
    "specbox-engine",
    instructions="""
    MCP server for the SpecBox Engine v5.22.2 — an agentic programming system for Claude Code.

    Use these tools to:
    - Query implementation plans and their status
    - Check quality baselines and evidence
    - List available Agent Skills with auto-discovery metadata
    - Track features in progress (checkpoints and healing events)
    - Get engine version and configuration
    - Monitor session telemetry and development patterns
    - Inspect self-healing events and resolution rates
    - View hooks configuration and enforcement status
    - Get comprehensive activity dashboards
    - Read agent prompts and global coding rules
    - Onboard new projects with auto-detected stack, infra, and quality gates
    - Upgrade onboarded projects to the latest engine templates (single or batch)
    - Check version matrix to see which projects need upgrading
    - Report and query development state (sessions, checkpoints, healing)
    - Report acceptance test results and validation verdicts (AG-09a/AG-09b)
    - Report developer feedback from manual testing and track resolutions
    - Report merge pipeline status (sequential merge tracking, feedback blocking)
    - Report E2E test results (Playwright) and track pass rates across projects
    - View the Sala de Máquinas global dashboard across all projects
    - Manage Trello boards for spec-driven development (US/UC/AC hierarchy)
    - Manage Plane projects for spec-driven development (US/UC/AC hierarchy)
    - Import project specifications, track progress, attach evidence
    - Find next UC to implement, mark acceptance criteria, generate delivery reports
    - Migrate projects bidirectionally between Trello and Plane
    - Query Spec-Code Sync status (implementation deltas vs plan)
    - Run standalone acceptance checks against PRDs without full /implement
    - Generate public benchmark snapshots with anonymized project metrics
    - Manage contextual hints for new developers
    - Discover and validate external skill manifests
    - Query live project state (heartbeat snapshots, session activity)
    - Sync project state from GitHub repos when local machine is off
    - Get conversational project summaries optimized for mobile queries
    - Proxy Google Stitch design tools (generate, edit, variants, design DNA, build site)

    The engine manages Flutter, React, Go, Python, and Google Apps Script projects
    with automated PRD → Plan → Implement → PR pipelines, self-healing protocol,
    acceptance validation (AG-09a/AG-09b), feedback loop, E2E testing telemetry,
    and quality gates with ratchet enforcement.

    Architecture:
    1. Engine (read-only): Skills, plans, architecture docs, templates.
    2. State (read-write): Project registry, sessions, checkpoints, healing,
       acceptance tests, acceptance validations, merge events, E2E results.
       Populated by hooks (fire-and-forget HTTP) and queried by dashboard tools.
    """
)

# Register engine tools
register_plan_tools(mcp, ENGINE_PATH)
register_quality_tools(mcp, ENGINE_PATH)
register_skill_tools(mcp, ENGINE_PATH)
register_feature_tools(mcp, ENGINE_PATH)
register_engine_tools(mcp, ENGINE_PATH)
register_telemetry_tools(mcp, ENGINE_PATH)
register_hook_tools(mcp, ENGINE_PATH)
register_onboarding_tools(mcp, ENGINE_PATH, STATE_PATH)
register_state_tools(mcp, ENGINE_PATH, STATE_PATH)
register_resources(mcp, ENGINE_PATH)

# Register spec-driven tools (21 tools)
register_spec_driven_tools(mcp)

# Register Tier 1 mutation tools (v5.23.0 Full Mutations — 8 tools:
# update_uc, update_uc_batch, update_us, update_ac, update_ac_batch,
# add_ac, delete_ac, add_uc)
register_spec_mutations_tools(mcp)

# Register Tier 2 milestone & multirepo tools (v5.23.0 — 8 tools:
# set_uc_milestone, set_uc_milestone_batch, set_uc_satellite,
# get_milestone_status, rebalance_milestones, get_satellite_queue,
# sync_multirepo_state, get_cross_repo_dependencies)
register_milestone_management_tools(mcp)

# Register Tier 3 board operation tools (v5.23.0 — 5 tools:
# validate_ac_quality, set_ac_metadata, link_uc_parent, delete_uc,
# get_board_diff)
register_board_operations_tools(mcp)

# Register Tier 4 acceptance automation tools (v5.23.0 — 3 tools:
# bulk_update_hours_from_description, estimate_from_ac,
# milestone_acceptance_check)
register_acceptance_automation_tools(mcp)

# Register migration tools (5 tools: migrate_preview, migrate_project, migrate_status, set_migration_target, switch_backend)
register_migration_tools(mcp)

# Register sync tools (2 tools: get_implementation_status, write_implementation_status)
register_sync_tools(mcp, ENGINE_PATH)

# Register acceptance tools (2 tools: run_acceptance_check, get_acceptance_report)
register_acceptance_tools(mcp, ENGINE_PATH, STATE_PATH)

# Register benchmark tools (1 tool: generate_benchmark_snapshot)
register_benchmark_tools(mcp, ENGINE_PATH, STATE_PATH)

# Register hint tools (3 tools: get_skill_hint, record_skill_hint, list_skill_hints)
register_hint_tools(mcp)

# Register skill registry tools (3 tools: list_skills_v2, discover_skills, validate_skill_manifest)
register_skill_registry_tools(mcp, ENGINE_PATH)

# Register live state tools (4 tools: get_project_live_state, get_all_projects_overview, get_active_sessions, refresh_project_state)
register_live_state_tools(mcp, STATE_PATH)

# Register heartbeat stats tools (1 tool: get_heartbeat_stats)
register_heartbeat_stats_tools(mcp, STATE_PATH)

# Register Stitch proxy tools (13 tools: stitch_set_api_key, stitch_create_project,
# stitch_list_projects, stitch_get_project, stitch_list_screens, stitch_get_screen,
# stitch_fetch_screen_code, stitch_fetch_screen_image, stitch_generate_screen,
# stitch_edit_screen, stitch_generate_variants, stitch_extract_design_context,
# stitch_build_site)
register_stitch_tools(mcp, STATE_PATH)

# Register Quality Audit tools (3 tools: run_quality_audit, attach_audit_evidence, get_last_audit)
# ISO/IEC 25010 (SQuaRE) v1 — on-demand audit with 8 characteristic analyzers,
# ReportLab PDF (embed.build brand) + JSON schema v1.0, persisted under evidence/audits/.
register_audit_tools(mcp, ENGINE_PATH, STATE_PATH)

# Dashboard REST API + static files (La Sala de Máquinas)
register_dashboard_routes(mcp, ENGINE_PATH, STATE_PATH)


def main():
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    port = int(os.getenv("MCP_PORT", "8000"))
    host = os.getenv("MCP_HOST", "0.0.0.0")

    logger = structlog.get_logger(__name__)
    logger.info("server_starting", transport=transport, host=host, port=port, version="5.22.2")

    uvicorn_opts = {"timeout_graceful_shutdown": 5}

    if transport in ("http", "streamable-http"):
        mcp.run(transport="streamable-http", host=host, port=port, uvicorn_config=uvicorn_opts)
    elif transport == "sse":
        mcp.run(transport="sse", host=host, port=port, uvicorn_config=uvicorn_opts)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
