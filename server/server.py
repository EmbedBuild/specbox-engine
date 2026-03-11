"""
SDD-JPS Engine MCP Server v4.0.0

Unified MCP endpoint: 73+ tools (engine + spec-driven + telemetry).
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
from .tools.migration import register_migration_tools
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
    "sdd-jps-engine",
    instructions="""
    MCP server for the SDD-JPS Engine v4.0.0 — an agentic programming system for Claude Code.

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

    The engine manages Flutter, React, Python, and Google Apps Script projects
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

# Register engine tools (52 tools)
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

# Register migration tools (5 tools: migrate_preview, migrate_project, migrate_status, set_migration_target, switch_backend)
register_migration_tools(mcp)

# Dashboard REST API + static files (La Sala de Máquinas)
register_dashboard_routes(mcp, ENGINE_PATH, STATE_PATH)


def main():
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    port = int(os.getenv("MCP_PORT", "8000"))
    host = os.getenv("MCP_HOST", "0.0.0.0")

    logger = structlog.get_logger(__name__)
    logger.info("server_starting", transport=transport, host=host, port=port, version="4.0.0")

    uvicorn_opts = {"timeout_graceful_shutdown": 5}

    if transport in ("http", "streamable-http"):
        mcp.run(transport="streamable-http", host=host, port=port, uvicorn_config=uvicorn_opts)
    elif transport == "sse":
        mcp.run(transport="sse", host=host, port=port, uvicorn_config=uvicorn_opts)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
