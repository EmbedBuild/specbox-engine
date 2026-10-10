#!/usr/bin/env node
/**
 * design-review-gate.mjs — PreToolUse hook before an implementation goes to review
 * (US-91 · UC-9102).
 *
 * Triggers:
 *   - mcp__SpecBox-MCP__move_uc with target "review" or "done"
 *   - mcp__SpecBox-MCP__complete_uc
 *   - Bash `gh pr create`
 *
 * Reads the verdict of each screen verification changed on the branch
 * (doc/design/{feature}/{screen}.verify.md, written by /design-review verify and /implement
 * Paso 6.5) and applies the project's mode:
 *
 *   `.claude/settings.local.json` → `specbox.design_review.mode`
 *     warn  — (default) the verdict goes to the PR and the evidence; nothing stops here
 *     block — a «Block» verdict stops the transition (exit 2) with the screens and their
 *             three priority problems
 *     off   — no check
 *
 * Changing the mode never requires touching the skill.
 */

import { existsSync, readFileSync } from 'fs';
import { join } from 'path';
import { readStdin, git, readJsonFile } from './lib/utils.mjs';

let payload = {};
try {
  payload = JSON.parse(readStdin() || '{}');
} catch {
  process.exit(0);
}

const toolName = payload.tool_name || payload.toolName || '';
const toolInput = payload.tool_input ?? payload.toolInput ?? {};

function goesToReview() {
  if (/move_uc$/.test(toolName)) return ['review', 'done'].includes(String(toolInput.target || '').toLowerCase());
  if (/complete_uc$/.test(toolName)) return true;
  if (toolName === 'Bash') return /\bgh\s+pr\s+create\b/.test(String(toolInput.command || ''));
  return false;
}

if (!goesToReview()) process.exit(0);

const root = git('rev-parse --show-toplevel') || payload.cwd || process.cwd();
const settings = readJsonFile(join(root, '.claude', 'settings.local.json')) || {};
const mode = settings?.specbox?.design_review?.mode;
if (mode !== 'block') process.exit(0);

function changedVerifications() {
  const run = (args) => git(`-C "${root}" ${args}`);
  let base = '';
  for (const ref of ['origin/main', 'origin/master', 'main', 'master']) {
    base = run(`merge-base HEAD ${ref}`);
    if (base) break;
  }
  const names = new Set();
  const add = (out) => out.split('\n').map((s) => s.trim()).filter(Boolean).forEach((f) => names.add(f));
  if (base) add(run(`diff --name-only --diff-filter=ACMR ${base}...HEAD`));
  add(run('diff --name-only --diff-filter=ACMR HEAD'));
  add(run('ls-files --others --exclude-standard'));
  return [...names].filter((f) => /(^|\/)doc\/design\/.+\.verify\.md$/.test(f));
}

/** Verdict and priority problems of a {screen}.verify.md. */
function readVerification(rel) {
  const abs = join(root, rel);
  if (!existsSync(abs)) return null;
  const text = readFileSync(abs, 'utf-8');
  const verdict = text.match(/Veredicto:\s*(Block|Needs changes|Approve)\b/i)?.[1] ?? null;
  const section = text.split(/^##\s+Tres problemas prioritarios\s*$/m)[1] ?? '';
  const problems = section.split(/^##\s/m)[0].split('\n').filter((l) => /^\s*\d+\.\s/.test(l)).map((l) => l.trim());
  return { rel, verdict, problems };
}

const blocked = changedVerifications().map(readVerification).filter((v) => v && /^block$/i.test(v.verdict || ''));
if (blocked.length === 0) process.exit(0);

const lines = [
  '',
  '============================================================',
  '  DESIGN REVIEW: hay pantallas con veredicto «Block» — paso a revisión bloqueado',
  '============================================================',
  '  El proyecto está en modo bloqueante (specbox.design_review.mode = "block").',
  '',
];
for (const v of blocked) {
  lines.push(`  ${v.rel}`);
  for (const p of v.problems.slice(0, 3)) lines.push(`    ${p}`);
}
lines.push(
  '',
  '  Qué hacer: aplica la ronda de corrección del Paso 6.5 de /implement (una sola, sin',
  '  inventar datos), vuelve a medir con --previous y --sources y actualiza el .verify.md.',
  '  Para entregar con el veredicto a la vista, el modo "warn" lo lleva a la PR sin bloquear.',
  '============================================================',
  '',
);
process.stderr.write(lines.join('\n'));
process.exit(2);
