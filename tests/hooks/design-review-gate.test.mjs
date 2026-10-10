/**
 * UC-9102 (US-91): el veredicto de la verificación de pantallas avisa o bloquea según el proyecto.
 *
 * AC-03: en modo aviso (el de por defecto) un «Block» no impide pasar a revisión; con
 * `specbox.design_review.mode = "block"` en `.claude/settings.local.json` lo para, sin tocar la skill.
 * El hook lee los `.verify.md` cambiados en la rama.
 *
 * Ejecutar: node --test tests/hooks/design-review-gate.test.mjs
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = resolve(fileURLToPath(import.meta.url), '../../..');
const hook = join(repoRoot, '.claude/hooks/design-review-gate.mjs');

const VERIFY = (verdict) => `# Verificación: listado

**Veredicto: ${verdict} · Total: 22/40**

## Tres problemas prioritarios
1. **.dos-col (l. 151):** scroll horizontal a 390 px.
2. **.texto (l. 141):** el espacio entre párrafos queda a cero.
3. **Hero (l. 119):** animación de 1,6 s al cargar.

## Notas
| # | Criterio | Nota | Justificación |
`;

function repo({ mode, verdict = 'Block', onMain = false } = {}) {
  const dir = mkdtempSync(join(tmpdir(), 'design-review-gate-'));
  const git = (...args) => spawnSync('git', args, { cwd: dir, encoding: 'utf8' });
  const write = (rel, content) => {
    mkdirSync(dirname(join(dir, rel)), { recursive: true });
    writeFileSync(join(dir, rel), content);
  };
  git('init', '-q', '-b', 'main');
  git('config', 'user.email', 't@t');
  git('config', 'user.name', 't');
  write('README.md', 'x\n');
  if (onMain) write('doc/design/propuestas/listado.verify.md', VERIFY(verdict));
  git('add', '-A');
  git('commit', '-qm', 'base');
  git('checkout', '-qb', 'feature/UC-1');
  if (!onMain) {
    write('doc/design/propuestas/listado.verify.md', VERIFY(verdict));
    git('add', '-A');
    git('commit', '-qm', 'verify');
  }
  if (mode) write('.claude/settings.local.json', JSON.stringify({ specbox: { design_review: { mode } } }));
  return { dir, done: () => rmSync(dir, { recursive: true, force: true }) };
}

function run(r, tool_name, tool_input) {
  return spawnSync(process.execPath, [hook], { cwd: r.dir, input: JSON.stringify({ tool_name, tool_input, cwd: r.dir }), encoding: 'utf8' });
}

const toReview = ['mcp__SpecBox-MCP__move_uc', { board_id: 'b', uc_id: 'UC-1', target: 'review' }];

test('AC-03: en modo bloqueante, un «Block» para el paso a revisión con las pantallas y sus problemas', () => {
  const r = repo({ mode: 'block' });
  try {
    for (const [tool, input] of [toReview, ['mcp__SpecBox-MCP__complete_uc', { uc_id: 'UC-1' }], ['Bash', { command: 'gh pr create --title x --body y' }]]) {
      const res = run(r, tool, input);
      assert.equal(res.status, 2, tool);
      assert.match(res.stderr, /doc\/design\/propuestas\/listado\.verify\.md/);
      assert.match(res.stderr, /1\. \*\*\.dos-col \(l\. 151\):\*\*/);
      assert.match(res.stderr, /modo bloqueante/);
    }
  } finally {
    r.done();
  }
});

test('AC-03: en modo aviso (por defecto) y apagado, el «Block» no para nada', () => {
  for (const mode of [undefined, 'warn', 'off']) {
    const r = repo({ mode });
    try {
      const res = run(r, ...toReview);
      assert.equal(res.status, 0, `modo ${mode}`);
      assert.equal(res.stderr, '');
    } finally {
      r.done();
    }
  }
});

test('en modo bloqueante pasan «Approve» y «Needs changes», los .verify.md que no cambian y lo que no va a revisión', () => {
  for (const verdict of ['Approve', 'Needs changes']) {
    const r = repo({ mode: 'block', verdict });
    try {
      assert.equal(run(r, ...toReview).status, 0, verdict);
    } finally {
      r.done();
    }
  }
  const old = repo({ mode: 'block', onMain: true });
  try {
    assert.equal(run(old, ...toReview).status, 0, 'un Block que ya estaba en main no es de esta rama');
  } finally {
    old.done();
  }
  const r = repo({ mode: 'block' });
  try {
    assert.equal(run(r, 'mcp__SpecBox-MCP__move_uc', { target: 'in_progress' }).status, 0);
    assert.equal(run(r, 'Bash', { command: 'git status' }).status, 0);
  } finally {
    r.done();
  }
});

test('registro: en el board sin condición y en Bash con una condición que casa con gh pr create', () => {
  for (const path of ['.claude/settings.json', 'templates/settings.json.template']) {
    const pre = JSON.parse(readFileSync(join(repoRoot, path), 'utf8')).hooks.PreToolUse;
    const entries = (matcher) => pre.filter((g) => g.matcher === matcher).flatMap((g) => g.hooks).filter((h) => h.command.includes('design-review-gate.mjs'));
    const board = entries('mcp__SpecBox-MCP__(move_uc|complete_uc)');
    assert.equal(board.length, 1, path);
    assert.equal(board[0].if, undefined, path);
    const bash = entries('Bash');
    assert.equal(bash.length, 1, path);
    assert.equal(bash[0].if, 'Bash(*gh pr create*)', `${path}: glob de reglas de permisos, no regex`);
  }
});
