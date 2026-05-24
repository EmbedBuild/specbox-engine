#!/usr/bin/env node
/**
 * pre-prd-discovery-check.mjs — PreToolUse hook for /prd invocation (v6.0.0, UC-D003).
 *
 * Verifies that a Discovery artifact (`doc/discovery/<feature>/icp_jtbd.md`)
 * exists and has verdict READY_FOR_PRD before allowing /prd to proceed.
 *
 * Gate modes (`.claude/settings.local.json` → `specbox.discovery.gate_mode`):
 *   - "off"   (default in upgraded projects): hook is a no-op.
 *   - "warn"  (default in fresh-clone v6.0): prints pedagogical warning,
 *             exits 0, /prd proceeds.
 *   - "block" (opt-in for power users): prints same warning, exits 1,
 *             /prd is aborted.
 *
 * How the hook resolves feature_name from the /prd invocation:
 *   - Reads the CommandInput from stdin (PreToolUse contract).
 *   - Looks for the first positional argument after "/prd" → feature_name.
 *   - If feature_name is a US/UC identifier (US-XX, UC-XXX), skip the
 *     check (Trello/Plane spec-driven mode doesn't use Discovery).
 *
 * Skipped when:
 *   - gate_mode == "off"
 *   - feature_name cannot be extracted
 *   - The skill being invoked is not /prd
 *
 * Telemetry: every block writes a JSONL entry to
 * `.quality/discovery_gate_events.jsonl`.
 */

import { existsSync, readFileSync } from 'fs';
import { spawnSync } from 'child_process';
import { appendLine, readJsonFile } from './lib/utils.mjs';
import { printWarning } from './lib/output.mjs';

const TELEMETRY_PATH = '.quality/discovery_gate_events.jsonl';

function printError(message) {
  process.stderr.write(`\nERROR: ${message}\n`);
}

function readGateMode() {
  const settings = readJsonFile('.claude/settings.local.json') || {};
  const mode = settings?.specbox?.discovery?.gate_mode;
  if (mode === 'off' || mode === 'warn' || mode === 'block') return mode;
  return 'off'; // safe default for projects without explicit config
}

function readHookInput() {
  // Hooks receive a JSON payload on stdin describing the tool call.
  // For PreToolUse on Skill invocation, the payload includes `tool_input`
  // with the args. Format may vary across Claude Code versions — defensive.
  if (process.stdin.isTTY) return null;
  try {
    const raw = readFileSync(0, 'utf-8');
    if (!raw.trim()) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

/**
 * Extract feature_name from a /prd invocation.
 *
 * Heuristic: looks for the first space-separated token after `/prd`
 * that doesn't look like a flag. Returns null if not extractable.
 * Returns a special marker "SPEC_DRIVEN" if the argument is a US/UC id
 * (the hook skips Discovery check for spec-driven mode).
 */
function extractFeatureName(input) {
  if (!input) return null;
  // Try several places: tool_input.command, tool_input.args, top-level args
  const ti = input?.tool_input || input?.toolInput || input?.input || {};
  const candidates = [
    ti.command,
    ti.args,
    ti.prompt,
    ti.text,
    input.command,
    input.args,
  ].filter(Boolean);

  for (const c of candidates) {
    const text = typeof c === 'string' ? c : Array.isArray(c) ? c.join(' ') : '';
    if (!text) continue;

    // Strip leading "/prd "
    const trimmed = text.replace(/^\/prd\s+/, '').trim();
    if (!trimmed) continue;

    // First non-flag token
    const tokens = trimmed.split(/\s+/).filter((t) => !t.startsWith('-'));
    if (tokens.length === 0) continue;
    const firstArg = tokens[0];

    // Spec-driven mode: US-XX or UC-XXX or board:ID → skip Discovery check
    if (/^US-[A-Z0-9-]+$/i.test(firstArg)) return 'SPEC_DRIVEN';
    if (/^UC-[A-Z0-9-]+$/i.test(firstArg)) return 'SPEC_DRIVEN';
    if (/^board:/i.test(firstArg)) return 'SPEC_DRIVEN';

    // Slug-friendly feature name
    if (/^[a-zA-Z0-9_-]+$/.test(firstArg)) return firstArg;
  }

  return null;
}

function recordEvent(entry) {
  try {
    appendLine(TELEMETRY_PATH, JSON.stringify(entry));
  } catch {
    // telemetry must never break the hook
  }
}

/**
 * Run `python3 -c "from server.tools.discovery import _validate_icp_jtbd; ..."`
 * to validate completeness without needing FastMCP running. Falls back to
 * a regex check if the Python invocation fails.
 */
function validateDiscoveryViaPython(featureName) {
  const code = `
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from server.tools.discovery import _validate_icp_jtbd, _icp_jtbd_path
artifact = _icp_jtbd_path(Path('.'), '${featureName}')
if not artifact.exists():
    print(json.dumps({"verdict": "DISCOVERY_INCOMPLETE", "missing": ["artifact_not_found"]}))
    sys.exit(0)
content = artifact.read_text(encoding='utf-8')
result = _validate_icp_jtbd(content)
print(json.dumps(result))
`;
  const py = spawnSync('python3', ['-c', code], { timeout: 5000, encoding: 'utf-8' });
  if (py.status !== 0 || !py.stdout) {
    return { verdict: 'UNKNOWN', missing: ['validation_subprocess_failed'] };
  }
  try {
    return JSON.parse(py.stdout.trim().split('\n').pop());
  } catch {
    return { verdict: 'UNKNOWN', missing: ['validation_parse_failed'] };
  }
}

function fallbackArtifactExists(featureName) {
  return existsSync(`doc/discovery/${featureName}/icp_jtbd.md`);
}

// ─── Main ────────────────────────────────────────────────────────────

const gateMode = readGateMode();
if (gateMode === 'off') {
  process.exit(0);
}

const input = readHookInput();
const featureName = extractFeatureName(input);

if (!featureName) {
  // Couldn't determine the feature_name — don't block.
  process.exit(0);
}

if (featureName === 'SPEC_DRIVEN') {
  // /prd US-XX or /prd UC-XXX — Trello/Plane spec-driven mode, no Discovery needed.
  process.exit(0);
}

// Validate Discovery
let validation;
try {
  validation = validateDiscoveryViaPython(featureName);
} catch {
  validation = { verdict: 'UNKNOWN', missing: ['validation_threw'] };
}

if (validation.verdict === 'READY_FOR_PRD') {
  process.exit(0); // happy path — Discovery complete
}

if (validation.verdict === 'UNKNOWN') {
  // Validation couldn't run (Python missing, etc.). Fall back to existence
  // check — if the artifact exists, give benefit of the doubt.
  if (fallbackArtifactExists(featureName)) {
    process.exit(0);
  }
  // Otherwise still treat as incomplete and let the gate decide.
  validation = { verdict: 'DISCOVERY_INCOMPLETE', missing: ['artifact_not_found'] };
}

// Build pedagogical message
const missingList = (validation.missing || []).map((m) => `- ${m}`).join('\n');
const message =
  `[DISCOVERY-GATE] /prd ${featureName} ${gateMode === 'block' ? 'BLOCKED' : 'WARNED'}: ` +
  `discovery incompleto.\n\n` +
  `Razones:\n${missingList || '  (sin detalles)'}\n\n` +
  `¿Por qué este check importa?\n` +
  `  Sin discovery, los AC del PRD nacen sin justificación trazable.\n` +
  `  3 de cada 4 features sin discovery requieren ≥2 iteraciones post-shipping.\n\n` +
  `Atajo (15-30 min):\n` +
  `  /discovery ${featureName}\n\n` +
  `O salta este check (registrado para review post-shipping):\n` +
  `  /prd ${featureName} --skip-discovery --reason "..."`;

recordEvent({
  type: 'discovery_gate',
  feature_name: featureName,
  gate_mode: gateMode,
  verdict: validation.verdict,
  missing: validation.missing || [],
  action: gateMode === 'block' ? 'blocked' : 'warned',
  detected_at: new Date().toISOString(),
});

if (gateMode === 'block') {
  printError(message);
  process.exit(1);
}

printWarning(
  `${message}\n\n(Warning mode — gate_mode=warn. Set ` +
    `specbox.discovery.gate_mode="block" in .claude/settings.local.json to ` +
    `block /prd when Discovery is incomplete.)`
);
process.exit(0);
