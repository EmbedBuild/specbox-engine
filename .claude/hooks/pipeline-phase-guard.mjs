#!/usr/bin/env node
/**
 * pipeline-phase-guard.mjs — PreToolUse hook for Write/Edit during /implement
 * BLOCKING: Prevents the agent from writing code that belongs to a phase
 * whose dependencies haven't been completed yet.
 *
 * Reads .quality/evidence/{feature}/checkpoint.json to determine current phase.
 * Validates that prerequisite phases are complete before allowing writes
 * that belong to subsequent phases.
 *
 * Phase dependency map (from /implement SKILL.md):
 *   Phase 1: DB/Infra           → no dependencies
 *   Phase 2: Stitch Designs     → no dependencies
 *   Phase 3: Design-to-Code     → requires Phase 2 (if UI project)
 *   Phase 4: Feature Code       → requires Phase 1 (if DB), Phase 3 (if UI)
 *   Phase 5: Apps Script / n8n  → requires Phase 4
 *   Phase 6: Integration / DI   → requires Phase 4
 *   Phase 7: Quality / Tests    → requires Phase 4
 *
 * v5.19.0 — Mechanical Enforcement
 */

import { readStdin, fileExists, readJsonFile } from './lib/utils.mjs';
import { printBlock } from './lib/output.mjs';
import { getActiveUC } from './lib/config.mjs';

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

// Get active UC
const activeUC = getActiveUC();
if (!activeUC || !activeUC.feature) {
  // No active UC → spec-guard handles this
  process.exit(0);
}

const feature = activeUC.feature;
const checkpointFile = `.quality/evidence/${feature}/checkpoint.json`;
const pipelineStateFile = `.quality/evidence/${feature}/pipeline_state.json`;

// Read pipeline state (written by implement skill at each phase transition)
const pipelineState = readJsonFile(pipelineStateFile);
if (!pipelineState) {
  // No pipeline state yet → first phase, allow
  process.exit(0);
}

const completedPhases = pipelineState.completed_phases || [];

// Detect what phase this file write belongs to based on path patterns
const detectedPhase = detectPhaseFromPath(filePath);
if (!detectedPhase) {
  // Can't determine phase from path → allow (conservative)
  process.exit(0);
}

// Check dependencies for the detected phase
const missingDeps = getMissingDependencies(detectedPhase, completedPhases, pipelineState);

if (missingDeps.length > 0) {
  printBlock(`PIPELINE PHASE GUARD — Phase "${detectedPhase}" blocked`, [
    `Feature: ${feature}`,
    `File: ${filePath}`,
    `Detected phase: ${detectedPhase}`,
    `Completed phases: ${completedPhases.join(', ') || '(none)'}`,
    '',
    `Missing prerequisites: ${missingDeps.join(', ')}`,
    '',
    'The SpecBox pipeline requires phases to execute in order.',
    'Complete the prerequisite phases before proceeding.',
    '',
    'Phase order: DB/Infra → Designs → Design-to-Code → Features → Integration → Tests',
  ]);
  process.exit(1);
}

process.exit(0);

// --- Helper functions ---

/**
 * Detect which implementation phase a file belongs to based on its path.
 * Returns phase name or null if can't determine.
 */
function detectPhaseFromPath(path) {
  // DB/Infra: migrations, schema, SQL, Supabase functions
  if (/(?:migrations?|schema|\.sql|supabase\/functions|prisma|drizzle)/.test(path)) {
    return 'db_infra';
  }

  // Design-to-code output: presentation layer, pages, widgets, components
  if (/(?:presentation\/(?:pages|widgets|components)|src\/(?:pages|components|views)|app\/.*page\.)/.test(path)) {
    return 'design_to_code';
  }

  // Feature code: domain, data, services, models, controllers, handlers
  if (/(?:domain\/|data\/|services\/|models\/|controllers\/|handlers\/|internal\/|cmd\/|api\/)/.test(path)) {
    return 'feature_code';
  }

  // Integration: DI, providers, routing, app config
  if (/(?:injection|providers?\/|routing|app_router|di\.|container\.)/.test(path)) {
    return 'integration';
  }

  // Tests
  if (/(?:test\/|tests\/|_test\.|\.test\.|\.spec\.|e2e\/|acceptance\/)/.test(path)) {
    return 'tests';
  }

  return null;
}

/**
 * Given a target phase, check if all its dependencies are in completedPhases.
 * Returns array of missing dependency names.
 */
function getMissingDependencies(phase, completedPhases, state) {
  const isUI = state.has_ui !== false; // default true if not specified
  const hasDB = state.has_db === true;

  const deps = {
    'db_infra': [],
    'stitch_designs': [],
    'design_to_code': isUI ? ['stitch_designs'] : [],
    'feature_code': [
      ...(hasDB ? ['db_infra'] : []),
      ...(isUI ? ['design_to_code'] : []),
    ],
    'integration': ['feature_code'],
    'tests': ['feature_code'],
  };

  const required = deps[phase] || [];
  return required.filter(dep => !completedPhases.includes(dep));
}
