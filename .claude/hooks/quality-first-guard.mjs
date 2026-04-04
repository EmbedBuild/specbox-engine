#!/usr/bin/env node
/**
 * quality-first-guard.mjs — PreToolUse hook for Write and Edit tools
 * BLOCKING: Prevents modifying existing files without reading them first.
 *
 * Philosophy: SpecBox Engine already provides speed. The LLM's job is QUALITY.
 * The #1 cause of wasted tokens and technical debt is modifying code without
 * understanding what's already there. This hook enforces "read before write."
 *
 * v5.15.0 — Quality First Enforcement
 */

import { readStdin, fileExists, fileAge } from './lib/utils.mjs';
import { readFileSync } from 'fs';
import { basename } from 'path';
import { resolve } from 'path';

const input = readStdin();

// Extract file path from tool input
let filePath = '';
try {
  const parsed = JSON.parse(input);
  filePath = parsed.file_path || '';
} catch {
  // Fallback: regex parse for non-JSON input
  const match = input.match(/"file_path"\s*:\s*"([^"]*)"/);
  filePath = match ? match[1] : '';
}

if (!filePath) {
  process.exit(0);
}

// If the file doesn't exist yet, it's a new file creation — allow
if (!fileExists(filePath)) {
  process.exit(0);
}

// Skip files that don't need read-before-write protection
// Generated files, lock files, config files, docs, etc.
if (/(\\.g\\.dart|\\.freezed\\.dart|\\.lock$|package-lock\\.json|pubspec\\.lock|poetry\\.lock|\\.min\\.js|\\.min\\.css|node_modules\/|\\.dart_tool\/|build\/|dist\/|\\.next\/)/.test(filePath)) {
  process.exit(0);
}

// Skip non-source artifacts that are frequently auto-generated
if (/(\\.quality\/|\\.claude\/|results\\.json|baseline\\.json|active_uc\\.json|hint_counters\\.json)/.test(filePath)) {
  process.exit(0);
}

// --- Check read tracker ---
const TRACKER_FILE = '.quality/read_tracker.jsonl';

function blockWithMessage(file) {
  console.log('');
  console.log('============================================================');
  console.log('  QUALITY FIRST: Read before you write');
  console.log('============================================================');
  console.log(`  File: ${file}`);
  console.log('');
  console.log('  You are trying to modify an existing file without reading');
  console.log('  it first. This is the #1 cause of wasted tokens and');
  console.log('  technical debt.');
  console.log('');
  console.log('  SpecBox provides speed. YOUR job is QUALITY.');
  console.log('');
  console.log('  To proceed:');
  console.log('    1. Use the Read tool to read this file');
  console.log('    2. Understand what\'s already there');
  console.log('    3. Then make your changes');
  console.log('');
  console.log('  Think before you act. Read before you write.');
  console.log('============================================================');
  console.log('');
  process.exit(1);
}

function blockWithSessionMessage(file) {
  console.log('');
  console.log('============================================================');
  console.log('  QUALITY FIRST: Read before you write');
  console.log('============================================================');
  console.log(`  File: ${file}`);
  console.log('');
  console.log('  You are trying to modify an existing file without reading');
  console.log('  it first in this session.');
  console.log('');
  console.log('  The Quality First contract requires understanding existing');
  console.log('  code before changing it. This prevents:');
  console.log('    - Breaking existing functionality');
  console.log('    - Duplicating code that already exists');
  console.log('    - Introducing inconsistencies with surrounding code');
  console.log('    - Wasting tokens on iterations that could be avoided');
  console.log('');
  console.log('  To proceed:');
  console.log(`    1. Use the Read tool to read '${file}'`);
  console.log('    2. Understand the existing code');
  console.log('    3. Then make your changes');
  console.log('============================================================');
  console.log('');
  process.exit(1);
}

// If no tracker exists, the agent hasn't read anything — block
if (!fileExists(TRACKER_FILE)) {
  blockWithMessage(filePath);
}

// Read tracker content
let trackerContent;
try {
  trackerContent = readFileSync(TRACKER_FILE, 'utf-8');
} catch {
  blockWithMessage(filePath);
}

// Normalize the file path for comparison
let normalizedPath = filePath;
if (!filePath.startsWith('/')) {
  normalizedPath = resolve(process.cwd(), filePath);
}

let fileWasRead = false;

// Check exact match
if (trackerContent.includes(`"${filePath}"`)) {
  fileWasRead = true;
}

// Check normalized path
if (!fileWasRead && trackerContent.includes(`"${normalizedPath}"`)) {
  fileWasRead = true;
}

// Check basename match (handles cases where path format differs)
if (!fileWasRead) {
  const base = basename(filePath);
  // Match the basename within a full path to avoid false positives
  const regex = new RegExp(`"[^"]*/${base.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}"`);
  if (regex.test(trackerContent)) {
    fileWasRead = true;
  }
}

if (!fileWasRead) {
  blockWithSessionMessage(filePath);
}

// File was read — allow the write/edit
process.exit(0);
