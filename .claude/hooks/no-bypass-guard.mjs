#!/usr/bin/env node
/**
 * no-bypass-guard.mjs — PreToolUse hook
 * BLOCKING: Prevents the agent from accidentally bypassing quality hooks
 * or performing destructive git operations.
 *
 * v5.12.0 — Agent Quality Guardrails
 */

import { readStdin } from './lib/utils.mjs';

const input = readStdin();

// Extract command from tool input
let command = '';
try {
  const parsed = JSON.parse(input);
  command = parsed.command || '';
} catch {
  const match = input.match(/"command"\s*:\s*"([^"]*)"/);
  command = match ? match[1] : '';
}

if (!command) {
  process.exit(0);
}

let blocked = false;
let reason = '';
let guidance = '';

// Check for --no-verify (hook bypass)
if (command.includes('--no-verify')) {
  blocked = true;
  reason = '--no-verify skips quality hooks (e2e-gate, spec-guard, lint).';
  guidance = 'Fix the issue that the hook is catching instead of bypassing it.';
}

// Check for push --force or push -f (destructive push)
if (/push\s+.*(-f\b|--force)/.test(command)) {
  blocked = true;
  reason = 'Force push can overwrite branch history that other sessions depend on.';
  guidance = 'Use a new commit to fix the issue instead of rewriting history.';
}

// Check for reset --hard (destructive reset)
if (command.includes('reset --hard')) {
  blocked = true;
  reason = 'Hard reset loses uncommitted changes without recovery.';
  guidance = "Use 'git stash' to save changes, or commit first, then fix.";
}

if (blocked) {
  console.log('');
  console.log('============================================================');
  console.log('  QUALITY GUARD: Operation blocked');
  console.log('============================================================');
  console.log(`  Command: ${command}`);
  console.log(`  Why: ${reason}`);
  console.log(`  Instead: ${guidance}`);
  console.log('============================================================');
  console.log('');
  process.exit(1);
}

process.exit(0);
