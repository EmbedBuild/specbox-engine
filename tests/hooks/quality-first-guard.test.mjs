/**
 * quality-first-guard.mjs (UC-7006): cuando bloquea, explica qué se bloqueó, por qué y qué hacer, y
 * no repite el lema invertido («SpecBox provides speed. YOUR job is QUALITY.»): la velocidad la pone
 * el modelo; SpecBox pone el control y garantiza la calidad.
 *
 * Ejecutar: node --test tests/hooks/quality-first-guard.test.mjs
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = resolve(fileURLToPath(import.meta.url), '../../..');
const hookPath = join(repoRoot, '.claude/hooks/quality-first-guard.mjs');

/** Un proyecto temporal con un fichero existente y, si se pide, un registro de lecturas. */
function withProject(tracker, fn) {
  const dir = mkdtempSync(join(tmpdir(), 'quality-first-guard-'));
  try {
    writeFileSync(join(dir, 'app.ts'), 'export const answer = 42;\n');
    if (tracker !== undefined) {
      mkdirSync(join(dir, '.quality'));
      writeFileSync(join(dir, '.quality/read_tracker.jsonl'), tracker);
    }
    return fn(dir);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

function runHook(cwd, filePath) {
  const r = spawnSync('node', [hookPath], {
    cwd,
    input: JSON.stringify({ file_path: filePath }),
    encoding: 'utf-8',
    timeout: 10000,
  });
  return { code: r.status, out: `${r.stdout ?? ''}${r.stderr ?? ''}` };
}

const INVERTED = /provides speed|YOUR job is QUALITY/i;

function assertExplains(out, file) {
  assert.match(out, /QUALITY FIRST: Read before you write/, 'dice qué regla bloquea');
  assert.ok(out.includes(`File: ${file}`), 'dice qué fichero se bloqueó');
  assert.match(out, /without reading/, 'dice por qué');
  assert.match(out, /To proceed:\s+1\. Use the Read tool/, 'dice qué hacer');
  assert.doesNotMatch(out, INVERTED, 'sin el lema invertido');
}

test('sin registro de lecturas, bloquea y explica qué, por qué y qué hacer, sin el lema invertido', () => {
  withProject(undefined, (dir) => {
    const file = join(dir, 'app.ts');
    const { code, out } = runHook(dir, file);
    assert.equal(code, 1);
    assertExplains(out, file);
  });
});

test('con registro de lecturas pero sin ese fichero, bloquea con el mismo criterio', () => {
  withProject(`${JSON.stringify({ file: '/otro/sitio/otro.ts' })}\n`, (dir) => {
    const file = join(dir, 'app.ts');
    const { code, out } = runHook(dir, file);
    assert.equal(code, 1);
    assertExplains(out, file);
  });
});

test('si el fichero se leyó en la sesión, deja escribir', () => {
  withProject(undefined, (dir) => {
    const file = join(dir, 'app.ts');
    mkdirSync(join(dir, '.quality'));
    writeFileSync(join(dir, '.quality/read_tracker.jsonl'), `${JSON.stringify({ file })}\n`);
    assert.equal(runHook(dir, file).code, 0);
  });
});

test('ni el hook ni su versión bash anterior llevan el lema invertido', async () => {
  const { readFileSync } = await import('node:fs');
  for (const f of ['.claude/hooks/quality-first-guard.mjs', '.claude/hooks/legacy-bash/quality-first-guard.sh']) {
    assert.doesNotMatch(readFileSync(join(repoRoot, f), 'utf8'), INVERTED, f);
  }
});
