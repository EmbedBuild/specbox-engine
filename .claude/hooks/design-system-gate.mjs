#!/usr/bin/env node
/**
 * design-system-gate.mjs — PreToolUse hook before an implementation goes to review
 * (US-49 · UC-4902). BLOCKING in autopilot.
 *
 * Triggers:
 *   - mcp__SpecBox-MCP__move_uc with target "review" or "done"
 *   - mcp__SpecBox-MCP__complete_uc
 *   - Bash `gh pr create`
 *
 * When the project has system tokens (design-system.tokens.json), it scans the
 * UI files changed on the branch (committed since the base branch, plus
 * uncommitted and untracked) for design gaps: colours written directly, fonts
 * outside the system, weights above the system maximum and gradients
 * (lib/design-gaps.mjs, same rules as the engine's get_visual_gap_report).
 *
 * Mode — `.claude/settings.local.json` → `specbox.design_gate.mode`:
 *   block — gaps stop the transition (exit 2) with what was found and what to do
 *   warn  — the same report, without stopping
 *   off   — no check
 * Default: `block` when `specbox.autopilot.level` is set to anything but `low`
 * (autopilot mode), `warn` otherwise.
 *
 * Without system tokens there is nothing to compare against: the hook passes.
 */

import { existsSync, readFileSync } from 'fs';
import { join } from 'path';
import { readStdin, git, readJsonFile } from './lib/utils.mjs';
import { findSystemTokens, fixFor, isUiSource, scanFiles } from './lib/design-gaps.mjs';

const MAX_LISTED = 40;
const KIND_LABELS = {
  direct_color: 'color escrito',
  font_outside: 'fuente fuera del sistema',
  weight_above: 'peso por encima del máximo',
  gradient: 'gradiente',
};

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

const root = git('rev-parse --show-toplevel') || process.cwd();
const settings = readJsonFile(join(root, '.claude', 'settings.local.json')) || {};

function resolveMode() {
  const mode = settings?.specbox?.design_gate?.mode;
  if (['block', 'warn', 'off'].includes(mode)) return mode;
  const level = settings?.specbox?.autopilot?.level;
  return level && level !== 'low' ? 'block' : 'warn';
}

const mode = resolveMode();
if (mode === 'off') process.exit(0);

const system = findSystemTokens(root);
if (!system) process.exit(0);
if (!system.rules) {
  process.stdout.write(
    `\nWARNING: design gate — ${system.path} no es JSON válido; no se puede comprobar el diseño.\n`,
  );
  process.exit(0);
}

function changedFiles() {
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
  return [...names];
}

const files = {};
for (const rel of changedFiles()) {
  if (!isUiSource(rel)) continue;
  const abs = join(root, rel);
  if (!existsSync(abs)) continue;
  try {
    files[rel] = readFileSync(abs, 'utf-8');
  } catch {
    /* unreadable: skip */
  }
}

const gaps = scanFiles(files, system.rules);
if (gaps.length === 0) process.exit(0);

const kinds = [...new Set(gaps.map((g) => g.kind))];
const lines = [
  `${gaps.length} brecha(s) de diseño en ${Object.keys(files).length} fichero(s) de UI cambiados,`,
  `comparados con los tokens del sistema (${system.path}):`,
  '',
  ...gaps.slice(0, MAX_LISTED).map((g) => `${g.location}  ${KIND_LABELS[g.kind]}: ${g.value}`),
];
if (gaps.length > MAX_LISTED) lines.push(`… y ${gaps.length - MAX_LISTED} más`);
lines.push('', 'Qué hacer:');
for (const kind of kinds) lines.push(`- ${KIND_LABELS[kind]}: ${fixFor(kind, system.rules)}`);
lines.push(
  '- Si un valor es deliberado, marca la línea con `design-gate:ignore` y el motivo;',
  '  un fichero de terceros entero, con `design-gate:disable-file`.',
  '- Corrige y vuelve a intentar el paso a revisión: el gate se ejecuta de nuevo.',
);

const title =
  mode === 'block'
    ? 'DESIGN GATE: la implementación se sale del sistema — paso a revisión bloqueado'
    : 'DESIGN GATE (aviso): la implementación se sale del sistema';
const out = mode === 'block' ? process.stderr : process.stdout;
out.write('\n============================================================\n');
out.write(`  ${title}\n`);
out.write('============================================================\n');
for (const line of lines) out.write(`  ${line}\n`);
out.write('============================================================\n\n');
process.exit(mode === 'block' ? 2 : 0);
