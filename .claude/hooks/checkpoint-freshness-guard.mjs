#!/usr/bin/env node
/**
 * checkpoint-freshness-guard.mjs — PostToolUse hook for git commit
 * NOTE to the agent (additionalContext, US-93/UC-9302): active UC with a stale (>30min) or
 * missing checkpoint. Reminds the agent to save checkpoints for recovery.
 *
 * v5.19.0 — Compliance Enforcement
 */

import { fileExists, fileAge, readJsonFile } from './lib/utils.mjs';
import { getActiveUC } from './lib/config.mjs';
import { noteWith } from './lib/output.mjs';
import { readHookInput, gitDirForCommand } from './lib/utils.mjs';

// The repo the commit went to (`cd <dir> && git commit`, `git -C <dir> commit`).
{
  const { toolInput, cwd } = readHookInput();
  try {
    process.chdir(gitDirForCommand(String(toolInput.command || ''), cwd));
  } catch {
    process.exit(0);
  }
}

// Only check if there's an active UC (implementation in progress)
const activeUC = getActiveUC();
if (!activeUC || !activeUC.feature) {
  process.exit(0);
}

const feature = activeUC.feature;
const checkpointFile = `.quality/evidence/${feature}/checkpoint.json`;

if (!fileExists(checkpointFile)) {
  noteWith('PostToolUse', `[CHECKPOINT] La feature «${feature}» no tiene checkpoint`, [
    'Si la sesión se corta, el avance se pierde.',
    `Guárdalo: node .claude/hooks/implement-checkpoint.mjs ${feature} {N} {phase_name}`,
  ]);
}

// Check freshness — warn if older than 30 minutes
const age = fileAge(checkpointFile);
const MAX_FRESHNESS_SECONDS = 30 * 60; // 30 minutes

if (age > MAX_FRESHNESS_SECONDS) {
  const minutesAgo = Math.round(age / 60);
  const checkpoint = readJsonFile(checkpointFile);
  const phase = checkpoint ? `Phase ${checkpoint.phase} (${checkpoint.phase_name || 'unknown'})` : 'unknown phase';

  noteWith('PostToolUse', `[CHECKPOINT] El último checkpoint de «${feature}» tiene ${minutesAgo} min (${phase})`, [
    'Guarda uno nuevo para no perder lo hecho desde entonces:',
    `node .claude/hooks/implement-checkpoint.mjs ${feature} {N} {phase_name}`,
  ]);
}

process.exit(0);
