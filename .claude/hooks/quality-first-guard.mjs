#!/usr/bin/env node
/**
 * quality-first-guard.mjs — PreToolUse hook for Write and Edit tools
 * BLOCKING (exit 2, before the write): modifying an existing file the agent has not read in this
 * session. A file the agent creates counts as known, so it can edit it afterwards.
 * US-93/UC-9302: it read the path from the top level (so it never checked a real write) and
 * exited 1, which does not block.
 *
 * Philosophy: the LLM brings the speed; SpecBox brings the control and guarantees
 * the quality (UC-7006: the block message no longer says the opposite).
 * The #1 cause of wasted tokens and technical debt is modifying code without
 * understanding what's already there. This hook enforces "read before write."
 *
 * v5.15.0 — Quality First Enforcement
 */

import { readHookInput, fileExists, appendLine, mkdir } from './lib/utils.mjs';
import { blockWith } from './lib/output.mjs';
import { readFileSync, realpathSync } from 'fs';
import { resolve } from 'path';

const { toolInput } = readHookInput();
const filePath = String(toolInput.file_path || '');
if (!filePath) process.exit(0);

const TRACKER_FILE = '.quality/read_tracker.jsonl';

// A new file: the agent is writing it, so from now on it knows it.
if (!fileExists(filePath)) {
  try {
    mkdir('.quality');
    appendLine(TRACKER_FILE, JSON.stringify({ file: filePath, ts: Math.floor(Date.now() / 1000), created: true }));
  } catch { /* no .quality: nothing to record */ }
  process.exit(0);
}

// Files that do not need read-before-write: generated, lock files, build output, SpecBox internals.
if (/(\.g\.dart$|\.freezed\.dart$|\.lock$|package-lock\.json$|pubspec\.lock$|poetry\.lock$|\.min\.js$|\.min\.css$|node_modules\/|\.dart_tool\/|(^|\/)build\/|(^|\/)dist\/|\.next\/)/.test(filePath)) {
  process.exit(0);
}
if (/(\.quality\/|\.claude\/|results\.json$|baseline\.json$|active_uc\.json$|hint_counters\.json$)/.test(filePath)) {
  process.exit(0);
}

function block(file, inSession) {
  blockWith('QUALITY FIRST: Read before you write', [
    `File: ${file}`,
    '',
    inSession
      ? 'You are trying to modify an existing file without reading it first in this session.'
      : 'You are trying to modify an existing file without reading it first.',
    'Reading first avoids breaking what is there, duplicating it or leaving it inconsistent.',
    '',
    'To proceed:',
    `  1. Use the Read tool to read '${file}'`,
    '  2. Understand the existing code',
    '  3. Then make your changes',
  ]);
}

let tracker = '';
try {
  tracker = readFileSync(TRACKER_FILE, 'utf-8');
} catch {
  block(filePath, false);
}

// The same file, whatever the spelling: resolved against the cwd and through symlinks (on macOS
// /tmp is /private/tmp). No more matching by basename: any README.md read anywhere counted.
const canonical = (p) => {
  const abs = resolve(process.cwd(), p);
  try { return realpathSync(abs); } catch { return abs; }
};
const target = canonical(filePath);
const wasRead = tracker.split('\n').some((line) => {
  try {
    const entry = JSON.parse(line);
    return entry.file && canonical(entry.file) === target;
  } catch {
    return false;
  }
});

if (!wasRead) block(filePath, true);
process.exit(0);
