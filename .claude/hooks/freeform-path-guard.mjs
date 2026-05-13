#!/usr/bin/env node
/**
 * freeform-path-guard.mjs — PreToolUse hook (v5.33.0)
 *
 * Intercepts MCP tool calls that configure or onboard a FreeForm backend
 * (`mcp__SpecBox-MCP__set_auth_token`, `mcp__SpecBox-MCP__onboard_project`)
 * and ensures the FreeForm root path reaching the MCP server is ALWAYS
 * an absolute path on the client filesystem.
 *
 * Why: when the MCP server runs remotely (env SPECBOX_ENGINE_MCP_URL set),
 * a relative path like "doc/tracking" is resolved against the server CWD,
 * not the client repo — so the tracking folder gets created on the VPS
 * instead of the developer's laptop. Server-side guards already reject
 * this with FREEFORM_PATH_MUST_BE_ABSOLUTE, but that surfaces as an error
 * the user has to fix by hand. This hook auto-rewrites the input so the
 * call just works.
 *
 * Behavior:
 *   - If tool is not one of the watched MCP tools          → exit 0 (no-op).
 *   - If backend_type != "freeform"                         → exit 0 (no-op).
 *   - If path is already absolute                           → exit 0 (no-op).
 *   - If path is relative and we can resolve git toplevel   → rewrite to
 *     absolute via hookSpecificOutput.updatedInput, exit 0.
 *   - If path is relative but CWD is not a git repo         → exit 2
 *     (block with a clear error) — auto-resolution would be ambiguous.
 *
 * Logs every rewrite to .quality/logs/freeform-path-rewrites.jsonl so the
 * behavior is auditable.
 */

import { isAbsolute } from 'path';
import { resolveFreeformPath, isRemoteMcp } from './lib/freeform-path.mjs';
import { readStdin, appendLine, now } from './lib/utils.mjs';

const WATCHED_TOOLS = new Set([
  'mcp__SpecBox-MCP__set_auth_token',
  'mcp__SpecBox-MCP__onboard_project',
]);

// Map of tool → which argument name carries the FreeForm root.
const ROOT_ARG_BY_TOOL = {
  'mcp__SpecBox-MCP__set_auth_token': 'root_path',
  'mcp__SpecBox-MCP__onboard_project': 'freeform_root_absolute',
};

const DEFAULT_ROOT = 'doc/tracking';
const LOG_PATH = '.quality/logs/freeform-path-rewrites.jsonl';

const raw = readStdin();
let payload = {};
try {
  payload = JSON.parse(raw);
} catch {
  process.exit(0);
}

const toolName = payload?.tool_name || payload?.toolName || '';
if (!WATCHED_TOOLS.has(toolName)) {
  process.exit(0);
}

const toolInput = payload?.tool_input ?? payload?.toolInput ?? {};
const backendType = (toolInput?.backend_type || '').toString().trim();

// onboard_project defaults to "freeform" when backend_type is empty AND
// trello_board_name is empty. Mirror that so the hook covers the implicit
// default case too.
const trelloBoardName = (toolInput?.trello_board_name || '').toString().trim();
const effectiveBackend = backendType
  || (toolName === 'mcp__SpecBox-MCP__onboard_project' && !trelloBoardName ? 'freeform' : '');

if (effectiveBackend !== 'freeform') {
  process.exit(0);
}

const argName = ROOT_ARG_BY_TOOL[toolName];
const rawRoot = (toolInput?.[argName] || '').toString().trim();

// If no value provided, fall back to the canonical default before resolving.
// This covers set_auth_token() with no root_path: server default is the
// relative string "doc/tracking", which would hit the same bug.
const effectiveRoot = rawRoot || DEFAULT_ROOT;

if (isAbsolute(effectiveRoot)) {
  // Nothing to do — already safe.
  process.exit(0);
}

// Relative path. Try to resolve from git toplevel.
let absolute;
try {
  absolute = resolveFreeformPath(effectiveRoot);
} catch (err) {
  // Cannot determine repo root. Block with an actionable message.
  console.error(
    '[freeform-path-guard] BLOCKED — FreeForm backend received a relative '
    + `root path (${JSON.stringify(effectiveRoot)}) and the hook could not `
    + 'resolve it: ' + err.message + ' '
    + 'Pass an absolute path explicitly, or invoke this tool from inside a '
    + 'git repository so the hook can compute the project root for you.'
  );
  process.exit(2);
}

// Successful rewrite. Log and return updatedInput.
try {
  appendLine(LOG_PATH, JSON.stringify({
    ts: now(),
    tool: toolName,
    arg: argName,
    from: effectiveRoot,
    to: absolute,
    is_remote_mcp: isRemoteMcp(),
    reason: rawRoot ? 'relative_path' : 'unspecified_default',
  }));
} catch {
  // Logging failures must never block the user.
}

const updatedInput = { ...toolInput, [argName]: absolute };

// When set_auth_token is called without backend_type, the server defaults
// to "trello", so we only stamp backend_type when the caller explicitly
// said "freeform" or the onboard_project implicit-freeform path applied.
if (!toolInput?.backend_type && toolName === 'mcp__SpecBox-MCP__onboard_project') {
  updatedInput.backend_type = 'freeform';
}

process.stdout.write(JSON.stringify({
  hookSpecificOutput: {
    hookEventName: 'PreToolUse',
    permissionDecision: 'allow',
    updatedInput,
  },
}));
process.exit(0);
