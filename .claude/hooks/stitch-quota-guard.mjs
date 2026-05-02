#!/usr/bin/env node
/**
 * stitch-quota-guard.mjs — PreToolUse hook (v5.31.0)
 *
 * Reads the cached quota state at .quality/stitch_quota.json (written
 * by the get_stitch_quota_status MCP tool) and surfaces a warning
 * before a Stitch generation tool is invoked when consumption is high.
 *
 * Default behaviour:
 *   - Consumption ≥ 80%  → emit a stderr warning, do NOT block.
 *   - Consumption ≥ 100% → block IF flash_safety_net is disabled in
 *     project settings (specbox.stitch.fallback.flash_safety_net).
 *     Otherwise still warn but allow — the v2 generation tool will
 *     route the call through Flash.
 *
 * The cache is read-only here; if the user never ran the quota tool,
 * the hook is a no-op.
 */

import { existsSync, readFileSync } from 'fs';
import { join } from 'path';
import { readStdin } from './lib/utils.mjs';

const STITCH_TOOL_NAMES = new Set([
  'mcp__SpecBox-MCP__stitch_generate_screen',
  'mcp__SpecBox-MCP__stitch_generate_screen_v2',
  'mcp__SpecBox-MCP__stitch_edit_screen',
  'mcp__SpecBox-MCP__stitch_edit_screens',
  'mcp__SpecBox-MCP__stitch_generate_variants',
  'mcp__SpecBox-MCP__stitch_build_site',
  'mcp__SpecBox-MCP__stitch_build_site_batched_v2',
]);

const QUOTA_CACHE = '.quality/stitch_quota.json';
const SETTINGS_PATH = '.claude/settings.local.json';

// Read the harness payload — PreToolUse passes a JSON object on stdin.
const raw = readStdin();
let payload = {};
try { payload = JSON.parse(raw); } catch { /* ignore */ }

const toolName = payload?.tool_name || payload?.toolName || '';
if (!STITCH_TOOL_NAMES.has(toolName)) {
  process.exit(0);
}

if (!existsSync(QUOTA_CACHE)) {
  process.exit(0);
}

let quota;
try {
  quota = JSON.parse(readFileSync(QUOTA_CACHE, 'utf-8'));
} catch {
  process.exit(0);
}

const expPct = Number(quota?.experimental?.percent ?? 0);
const stdPct = Number(quota?.standard?.percent ?? 0);

// Detect whether the project has opted into Flash safety net.
let flashSafetyNet = false;
try {
  if (existsSync(SETTINGS_PATH)) {
    const settings = JSON.parse(readFileSync(SETTINGS_PATH, 'utf-8'));
    flashSafetyNet =
      settings?.specbox?.stitch?.fallback?.flash_safety_net === true;
  }
} catch { /* ignore */ }

// Hard limit reached on PRO and no safety net → block.
if (expPct >= 100 && !flashSafetyNet) {
  console.error(
    '[stitch-quota-guard] BLOCKED — PRO (Experimental) quota exhausted ' +
      'this month and flash_safety_net is OFF. Either enable it in ' +
      '.claude/settings.local.json under specbox.stitch.fallback or wait ' +
      `until the reset (${quota.reset_at || 'next month'}).`
  );
  process.exit(2); // Convention: exit 2 = blocking
}

// Warn at >= 80% on either bucket (do not block).
if (expPct >= 80 || stdPct >= 80) {
  const parts = [];
  if (expPct >= 80) parts.push(`PRO ${expPct}%`);
  if (stdPct >= 80) parts.push(`Flash ${stdPct}%`);
  console.error(
    `[stitch-quota-guard] WARNING — Stitch quota high (${parts.join(', ')}). ` +
      `Reset on ${quota.reset_at || 'next month'}. Consider deferring ` +
      'non-critical generations or enabling flash_safety_net.'
  );
}

process.exit(0);
