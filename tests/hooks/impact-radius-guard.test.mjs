/**
 * UC-12606 — el gobierno depende del radio de impacto del cambio real (medida impact_radius).
 *
 * El hook impact-radius-guard real sobre un repositorio con un tablero FreeForm:
 * - AC-01: clasifica el commit (contrato de API, migración de datos, dependencias o interno) y la
 *   clase va en su mensaje; las firmas de funciones públicas cuentan, su cuerpo no.
 * - AC-02: en «block», un contrato o una migración se detiene hasta que una persona lo aprueba
 *   (skip_enforcement en doc/tracking/policy.json); la aprobación se gasta en ese commit y vale
 *   para repetirlo si falló, pero no para el siguiente.
 * - AC-03: un cambio interno no pide aprobación y la clasificación queda en
 *   .quality/logs/impact-radius.jsonl con los ficheros que la decidieron.
 * - AC-04: en «warn» muestra la clase y deja seguir.
 * Ejecutar: node --test tests/hooks/impact-radius-guard.test.mjs
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { changedSignatures, classifyCommit, describe, globMatcher } from '../../.claude/hooks/lib/impact-radius.mjs';

const repoRoot = resolve(fileURLToPath(import.meta.url), '../../..');
const HOOK = join(repoRoot, '.claude/hooks/impact-radius-guard.mjs');
const SKIP = { measure: 'impact_radius', uc_id: 'UC-701', reason: 'La persona revisó la migración y la aprueba.', by: 'Ana', at: '2026-11-19T10:00:00+00:00' };

function write(dir, rel, content) {
  mkdirSync(dirname(join(dir, rel)), { recursive: true });
  writeFileSync(join(dir, rel), typeof content === 'string' ? content : JSON.stringify(content, null, 2));
}

function git(dir, ...args) {
  const r = spawnSync('git', args, { cwd: dir, encoding: 'utf8' });
  assert.equal(r.status, 0, r.stderr);
  return r.stdout.trim();
}

function project({ mode = 'block', skips = [], marker = true, settings = {} } = {}) {
  const dir = mkdtempSync(join(tmpdir(), 'impact-'));
  git(dir, 'init', '-q', '-b', 'main');
  git(dir, 'config', 'user.email', 't@t.t');
  git(dir, 'config', 'user.name', 't');
  write(dir, '.claude/settings.local.json', { specbox: { backend_type: 'freeform' } });
  write(dir, '.claude/settings.json', settings);
  write(dir, 'server/tools/x.py', 'async def get_uc(board_id: str, uc_id: str):\n    return 1\n');
  write(dir, 'server/a.py', 'x = 1\n');
  write(dir, '.gitignore', '.quality/\ndoc/tracking/\n');
  git(dir, 'add', '-A');
  git(dir, 'commit', '-q', '-m', 'base');
  git(dir, 'checkout', '-q', '-b', 'feat/UC-701-x');
  write(dir, 'doc/tracking/policy.json', {
    schema: 1, origin: 'existing', skips,
    measures: { impact_radius: { mode, ...(mode === 'block' ? { block_since: '2026-11-19T00:00:00+00:00' } : {}) } },
  });
  if (marker) write(dir, '.quality/active_uc.json', { uc_id: 'UC-701', board_id: 'ff-1', started_at: '2026-11-19T09:00:00+00:00' });
  return dir;
}

function commit(dir, command = 'git commit -m "UC-701: cambio"') {
  const r = spawnSync(process.execPath, [HOOK], {
    cwd: dir,
    input: JSON.stringify({ hook_event_name: 'PreToolUse', tool_name: 'Bash', tool_input: { command }, cwd: dir }),
    encoding: 'utf8',
    env: { ...process.env, SPECBOX_ENFORCEMENT_POLICY: 'off' },
  });
  let note = '';
  try { note = JSON.parse(r.stdout || '{}').hookSpecificOutput?.additionalContext || ''; } catch { /* sin nota */ }
  return { code: r.status, stderr: r.stderr, note };
}

function logLines(dir) {
  const path = join(dir, '.quality/logs/impact-radius.jsonl');
  return existsSync(path) ? readFileSync(path, 'utf8').trim().split('\n').map((l) => JSON.parse(l)) : [];
}

const policy = (dir) => JSON.parse(readFileSync(join(dir, 'doc/tracking/policy.json'), 'utf8'));

// ── El clasificador ──────────────────────────────────────────────────

test('AC-01: cada clase por sus ficheros, la mayor manda y dice qué ficheros la decidieron', () => {
  const cases = [
    [['server/a.py'], 'internal'],
    [['package.json', 'server/a.py'], 'dependencies'],
    [['requirements-dev.txt'], 'dependencies'],
    [['server/db/migrations/0041_x.sql'], 'data_migration'],
    [['db/seed.sql', 'package.json'], 'data_migration'],
    [['api/openapi.yaml', 'server/db/migrations/1.sql'], 'api_contract'],
    [['proto/cobros.proto'], 'api_contract'],
    [['web/schema.graphql'], 'api_contract'],
  ];
  for (const [files, cls] of cases) assert.equal(classifyCommit(files).class, cls, files.join(','));
  const r = classifyCommit(['src/rutas/cobros.ts'], { api_globs: ['src/rutas/**'] });
  assert.equal(r.class, 'api_contract');
  assert.equal(r.needs_approval, true);
  assert.match(describe(r), /^Radio de impacto: contrato de API — src\/rutas\/cobros\.ts \(fichero de contrato\)\.$/);
  assert.equal(classifyCommit(['infra/cambios/001.up'], { migration_globs: ['infra/cambios/*.up'] }).class, 'data_migration');
});

test('AC-01: en los ficheros de firmas cuenta un cambio en los parámetros de una función pública, no su cuerpo', () => {
  const cfg = { signature_globs: ['server/tools/*.py'] };
  const body = () => ({ before: 'def f(a):\n    return 1\n', after: 'def f(a):\n    return 2\n' });
  assert.equal(classifyCommit(['server/tools/x.py'], cfg, body).class, 'internal');
  const params = () => ({ before: 'async def get_uc(board_id: str):\n    pass\n', after: 'async def get_uc(board_id: str, plan: str = ""):\n    pass\n' });
  const r = classifyCommit(['server/tools/x.py'], cfg, params);
  assert.equal(r.class, 'api_contract');
  assert.match(describe(r), /firma de get_uc/);
  assert.deepEqual(changedSignatures('def _privada(a):\n  pass', 'def _privada(a, b):\n  pass'), []);
  assert.deepEqual(changedSignatures('', 'def nueva(a):\n  pass'), ['nueva']);
});

test('los globs del proyecto se comparan en tiempo lineal', () => {
  const start = Date.now();
  assert.equal(globMatcher(`${'*'.repeat(40)}z`)('a'.repeat(400)), false);
  assert.equal(globMatcher(`${'**/'.repeat(20)}x`)(`${'a/'.repeat(200)}y`), false);
  assert.ok(Date.now() - start < 500);
  assert.equal(globMatcher('docs')('docs/a/b.md'), true); // un nombre cubre la carpeta, como en .gitignore
  assert.equal(globMatcher('docs/*.md')('docs/a/b.md'), false);
  assert.equal(globMatcher('docs/')('docs/a/b.md'), true);
  assert.equal(globMatcher('/CHANGELOG.md')('a/CHANGELOG.md'), false);
});

// ── El hook ──────────────────────────────────────────────────────────

test('AC-03/AC-04: un cambio interno no pide aprobación ni en «block» y queda registrado con sus ficheros', () => {
  const dir = project({ mode: 'block' });
  try {
    write(dir, 'server/a.py', 'x = 2\n');
    git(dir, 'add', 'server/a.py');
    const r = commit(dir);
    assert.equal(r.code, 0);
    assert.match(r.note, /Radio de impacto: código interno — server\/a\.py/);
    const [line] = logLines(dir);
    assert.equal(line.class, 'internal');
    assert.equal(line.needs_approval, false);
    assert.equal(line.outcome, 'passed');
    assert.equal(line.uc_id, 'UC-701');
    assert.deepEqual(line.files, [{ path: 'server/a.py', why: 'código interno' }]);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test('AC-04: en «warn» una migración muestra su clase y deja seguir', () => {
  const dir = project({ mode: 'warn' });
  try {
    write(dir, 'server/db/migrations/0041_x.sql', 'ALTER TABLE a ADD b int;\n');
    const r = commit(dir, 'git add -A && git commit -m "UC-701: columna"');
    assert.equal(r.code, 0);
    assert.match(r.note, /migración de datos — server\/db\/migrations\/0041_x\.sql \(migración\)/);
    assert.match(r.note, /«warn»: el commit sigue/);
    assert.equal(logLines(dir)[0].outcome, 'noted');
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test('AC-02: en «block» una migración se detiene sin la aprobación de una persona, y el bloqueo queda en el tablero', () => {
  const dir = project({ mode: 'block' });
  try {
    write(dir, 'server/db/migrations/0041_x.sql', 'ALTER TABLE a ADD b int;\n');
    git(dir, 'add', '-A');
    const r = commit(dir);
    assert.equal(r.code, 2);
    assert.match(r.stderr, /COMMIT DETENIDO por la medida impact_radius/);
    assert.match(r.stderr, /migración de datos/);
    assert.match(r.stderr, /skip_enforcement\(measure="impact_radius", uc_id="UC-701"/);
    assert.match(r.stderr, /también en autopilot|cualquier nivel de autopilot/);
    assert.equal(logLines(dir)[0].outcome, 'blocked');
    const events = readFileSync(join(dir, 'doc/tracking/enforcement_events.jsonl'), 'utf8');
    assert.match(events, /"measure":"impact_radius","uc_id":"UC-701","outcome":"blocked"/);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test('AC-02: la firma de una tool cambiada es contrato de API y se detiene en «block»', () => {
  const dir = project({ mode: 'block', settings: { impact: { signature_globs: ['server/tools/*.py'] } } });
  try {
    write(dir, 'server/tools/x.py', 'async def get_uc(board_id: str, uc_id: str):\n    return 2\n');
    git(dir, 'add', '-A');
    assert.equal(commit(dir).code, 0); // solo el cuerpo: interno
    write(dir, 'server/tools/x.py', 'async def get_uc(board_id: str, uc_id: str, plan: str = ""):\n    return 2\n');
    git(dir, 'add', '-A');
    const r = commit(dir);
    assert.equal(r.code, 2);
    assert.match(r.stderr, /contrato de API — server\/tools\/x\.py \(firma de get_uc\)/);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test('AC-02: con la aprobación el commit sigue; vale para repetirlo si falló, no para el siguiente', () => {
  const dir = project({ mode: 'block', skips: [SKIP] });
  try {
    write(dir, 'server/db/migrations/0041_x.sql', 'ALTER TABLE a ADD b int;\n');
    git(dir, 'add', '-A');
    const first = commit(dir);
    assert.equal(first.code, 0);
    assert.match(first.note, /Aprobado por Ana .*La persona revisó la migración/);
    assert.deepEqual(policy(dir).skips, []); // gastada
    const [line] = logLines(dir);
    assert.equal(line.outcome, 'approved');
    assert.deepEqual(line.approval, { by: 'Ana', at: SKIP.at, reason: SKIP.reason, reused: false });
    // El commit falló (lint, por ejemplo) y se repite sin que HEAD cambie: la misma aprobación vale.
    const retry = commit(dir);
    assert.equal(retry.code, 0);
    assert.equal(logLines(dir)[1].approval.reused, true);
    // Hecho el commit, otra migración necesita otra aprobación.
    git(dir, 'commit', '-q', '-m', 'UC-701: columna');
    write(dir, 'server/db/migrations/0042_y.sql', 'ALTER TABLE a ADD c int;\n');
    git(dir, 'add', '-A');
    assert.equal(commit(dir).code, 2);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test('AC-02: sin UC activa no hay a quién aprobar y el commit se detiene; en «off» no clasifica', () => {
  const dir = project({ mode: 'block', marker: false });
  try {
    write(dir, 'api/openapi.yaml', 'openapi: 3.1.0\n');
    git(dir, 'add', '-A');
    const r = commit(dir);
    assert.equal(r.code, 2);
    assert.match(r.stderr, /No hay UC activa/);
    write(dir, 'doc/tracking/policy.json', { schema: 1, origin: 'existing', skips: [], measures: { impact_radius: { mode: 'off' } } });
    const off = commit(dir);
    assert.equal(off.code, 0);
    assert.equal(off.note, '');
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test('una orden que no es un commit no hace nada', () => {
  const dir = project({ mode: 'block' });
  try {
    const r = commit(dir, 'git status');
    assert.equal(r.code, 0);
    assert.equal(r.note, '');
    assert.deepEqual(logLines(dir), []);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
