#!/usr/bin/env node
/**
 * pre-commit-lint.mjs — PreToolUse hook for `git commit`
 * BLOCKING (exit 2, before the commit exists): the project's own linter fails on the files that go
 * into the commit. Zero tolerance on those files, not on the whole repo.
 *
 * Files: the staged ones, plus the tracked changes with `git commit -a`, plus what a `git add` in
 * the same command will add (the hook runs before that `git add`).
 * Linters, only if the project or the machine already has them (never `npx`, which can download):
 *   .py                          ruff check (.venv/bin/ruff or ruff on PATH)
 *   .ts .tsx .js .jsx .mjs .cjs  eslint --max-warnings=0 (node_modules/.bin/eslint of the project)
 *   .dart                        dart analyze --no-fatal-infos (dart or fvm dart)
 * Nothing to lint, or no linter for those files → silent.
 *
 * v5.7.0 · US-93/UC-9302: runs before the commit (it ran after it, on an empty staging area) and
 * uses the project's linter on the committed files. GGA, an AI review, is no longer run here: it
 * cost a review per commit attempt; whoever wants it installs it as a git hook (`gga install`).
 */

import { spawnSync } from 'child_process';
import { existsSync } from 'fs';
import { join } from 'path';
import { readHookInput, gitDirForCommand, git, commandExists, commitFiles } from './lib/utils.mjs';
import { blockWith } from './lib/output.mjs';

const { toolInput, cwd } = readHookInput();
const command = String(toolInput.command || '');
if (command && !/\bgit\b[^;&|]*\bcommit\b/.test(command)) process.exit(0);
const repo = gitDirForCommand(command, cwd);
try {
  process.chdir(repo);
} catch {
  process.exit(0);
}
if (!git('rev-parse --show-toplevel')) process.exit(0);

const existing = commitFiles(command).filter((f) => existsSync(f));

const byExt = (re) => existing.filter((f) => re.test(f));
const runs = [];
const py = byExt(/\.py$/);
if (py.length) {
  const ruff = existsSync('.venv/bin/ruff') ? '.venv/bin/ruff' : commandExists('ruff') ? 'ruff' : null;
  if (ruff) runs.push({ name: 'ruff', cmd: ruff, args: ['check', ...py] });
}
const js = byExt(/\.(ts|tsx|js|jsx|mjs|cjs)$/);
const eslint = join('node_modules', '.bin', 'eslint');
if (js.length && existsSync(eslint)) runs.push({ name: 'eslint', cmd: eslint, args: ['--max-warnings=0', ...js] });
const dart = byExt(/\.dart$/);
if (dart.length) {
  if (commandExists('dart')) runs.push({ name: 'dart analyze', cmd: 'dart', args: ['analyze', '--no-fatal-infos', ...dart] });
  else if (commandExists('fvm')) runs.push({ name: 'dart analyze', cmd: 'fvm', args: ['dart', 'analyze', '--no-fatal-infos', ...dart] });
}

const failures = [];
for (const r of runs) {
  const res = spawnSync(r.cmd, r.args, { encoding: 'utf-8', timeout: 50_000 });
  if (res.error || res.status !== 0) {
    const out = `${res.stdout || ''}\n${res.stderr || ''}`.trim().split('\n').filter(Boolean);
    failures.push(`${r.name}:`, ...out.slice(-25).map((l) => `  ${l}`));
  }
}

if (failures.length) {
  blockWith('LINT: el commit no pasa el linter del proyecto', [
    ...failures,
    '',
    'Corrige estos errores en los ficheros del commit y vuelve a intentarlo. Tolerancia cero: también los avisos.',
  ]);
}
process.exit(0);
