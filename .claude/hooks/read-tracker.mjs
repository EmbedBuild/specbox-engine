#!/usr/bin/env node
/**
 * read-tracker.mjs — PostToolUse hook for Read tool
 * NON-BLOCKING: Records which files the agent has read in the current session.
 * Used by quality-first-guard.mjs to enforce "read before write."
 *
 * v5.15.0 — Quality First Enforcement
 */

import { readStdin, fileExists, fileAge, mkdir, appendLine } from './lib/utils.mjs';
import { unlinkSync } from 'fs';

const input = readStdin();

// Extract file path
let filePath = '';
try {
  const parsed = JSON.parse(input);
  filePath = parsed.file_path || '';
} catch {
  const match = input.match(/"file_path"\s*:\s*"([^"]*)"/);
  filePath = match ? match[1] : '';
}

if (!filePath) {
  process.exit(0);
}

// Ensure .quality directory exists
mkdir('.quality');

const TRACKER_FILE = '.quality/read_tracker.jsonl';

// Clear stale tracker (older than 24 hours)
if (fileExists(TRACKER_FILE)) {
  const age = fileAge(TRACKER_FILE);
  if (age > 86400) {
    try { unlinkSync(TRACKER_FILE); } catch { /* ignore */ }
  }
}

// Append the read event (use JSON.stringify to escape special chars in file paths)
const timestamp = Math.floor(Date.now() / 1000);
appendLine(TRACKER_FILE, JSON.stringify({ file: filePath, ts: timestamp }));

process.exit(0);
