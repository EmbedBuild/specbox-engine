# Phase Outputs Contract (v5.32.0)

> **File**: `.quality/evidence/{feature_slug}/phase_outputs.jsonl`
> **Format**: JSONL — one JSON object per line, append-only.
> **Owner**: each Task delegated by `/implement` writes one line at the end of its run.
> **Reader**: the orchestrator (Spec-Code Sync, Paso 5.1.1b / 8.5.1a) consumes the file via `aggregate_for_spec_sync`.

## Why

Before v5.32 the orchestrator relied on `git diff` from its own session to know what each phase had changed. That works only as long as every phase ran in the same Claude session — the moment a phase delegates to an isolated Task, those changes happen in a different process and the orchestrator never sees the diff.

`phase_outputs.jsonl` flips the data flow: every Task writes a structured delta as its last action, and the orchestrator reads from disk. The file survives compactations, re-runs, and Tasks that crash mid-flight.

## Schema (v1)

```json
{
  "schema_version": 1,
  "ts": "2026-MM-DDTHH:MM:SSZ",
  "phase": "feature",
  "phase_index": 4,
  "agent": "AG-01",
  "task_id": "uuid-v4",
  "duration_s": 423.5,
  "status": "ok",
  "files_created": ["lib/features/staff/staff_provider.dart"],
  "files_modified": ["lib/main.dart"],
  "files_deleted": [],
  "summary": "Implementé el provider de staff con CRUD básico.",
  "tokens_used_prompt": 14823,
  "tokens_used_response": 3107,
  "healing_attempts": 0,
  "error": null
}
```

### Required fields

- `schema_version` — integer, currently `1`.
- `phase` — short string identifier of the phase (e.g. `db`, `feature`, `qa`).
- `phase_index` — 1-indexed position of the phase in the SKILL.md order.
- `agent` — agent ID (`AG-01` … `AG-09b`) that ran the phase.
- `status` — one of `ok` | `error` | `partial`.

### Optional fields (omit when not applicable)

- `ts` — ISO-8601 UTC. Default: now-at-write.
- `task_id` — UUID for cross-correlation with other telemetry.
- `duration_s` — wall-clock seconds.
- `files_created` / `files_modified` / `files_deleted` — repo-relative paths. Default empty arrays.
- `summary` — human-readable 1-3 sentence summary. Highly recommended.
- `tokens_used_prompt` / `tokens_used_response` — for budget telemetry.
- `healing_attempts` — number of self-healing retries within this phase. Default `0`.
- `error` — string with the human-readable error if `status="error"` or `partial`.

### Forbidden

- Extra fields rejected by the validator (Pydantic `extra="forbid"`). Add a field to the schema rather than smuggling it through.
- Absolute paths in any `files_*` array — repo-relative only. The aggregator does not normalise.

## Examples

### Valid — minimal

```json
{"schema_version":1,"phase":"db","phase_index":1,"agent":"AG-03","status":"ok"}
```

### Valid — full

```json
{
  "schema_version": 1,
  "ts": "2026-05-02T10:30:00Z",
  "phase": "feature",
  "phase_index": 4,
  "agent": "AG-01",
  "task_id": "1f7e9c2a-...",
  "duration_s": 142.3,
  "status": "ok",
  "files_created": ["lib/features/staff/provider.dart", "lib/features/staff/repository.dart"],
  "files_modified": ["lib/main.dart"],
  "files_deleted": [],
  "summary": "Provider + repository for staff CRUD, wired into DI.",
  "tokens_used_prompt": 14823,
  "tokens_used_response": 3107,
  "healing_attempts": 1
}
```

### Invalid — extra field

```json
{"schema_version":1,"phase":"db","phase_index":1,"agent":"AG-03","status":"ok","unexpected":"x"}
```

### Invalid — bad status

```json
{"schema_version":1,"phase":"db","phase_index":1,"agent":"AG-03","status":"???"}
```

(Note: the current Python validator only enforces `extra="forbid"`. The string set for `status` is enforced by the aggregator's switch-case — unknown statuses propagate but show up as `unknown` in `overall_status`.)

## How Spec-Code Sync uses this

`aggregate_for_spec_sync(feature_slug)` collapses every entry into:

```python
SpecSyncAggregate(
    feature_slug=...,
    overall_status="ok" | "partial" | "error" | "empty",
    delta_count=int,                # sum of all files_* across all phases
    files_created=[...],            # deduped first-seen-order
    files_modified=[...],           # deduped first-seen-order
    files_deleted=[...],            # deduped first-seen-order
    phases=[                        # one dict per entry, in file order
        {"phase", "phase_index", "agent", "status",
         "summary", "duration_s", "files_touched", "healing_attempts"}
    ],
    total_duration_s=float,
    total_healing_attempts=int,
)
```

This is what `write_implementation_status` consumes to write the `## Implementation Status` section of the PRD.

## Validation

Run from the repo root:

```
node .quality/scripts/validate-phase-outputs.mjs .quality/evidence/{feature}/phase_outputs.jsonl
```

Exit codes:
- `0` — all lines valid.
- `1` — at least one line invalid; specific line numbers + reasons go to stderr.

## Forward compatibility

If the schema evolves (`schema_version: 2`), the loader will support the union and the aggregator will branch on `schema_version`. Old entries remain readable.
