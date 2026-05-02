#!/usr/bin/env node
/**
 * session-start.mjs — SessionStart hook: injects continuity context into the new session.
 *
 * Reads, in order of priority:
 *   1. .quality/handoff.md (if fresh) — full content, capped at MAX_CHARS
 *   2. .quality/active_uc.json — UC en progreso
 *   3. doc/app/app_spec.md — auto-zones (tracking_backend, autopilot)
 *   4. .quality/evidence/<feature>/checkpoint.json — last phase
 *
 * Output: JSON to stdout with hookSpecificOutput.additionalContext
 * If nothing relevant exists, exits silently (no context injection).
 */

import { readFileSync, statSync, existsSync } from 'fs';
import { findFiles, readJsonFile, fileExists } from './lib/utils.mjs';

const HANDOFF_PATH = '.quality/handoff.md';
const APP_SPEC_PATH = 'doc/app/app_spec.md';
const ACTIVE_UC_PATH = '.quality/active_uc.json';
const MAX_CHARS = 14000;
const STALE_TTL_MIN = 1440;

function fileAgeMinutes(path) {
  if (!existsSync(path)) return Infinity;
  try {
    return (Date.now() - statSync(path).mtimeMs) / 60000;
  } catch {
    return Infinity;
  }
}

function readHandoff() {
  if (!fileExists(HANDOFF_PATH)) return null;
  try {
    const content = readFileSync(HANDOFF_PATH, 'utf-8');
    const ageMin = fileAgeMinutes(HANDOFF_PATH);
    const stale = ageMin > STALE_TTL_MIN;
    return { content, ageMin: Math.round(ageMin), stale };
  } catch {
    return null;
  }
}

function readActiveUC() {
  const data = readJsonFile(ACTIVE_UC_PATH);
  if (!data) return null;
  return {
    uc_id: data.uc_id || data.feature || 'unknown',
    started_at: data.started_at || null,
  };
}

function readLatestCheckpoint() {
  const files = findFiles('.quality/evidence', /^checkpoint\.json$/);
  if (files.length === 0) return null;
  let latest = null;
  let latestMtime = 0;
  for (const f of files) {
    try {
      const m = statSync(f).mtimeMs;
      if (m > latestMtime) { latestMtime = m; latest = f; }
    } catch { /* ignore */ }
  }
  return latest ? readJsonFile(latest) : null;
}

function extractAutoZones(specPath) {
  if (!fileExists(specPath)) return null;
  let content;
  try {
    content = readFileSync(specPath, 'utf-8');
  } catch {
    return null;
  }
  const zones = {};
  const zoneRegex = /<!--\s*@specbox:zone start kind="auto" id="([^"]+)"\s*-->([\s\S]*?)<!--\s*@specbox:zone end\s*-->/g;
  let match;
  while ((match = zoneRegex.exec(content)) !== null) {
    const id = match[1];
    if (id === 'tracking_backend' || id === 'autopilot' || id === 'stack') {
      zones[id] = match[2].trim();
    }
  }
  return Object.keys(zones).length > 0 ? zones : null;
}

function buildContext() {
  const parts = [];

  const handoff = readHandoff();
  if (handoff) {
    const tag = handoff.stale ? '[STALE]' : '[FRESH]';
    parts.push(`## SpecBox Handoff ${tag} (age: ${handoff.ageMin}min)\n\nFrom previous session — ${handoff.stale ? 'WARNING: older than 24h, may be outdated.' : 'this is the recovered state.'}\n\n${handoff.content}`);
  }

  if (!handoff || handoff.stale) {
    const activeUC = readActiveUC();
    const checkpoint = readLatestCheckpoint();
    if (activeUC || checkpoint) {
      const lines = ['## SpecBox Live State (no fresh handoff)'];
      if (activeUC) {
        lines.push(`- Active UC: **${activeUC.uc_id}**${activeUC.started_at ? ` (started ${activeUC.started_at})` : ''}`);
      }
      if (checkpoint) {
        lines.push(`- Last checkpoint: feature=${checkpoint.feature}, phase=${checkpoint.phase} (${checkpoint.phase_name}), branch=${checkpoint.branch}, status=${checkpoint.status}`);
      }
      lines.push('');
      lines.push('Consider running `/handoff` to restore richer context, or check `git log` and `.quality/evidence/` for state.');
      parts.push(lines.join('\n'));
    }
  }

  const zones = extractAutoZones(APP_SPEC_PATH);
  if (zones) {
    const lines = ['## SpecBox Canonical (from doc/app/app_spec.md)'];
    if (zones.stack) lines.push(`### Stack\n${zones.stack}`);
    if (zones.tracking_backend) lines.push(`### Tracking backend\n${zones.tracking_backend}`);
    if (zones.autopilot) lines.push(`### Autopilot\n${zones.autopilot}`);
    parts.push(lines.join('\n\n'));
  }

  if (parts.length === 0) return null;

  let combined = parts.join('\n\n---\n\n');
  if (combined.length > MAX_CHARS) {
    combined = combined.slice(0, MAX_CHARS - 100) + '\n\n_(truncated by session-start hook to fit budget)_\n';
  }
  return combined;
}

function main() {
  const ctx = buildContext();
  if (!ctx) {
    process.exit(0);
  }
  const out = {
    hookSpecificOutput: {
      hookEventName: 'SessionStart',
      additionalContext: ctx,
    },
  };
  process.stdout.write(JSON.stringify(out));
  process.exit(0);
}

try {
  main();
} catch (e) {
  console.error(`[session-start] error: ${e.message}`);
  process.exit(0);
}
