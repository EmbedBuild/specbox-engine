#!/usr/bin/env node
/**
 * mcp-report.mjs — Hook helper: sends data to remote MCP server (fire-and-forget)
 * Usage: node mcp-report.mjs <tool_name> '<json_arguments>'
 * Requires: SPECBOX_ENGINE_MCP_URL env var
 * If not configured or fails, does nothing (silent).
 *
 * When called as a subprocess, reads tool_name and args from process.argv.
 * Can also be imported as a module for mcpCall().
 */

import { mcpCall } from './lib/http.mjs';

// When run as a script (not imported)
const toolName = process.argv[2] || '';
const toolArgs = process.argv[3] || '{}';

if (toolName) {
  let args;
  try {
    args = JSON.parse(toolArgs);
  } catch {
    args = {};
  }

  mcpCall(toolName, args)
    .catch(() => {})
    .finally(() => process.exit(0));
}
