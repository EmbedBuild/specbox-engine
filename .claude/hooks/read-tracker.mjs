#!/usr/bin/env node
/**
 * read-tracker.mjs — PostToolUse hook for the Read tool
 * NON-BLOCKING, silent: records which files the agent has read in the current session, in
 * .quality/read_tracker.jsonl. quality-first-guard.mjs uses it to enforce "read before write".
 *
 * v5.15.0 — Quality First Enforcement · US-93/UC-9302: reads the path from tool_input (it read
 * the top level, so it never recorded a real read) and keeps the tracker out of git with a
 * .quality/.gitignore entry.
 */

import { readHookInput, fileExists, fileAge, mkdir, appendLine } from './lib/utils.mjs';
import { unlinkSync, writeFileSync } from 'fs';

const { toolInput } = readHookInput();
const filePath = String(toolInput.file_path || '');
if (!filePath) process.exit(0);

mkdir('.quality');
const TRACKER_FILE = '.quality/read_tracker.jsonl';

// The tracker is per machine and session: never in git.
if (!fileExists('.quality/.gitignore')) {
  try { writeFileSync('.quality/.gitignore', 'read_tracker.jsonl\n'); } catch { /* read-only: ignore */ }
}

// Clear stale tracker (older than 24 hours)
if (fileExists(TRACKER_FILE) && fileAge(TRACKER_FILE) > 86400) {
  try { unlinkSync(TRACKER_FILE); } catch { /* ignore */ }
}

appendLine(TRACKER_FILE, JSON.stringify({ file: filePath, ts: Math.floor(Date.now() / 1000) }));
process.exit(0);
