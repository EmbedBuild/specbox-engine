# .quality/scripts/audit/ — Client-side ISO/IEC 25010 analyzers

The 8 SQuaRE analyzers that the `/audit` skill runs on the **client repo** to
build a `QualityReport`, which it then submits to the MCP via
`submit_quality_audit(project, report)`. The server validates the report,
re-tags audit-tool availability, and (in `attach_audit_evidence`) renders the
PDF + JSON evidence.

## Background — v6.0.1 MCP Path Contract

Before v6.0.1 the analyzers lived inside the MCP server
(`server/audit/analyzers/`). The server ran them against `project_path`, which
is broken in remote MCP setups: that path resolves on the MCP host (the VPS),
not the user's machine, so the audit scanned the wrong filesystem.

v6.0.1 moved the responsibility to the client and added the content-passing
`submit_quality_audit(project, report)` tool. **UC-663 (v6.0.2)** completed the
port: the 8 analyzers are now Node `.mjs` (no Python on the client — consistent
with v6.7.0 zero-Python onboarding) and live here.

## Flow

1. `/audit` detects the project stack locally and calls
   `check_audit_tools_status(stack)` to report which optional external tools
   are present.
2. It runs the orchestrator:

   ```bash
   node .quality/scripts/audit/run-audit.mjs --project <name> --stack <stack> [--scope <char>]
   ```

   which prints the full `QualityReport` JSON to stdout (8 `CharacteristicResult`
   blocks in canonical SQuaRE order + `global_score` + `tools_used` + `audit_id`).
3. The skill submits that JSON with
   `submit_quality_audit(project, report=<dict>)` (server validates via
   `QualityReport.from_dict`).
4. AG-10 enriches justifications/recommendations, then
   `attach_audit_evidence(project, report)` persists PDF + JSON.

## Layout

```
.quality/scripts/audit/
├── README.md                         (this file)
├── run-audit.mjs                     (orchestrator + CLI; exports buildReport)
├── run-audit.test.mjs                (node:test — AC-01 + AC-03 + scoring/signals)
├── analyzers/
│   ├── functional_suitability.mjs
│   ├── performance_efficiency.mjs
│   ├── compatibility.mjs
│   ├── usability.mjs
│   ├── reliability.mjs
│   ├── security.mjs                  (semgrep/gitleaks/pip-audit/npm/checkov)
│   ├── maintainability.mjs           (60/40 mix; emits breakdown)
│   └── portability.mjs
└── lib/
    ├── schema.mjs                    (mirrors server/audit/schema.py shapes)
    ├── scoring.mjs                   (mirrors server/audit/scoring.py — numerically identical)
    ├── fs-scan.mjs                   (pruned filesystem walk + helpers)
    ├── tool-runner.mjs               (optional external tool subprocess wrapper)
    └── signals.mjs                   (SpecBox signals from local doc/tracking + .quality)
```

## Design split (client vs server)

- **Client (here)**: scan the filesystem, run optional external tools, compute
  per-characteristic + global scores. This is exactly the part that broke in
  remote MCP (filesystem access), so it has to be client-side.
- **Server**: validate the submitted report, render the branded PDF (ReportLab),
  persist evidence, update `project_meta.last_audit`. No access to the client
  filesystem required.

Scoring lives on both sides intentionally: `lib/scoring.mjs` mirrors
`server/audit/scoring.py` so a report is complete before submission, and the
server re-derives nothing it isn't given.

## External tools (all optional)

`semgrep`, `gitleaks`, `pip-audit`, `npm`, `lizard`, `jscpd`, `checkov`. Missing
binaries are reported in `tools_used` with `status:"missing"` and never abort
the audit (graceful degradation).

## Tests

```bash
node --test ".quality/scripts/audit/**/*.test.mjs"
```

Zero-dependency `node:test`. Covers AC-01 (each analyzer emits a schema-valid
block), AC-03 (orchestrator merges 8 in order, `--scope`, robustness),
scoring parity with `scoring.py`, local-FS signal extraction, and a
concurrency regression for the portability path-scan regex.
```
