#!/usr/bin/env node
/**
 * commit-spec-guard.mjs — PreToolUse hook for `git commit`
 *
 * BLOCKING (exit 2, before the commit exists):
 *   1. Commit on main/master in a spec-driven project.
 * NOTE to the agent (additionalContext, the commit goes ahead):
 *   2. No active UC.
 *   3. No checkpoint saved for the active feature.
 *   4. Large commit (more than 15 staged files).
 *
 * Checks the repo the command acts on (`cd <dir> && git commit`, `git -C <dir> commit`), not the
 * session's directory.
 *
 * v5.10.0 — Branch discipline · US-93/UC-9302: runs before the commit (it ran after it, so its
 * «blocked» commit already existed) and its warnings reach the agent.
 */

import { readHookInput, gitDirForCommand, git, fileExists, readJsonFile } from './lib/utils.mjs';
import { getProjectConfig } from './lib/config.mjs';
import { blockWith, noteWith } from './lib/output.mjs';

const { toolInput, cwd } = readHookInput();
const command = String(toolInput.command || '');
if (command && !/\bgit\b[^;&|]*\bcommit\b/.test(command)) process.exit(0);
try {
  process.chdir(gitDirForCommand(command, cwd));
} catch {
  process.exit(0);
}

const { boardId, isSpecDriven } = getProjectConfig();
if (!isSpecDriven) process.exit(0);

const branch = git('branch --show-current');
if (branch === 'main' || branch === 'master') {
  blockWith(`COMMIT BLOQUEADO: no se hace commit en ${branch}`, [
    'Es un proyecto spec-driven: el trabajo va en una rama de la UC, nunca en main ni en master.',
    'Para seguir: git checkout -b feature/{uc}-{nombre} (los cambios se van contigo) y haz el commit ahí.',
  ]);
}

const notes = [];
const activeUC = fileExists('.quality/active_uc.json') ? readJsonFile('.quality/active_uc.json') : null;
if (!activeUC) {
  notes.push(`- No hay UC activa (board ${boardId}): llama a start_uc antes de implementar y a mark_ac_batch al terminar.`);
} else if (activeUC.feature && !fileExists(`.quality/evidence/${activeUC.feature}/checkpoint.json`)) {
  notes.push(`- La feature «${activeUC.feature}» no tiene checkpoint: llama a report_checkpoint para poder retomarla.`);
}
const staged = git('diff --cached --name-only').split('\n').filter(Boolean).length;
if (staged > 15) {
  notes.push(`- Commit grande (${staged} ficheros): mejor un commit por UC, para poder seguirlo y deshacerlo.`);
}

if (notes.length) {
  noteWith('PreToolUse', 'SPEC GUARD: el commit sigue, pero conviene arreglar esto', [
    ...notes,
    'Recorrido: find_next_uc → start_uc → implementar → mark_ac_batch → complete_uc.',
  ]);
}
process.exit(0);
