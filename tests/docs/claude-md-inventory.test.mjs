/**
 * UC-7203 (US-72): CLAUDE.md del engine nombra lo que hay, ni más ni menos.
 *
 * Las tablas «Available Skills», «Hooks» y «Agents» y el árbol del repositorio se comparan con
 * .claude/skills/<name>/SKILL.md, .claude/hooks/*.mjs y agents/*.md; ningún ID de agente se repite.
 *
 * Ejecutar: node --test tests/docs/claude-md-inventory.test.mjs
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = resolve(fileURLToPath(import.meta.url), '../../..');
const claude = readFileSync(join(repoRoot, 'CLAUDE.md'), 'utf8');

const sorted = (xs) => [...new Set(xs)].sort();

/** El texto de una sección «## Título» hasta la siguiente de su nivel. */
function section(title) {
  const start = claude.indexOf(`\n## ${title}\n`);
  assert.ok(start >= 0, `CLAUDE.md no tiene la sección «${title}»`);
  const end = claude.indexOf('\n## ', start + 1);
  return claude.slice(start, end < 0 ? undefined : end);
}

/** La primera celda de cada fila de tabla (sin cabecera ni separador), sin negritas. */
function firstCells(text) {
  return text
    .split('\n')
    .filter((l) => l.startsWith('| ') && !/^\|\s*-/.test(l))
    .map((l) => l.split('|')[1].replace(/\*\*/g, '').trim())
    .slice(1);
}

/** Líneas del árbol entre dos marcas. */
function treeBetween(from, to) {
  const start = claude.indexOf(from);
  const end = claude.indexOf(to, start + from.length);
  assert.ok(start >= 0 && end > start, `árbol: ${from}`);
  return claude.slice(start + from.length, end).split('\n');
}

const skillDirs = sorted(
  readdirSync(join(repoRoot, '.claude/skills')).filter((d) => existsSync(join(repoRoot, '.claude/skills', d, 'SKILL.md'))),
);
const hookFiles = sorted(
  readdirSync(join(repoRoot, '.claude/hooks'))
    .filter((f) => f.endsWith('.mjs'))
    .map((f) => f.slice(0, -'.mjs'.length)),
);
const agentFiles = sorted(readdirSync(join(repoRoot, 'agents')).filter((f) => f.endsWith('.md')));

test('la tabla de skills nombra cada skill que existe y ninguna que no', () => {
  const table = firstCells(section('Available Skills')).map((c) => c.replace(/^\//, ''));
  assert.deepEqual(sorted(table), skillDirs);
});

test('el árbol del repositorio lista cada skill', () => {
  const tree = treeBetween('│   ├── skills/', '│   ├── hooks/')
    .map((l) => l.match(/── ([a-z0-9-]+)\/SKILL\.md/)?.[1])
    .filter(Boolean);
  assert.deepEqual(sorted(tree), skillDirs);
});

test('la tabla de hooks nombra cada hook que existe y ninguno que no', () => {
  assert.deepEqual(sorted(firstCells(section('Hooks'))), hookFiles);
});

test('el árbol del repositorio lista cada hook', () => {
  const tree = treeBetween('│   ├── hooks/', '│   └── settings.json')
    .map((l) => l.match(/── ([a-z0-9-]+)\.mjs/)?.[1])
    .filter(Boolean);
  assert.deepEqual(sorted(tree), hookFiles);
});

test('la tabla de agentes nombra cada agente una vez, sin IDs repetidos', () => {
  const rows = section('Agents')
    .split('\n')
    .filter((l) => /^\| AG-/.test(l))
    .map((l) => l.split('|').map((c) => c.trim()));
  const ids = rows.map((r) => r[1]);
  assert.deepEqual(ids.filter((id, i) => ids.indexOf(id) !== i), [], 'IDs repetidos');
  const files = rows.map((r) => r[3].match(/agents\/([a-z0-9-]+\.md)/)?.[1]);
  assert.deepEqual(sorted(files), agentFiles);
});

test('el árbol del repositorio lista cada agente', () => {
  const tree = treeBetween('├── agents/', '├── agent-teams/')
    .map((l) => l.match(/── ([a-z0-9-]+\.md)/)?.[1])
    .filter(Boolean);
  assert.deepEqual(sorted(tree), agentFiles);
});
