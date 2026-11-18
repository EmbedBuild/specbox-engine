#!/usr/bin/env node
/**
 * uc-lifecycle-guard.mjs — PostToolUse hook for git push
 * NOTE to the agent (additionalContext, US-93/UC-9302): pushing a feature branch without having
 * called move_uc to move the UC to Review. Ensures the board stays in sync.
 *
 * Also warns if mark_ac_batch hasn't been called (no ACs marked).
 *
 * UC-12206: los ficheros que mira (.quality/evidence/<feature>/ac_marked.json y
 * uc_moved_to_review.json) los escribe el hook uc-state-marker con lo que devuelven mark_ac_batch y
 * move_uc; antes no los escribía nadie y el aviso salía en cada push. El aviso nombra lo que falta:
 * los criterios sin marcar (con los de la UC que guarda el marcador) o la UC fuera de revisión.
 *
 * v5.19.0 — Compliance Enforcement
 */

import { readHookInput, gitDirForCommand, git, fileExists, readJsonFile } from './lib/utils.mjs';
import { getProjectConfig, getActiveUC } from './lib/config.mjs';
import { noteWith } from './lib/output.mjs';

const { toolInput, cwd } = readHookInput();
const command = String(toolInput.command || '');

// Only check git push commands
if (!command.includes('git push')) {
  process.exit(0);
}
// The repo the push comes from (`cd <dir> && git push`, `git -C <dir> push`).
try {
  process.chdir(gitDirForCommand(command, cwd, 'push'));
} catch {
  process.exit(0);
}

// Only check spec-driven projects
const { isSpecDriven } = getProjectConfig();
if (!isSpecDriven) {
  process.exit(0);
}

// Only check feature branches
const branch = git('branch --show-current');
if (!branch || !branch.startsWith('feature/')) {
  process.exit(0);
}

// Check if there's an active UC
const activeUC = getActiveUC();
if (!activeUC) {
  // No active UC but pushing feature branch — unusual but not necessarily wrong
  // (could be pushing after complete_uc was already called)
  process.exit(0);
}

const feature = activeUC.feature || activeUC.ucId;
const warnings = [];

// Los escribe el hook uc-state-marker con lo que devuelven mark_ac_batch y move_uc (UC-12206).
const evidenceDir = `.quality/evidence/${String(feature).replace(/[^A-Za-z0-9._-]/g, '_')}`;

// Check 1: criterios sin marcar como cumplidos.
const marked = readJsonFile(`${evidenceDir}/ac_marked.json`);
const audit = readJsonFile(`${evidenceDir}/audit.json`);
const marker = readJsonFile('.quality/active_uc.json') || {};
const acIds = Array.isArray(marker.ac_ids) ? marker.ac_ids : [];
if (!marked && !audit?.ac_results) {
  warnings.push(
    'Criterios sin marcar: no consta ningún mark_ac_batch de esta UC, así que el board no dice cuáles se cumplen.' +
      (acIds.length ? ` Faltan ${acIds.join(', ')}.` : '')
  );
} else if (marked) {
  const passed = new Set(Array.isArray(marked.passed) ? marked.passed : []);
  const missing = acIds.filter((id) => !passed.has(id));
  const failed = Array.isArray(marked.failed) ? marked.failed : [];
  if (missing.length) {
    warnings.push(`Criterios sin marcar como cumplidos: ${missing.join(', ')}.`);
  } else if (failed.length) {
    warnings.push(`Criterios marcados como no cumplidos: ${failed.join(', ')}.`);
  }
}

// Check 2: la UC fuera de revisión.
if (!fileExists(`${evidenceDir}/uc_moved_to_review.json`)) {
  warnings.push(
    `UC fuera de revisión: ${activeUC.ucId} no se ha movido a «review». ` +
      'Llama a move_uc(board_id, uc_id, "review") antes o después de abrir la PR.'
  );
}

if (warnings.length > 0) {
  noteWith('PostToolUse', 'UC LIFECYCLE: el board puede no reflejar lo que hay', [
    `Feature: ${feature} · UC: ${activeUC.ucId} · rama: ${branch}`,
    ...warnings.map((w) => `- ${w}`),
    'El push ya está hecho; pon el board al día ahora.',
  ]);
}

process.exit(0);
