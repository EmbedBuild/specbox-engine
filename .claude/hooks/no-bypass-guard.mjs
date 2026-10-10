#!/usr/bin/env node
/**
 * no-bypass-guard.mjs — PreToolUse hook for Bash
 * BLOCKING: stops the agent from skipping the quality checks or rewriting history
 * before the command runs (exit 2: the command does not run and the agent gets the reason).
 *
 *   --no-verify               skips the git hooks of the project
 *   push --force / -f / +ref  overwrites the remote branch; --force-with-lease and
 *                             --force-if-includes are allowed (they refuse to overwrite work
 *                             the agent has not seen, and the rebase flow needs them)
 *   reset --hard              throws away uncommitted changes
 *
 * v5.12.0 — Agent Quality Guardrails · US-93/UC-9302: blocks for real (it exited 1, which
 * Claude Code treats as a non-blocking error) and lets --force-with-lease through.
 */

import { readHookInput } from './lib/utils.mjs';
import { blockWith } from './lib/output.mjs';

const { toolInput } = readHookInput();
const command = String(toolInput.command || '');
if (!command) process.exit(0);

/** The arguments of each `git push` in the command (a compound command can have several). */
function pushArgs(cmd) {
  const out = [];
  for (const m of cmd.matchAll(/\bpush\b([^;&|]*)/g)) out.push(m[1].trim().split(/\s+/).filter(Boolean));
  return out;
}

/** Whether a push rewrites the remote without a safety check. */
function isForcePush(cmd) {
  return pushArgs(cmd).some((args) =>
    args.some((a) =>
      a === '--force'
      || (a.startsWith('--force') && !/^--force-(with-lease|if-includes)\b/.test(a))
      || /^-[a-zA-Z]*f[a-zA-Z]*$/.test(a)
      || /^\+[^\s]/.test(a)));
}

let reason = '';
let instead = '';
if (/(^|\s)--no-verify(\s|$)/.test(command)) {
  reason = '--no-verify se salta las comprobaciones del proyecto (lint, evidencia, guardias de spec).';
  instead = 'Corrige lo que la comprobación señala en vez de saltártela. Si de verdad hay que saltarla, pídeselo a la persona.';
} else if (isForcePush(command)) {
  reason = 'Un push forzado sobrescribe la rama remota, también el trabajo que otras sesiones han subido.';
  instead = 'Usa --force-with-lease (se niega si el remoto tiene algo que no has visto) o un commit nuevo.';
} else if (/\breset\s+(.*\s)?--hard\b/.test(command)) {
  reason = 'reset --hard tira los cambios sin guardar y no se pueden recuperar.';
  instead = "Guarda antes con un commit o con 'git stash', o pídele a la persona que lo haga ella.";
}

if (reason) {
  blockWith('GUARDIA DE CALIDAD: orden bloqueada', [`Orden: ${command}`, `Por qué: ${reason}`, `En su lugar: ${instead}`]);
}
process.exit(0);
