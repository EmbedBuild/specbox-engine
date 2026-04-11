## Configure MCP Servers

MCP (Model Context Protocol) servers give Claude Code access to external tools.

### SpecBox MCP Server
110 tools for spec-driven development:
- Query plans, track features, manage quality baselines
- Trello/Plane/FreeForm integration for US/UC/AC tracking
- Session telemetry, healing events, evidence pipeline
- Stitch proxy for UI design generation

### Engram Memory Server
Persistent memory that survives context compaction:
- Saves decisions, conventions, and discoveries
- Recalls prior work across sessions
- Reduces token waste from repeated context

Both servers are configured in `~/.claude/settings.local.json` and activated automatically when Claude Code starts.

Click **Configure MCP** to set up both servers.
