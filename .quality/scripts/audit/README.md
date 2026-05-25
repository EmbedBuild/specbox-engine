# .quality/scripts/audit/ — Client-side ISO/IEC 25010 analyzers

Reserved location for the 8 SQuaRE analyzers that the `/audit` skill runs
on the client repo to build a `QualityReport` it then submits to the MCP
via `submit_quality_audit(project, report)`.

## Background — v6.0.1 MCP Path Contract

Before v6.0.1, the audit tools lived inside the MCP server
(`server/audit/analyzers/`). The server ran them against the client repo
when invoked, which is broken in remote MCP setups: the analyzers scan
`project_path` as a server-side filesystem path, so they read the MCP
host (typically the VPS), not the user's repo.

v6.0.1 moves the responsibility to the client:

1. The `/audit` skill detects the project stack.
2. The skill executes the appropriate analyzer scripts from this directory
   (one Python module per SQuaRE characteristic), each producing a JSON
   fragment compliant with `server/audit/schema.py`.
3. The skill merges the fragments into a single `QualityReport` dict.
4. The skill calls `mcp__SpecBox-MCP__submit_quality_audit(project, report)`,
   which validates the dict, tags audit-tool availability, and returns the
   canonical report ready for `attach_audit_evidence`.

## Status (v6.0.1)

The directory is provisioned and the MCP contract is in place
(`submit_quality_audit` accepts the report). The actual analyzer scripts
are **not yet ported** — `/audit` continues to call the legacy
`run_quality_audit`, which now returns a deprecation error pointing to
this README. Porting the 8 analyzers is tracked as out-of-scope for v6.0.1
and scheduled for v6.0.2.

## Layout (planned)

```
.quality/scripts/audit/
├── README.md                         (this file)
├── run-audit.sh                      (top-level orchestrator the skill invokes)
├── analyzers/
│   ├── functional_suitability.py
│   ├── performance_efficiency.py
│   ├── compatibility.py
│   ├── usability.py
│   ├── reliability.py
│   ├── security.py
│   ├── maintainability.py
│   └── portability.py
└── lib/
    ├── schema.py                     (mirrors server/audit/schema.py)
    └── tool_runner.py                (subprocess wrapper for semgrep, etc.)
```
