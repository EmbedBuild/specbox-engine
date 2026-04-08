#!/usr/bin/env node
/**
 * checkpoint-freshness-guard.mjs — PostToolUse hook for git commit
 * WARNING (non-blocking): Warns if active UC exists but checkpoint is stale (>30min)
 * or missing entirely. Reminds the agent to save checkpoints for recovery.
 *
 * v5.19.0 — Compliance Enforcement
 */

import { fileExists, fileAge, readJsonFile } from './lib/utils.mjs';
import { getActiveUC } from './lib/config.mjs';
import { printWarning } from './lib/output.mjs';

// Only check if there's an active UC (implementation in progress)
const activeUC = getActiveUC();
if (!activeUC || !activeUC.feature) {
  process.exit(0);
}

const feature = activeUC.feature;
const checkpointFile = `.quality/evidence/${feature}/checkpoint.json`;

if (!fileExists(checkpointFile)) {
  printWarning(
    `[CHECKPOINT] No checkpoint found for feature "${feature}". ` +
    `If the session is interrupted, progress will be lost. ` +
    `Save checkpoint: node .claude/hooks/implement-checkpoint.mjs ${feature} {N} {phase_name}`
  );
  process.exit(0);
}

// Check freshness — warn if older than 30 minutes
const age = fileAge(checkpointFile);
const MAX_FRESHNESS_SECONDS = 30 * 60; // 30 minutes

if (age > MAX_FRESHNESS_SECONDS) {
  const minutesAgo = Math.round(age / 60);
  const checkpoint = readJsonFile(checkpointFile);
  const phase = checkpoint ? `Phase ${checkpoint.phase} (${checkpoint.phase_name || 'unknown'})` : 'unknown phase';

  printWarning(
    `[CHECKPOINT] Last checkpoint for "${feature}" is ${minutesAgo}min old (${phase}). ` +
    `Consider saving a fresh checkpoint to protect progress. ` +
    `Save: node .claude/hooks/implement-checkpoint.mjs ${feature} {N} {phase_name}`
  );
}

process.exit(0);
