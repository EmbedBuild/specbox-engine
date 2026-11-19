/**
 * UC-12701 AC-04 — /fix para y propone /prd si el arreglo toca más de 5 ficheros, sin contar sus
 * pruebas, o un contrato de API o una migración de datos (`.claude/skills/fix/scripts/scope.mjs`).
 * Ejecutar: node --test tests/hooks/fix-scope.test.mjs
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { classifiable, decide } from '../../.claude/skills/fix/scripts/scope.mjs';
import { classifyCommit } from '../../.claude/hooks/lib/impact-radius.mjs';

const repoRoot = resolve(fileURLToPath(import.meta.url), '../../..');
const SCOPE = join(repoRoot, '.claude/skills/fix/scripts/scope.mjs');

const files = (n, prefix = 'src/m') => Array.from({ length: n }, (_, i) => `${prefix}${i}.py`);
const judge = (list) => decide(list, classifyCommit(classifiable(list)));

test('AC-04: cinco ficheros siguen siendo un arreglo; seis no', () => {
  assert.equal(judge(files(5)).stop, false);
  const six = judge(files(6));
  assert.equal(six.stop, true);
  assert.equal(six.count, 6);
  assert.match(six.reasons[0], /toca 6 ficheros \(el límite de \/fix es 5/);
});

test('AC-04: las pruebas del arreglo, .quality/ y doc/tracking/ no cuentan', () => {
  const list = [
    ...files(5),
    'tests/test_total.py', 'src/total.test.ts', 'lib/total_test.go', 'test/widget_test.dart',
    '.quality/evidence/UC-1/x.json', 'doc/tracking/items.json',
  ];
  const r = judge(list);
  assert.equal(r.stop, false);
  assert.equal(r.count, 5);
  assert.deepEqual(r.excluded.map((e) => e.why).sort(), [
    'prueba del arreglo', 'prueba del arreglo', 'prueba del arreglo', 'prueba del arreglo', 'registro del engine', 'registro del engine',
  ]);
});

test('AC-04: un contrato de API o una migración de datos paran aunque sean pocos ficheros', () => {
  const api = judge(['api/openapi.yaml', 'src/a.py']);
  assert.equal(api.stop, true);
  assert.match(api.reasons.join(' '), /contrato de API: api\/openapi\.yaml/);
  const migration = judge(['db/migrations/0003_add_total.sql']);
  assert.equal(migration.stop, true);
  assert.match(migration.reasons.join(' '), /migración de datos: db\/migrations\/0003_add_total\.sql/);
  // Una semilla de pruebas no es una migración.
  assert.equal(judge(['tests/fixtures/seed.sql', 'src/a.py']).stop, false);
});

test('AC-04: un contrato o una migración dentro de una carpeta de pruebas también paran', () => {
  // No cuentan para el límite, pero se clasifican: la regla es la del hook del radio de impacto.
  for (const path of ['spec/openapi.yaml', 'api/spec/openapi.yaml']) {
    const r = judge([path]);
    assert.equal(r.stop, true, path);
    assert.equal(r.count, 0);
    assert.match(r.reasons.join(' '), new RegExp(`contrato de API: ${path.replace(/[./]/g, '\\$&')}`));
  }
  const migration = judge(['integration_test/migrations/0001.sql']);
  assert.equal(migration.stop, true);
  assert.match(migration.reasons.join(' '), /migración de datos/);
  // doc/spec/ es el documento de comportamiento, no una prueba: cuenta.
  assert.deepEqual(judge(['doc/spec/cobros.md']).files, ['doc/spec/cobros.md']);
});

function repo() {
  const dir = mkdtempSync(join(tmpdir(), 'fix-scope-'));
  const run = (...args) => spawnSync('git', args, { cwd: dir, encoding: 'utf8' });
  run('init', '-q', '-b', 'main');
  run('config', 'user.email', 'a@b.c');
  run('config', 'user.name', 'Prueba');
  const write = (rel, text) => {
    mkdirSync(dirname(join(dir, rel)), { recursive: true });
    writeFileSync(join(dir, rel), text);
  };
  return { dir, run, write, done: () => rmSync(dir, { recursive: true, force: true }) };
}

const scope = (dir) => {
  const r = spawnSync(process.execPath, [SCOPE], { cwd: dir, encoding: 'utf8' });
  return { code: r.status, json: JSON.parse(r.stdout) };
};

test('AC-04: la orden real en un repositorio sin el clasificador propio usa el del engine', () => {
  const p = repo();
  try {
    p.write('server/tools/cobros.py', 'def total(lineas):\n    return 0\n');
    p.write('.claude/settings.json', JSON.stringify({ impact: { signature_globs: ['server/tools/*.py'] } }));
    p.run('add', '-A');
    p.run('commit', '-qm', 'base');
    p.run('switch', '-qc', 'fix/UC-13101-total');
    // Lo commiteado y lo añadido cuentan; la prueba no; lo nuevo sin añadir queda aparte.
    p.write('server/a.py', 'x = 1\n');
    p.run('add', 'server/a.py');
    p.run('commit', '-qm', 'a');
    p.write('server/b.py', 'y = 2\n');
    p.write('tests/test_total.py', 'def test_total():\n    assert False\n');
    p.run('add', 'server/b.py', 'tests/test_total.py');
    for (let i = 0; i < 6; i += 1) p.write(`doc/outcome/notas/n${i}.md`, 'nota\n');
    let r = scope(p.dir);
    assert.equal(r.code, 0);
    assert.equal(r.json.base, 'main');
    assert.deepEqual(r.json.files, ['server/a.py', 'server/b.py']);
    assert.equal(r.json.untracked.length, 6);
    assert.match(r.json.notice, /6 ficheros nuevos sin añadir no cuentan/);
    assert.equal(r.json.stop, false);
    // Cambiar la firma de una función pública de server/tools/*.py es un contrato (los `impact` de la base).
    p.write('server/tools/cobros.py', 'def total(lineas, moneda):\n    return 0\n');
    r = scope(p.dir);
    assert.equal(r.json.stop, true);
    assert.match(r.json.reasons.join(' '), /contrato de API: server\/tools\/cobros\.py \(firma de total\)/);
  } finally {
    p.done();
  }
});

test('sin rama base lo dice y cuenta solo lo pendiente', () => {
  const p = repo();
  try {
    p.run('switch', '-qc', 'trunk');
    p.write('a.py', 'x = 1\n');
    p.run('add', 'a.py');
    p.run('commit', '-qm', 'base');
    p.write('a.py', 'x = 2\n');
    const r = scope(p.dir);
    assert.equal(r.json.base, 'HEAD');
    assert.deepEqual(r.json.files, ['a.py']);
    assert.match(r.json.notice, /Sin rama base.*--base/);
  } finally {
    p.done();
  }
});

test('fuera de un repositorio git lo dice y sale con 2', () => {
  const dir = mkdtempSync(join(tmpdir(), 'fix-scope-nogit-'));
  try {
    const r = scope(dir);
    assert.equal(r.code, 2);
    assert.equal(r.json.error, 'not_a_git_repo');
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
