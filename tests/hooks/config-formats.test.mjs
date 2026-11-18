/**
 * UC-12215 — los hooks ven como spec-driven un proyecto con `specbox.backend_type`.
 *
 * - AC-01/AC-04: los tres formatos de configuración (claves en el primer nivel de settings.local.json,
 *   .claude/project-config.json aparte y el bloque `specbox`) quedan reconocidos.
 * - AC-02: un proyecto reconocido por primera vez (solo el bloque `specbox`) hace el commit en main
 *   con un aviso: commit_on_main está en «warn».
 * - AC-03: un proyecto que ya se reconocía conserva el bloqueo. Lo que puso una persona en la política
 *   manda en los dos casos.
 * Sin red: FreeForm lee doc/tracking/policy.json; native con SPECBOX_ENFORCEMENT_POLICY=off.
 * Ejecutar: node --test tests/hooks/config-formats.test.mjs
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = resolve(fileURLToPath(import.meta.url), '../../..');
const hooks = join(repoRoot, '.claude/hooks');
const ENV = { ...process.env, SPECBOX_ENFORCEMENT_POLICY: 'off', SPECBOX_RESERVATION_CHECK: 'off', SPECBOX_ENGINE_MCP_URL: '' };

function repo(files, branch = 'main') {
  const dir = mkdtempSync(join(tmpdir(), 'config-formats-'));
  spawnSync('git', ['init', '-q', '-b', branch], { cwd: dir });
  for (const [rel, content] of Object.entries(files)) {
    mkdirSync(dirname(join(dir, rel)), { recursive: true });
    writeFileSync(join(dir, rel), typeof content === 'string' ? content : JSON.stringify(content));
  }
  return { dir, done: () => rmSync(dir, { recursive: true, force: true }) };
}

function config(dir) {
  const code = `import('${join(hooks, 'lib/config.mjs')}').then((m) => process.stdout.write(JSON.stringify(m.getProjectConfig())))`;
  return JSON.parse(spawnSync(process.execPath, ['-e', code], { cwd: dir, encoding: 'utf8' }).stdout);
}

/** Lo que lee el agente: el texto del aviso (additionalContext) o el motivo del bloqueo. */
function readable(r) {
  try {
    return `${JSON.parse(r.stdout).hookSpecificOutput.additionalContext}${r.stderr}`;
  } catch {
    return `${r.stdout}${r.stderr}`;
  }
}

function commit(dir) {
  const payload = { hook_event_name: 'PreToolUse', tool_name: 'Bash', tool_input: { command: 'git commit -m x' }, cwd: dir };
  const r = spawnSync(process.execPath, [join(hooks, 'commit-spec-guard.mjs')], { cwd: dir, input: JSON.stringify(payload), encoding: 'utf8', env: ENV });
  return { code: r.status, out: readable(r) };
}

function write(dir) {
  const payload = { hook_event_name: 'PostToolUse', tool_name: 'Write', tool_input: { file_path: join(dir, 'src/app.ts') } };
  const r = spawnSync(process.execPath, [join(hooks, 'spec-guard.mjs')], { cwd: dir, input: JSON.stringify(payload), encoding: 'utf8', env: ENV });
  return { code: r.status, out: readable(r) };
}

const FORMATS = {
  'claves en el primer nivel': { '.claude/settings.local.json': { backend_type: 'native', board_id: 'Acme/web' } },
  'configuración de proyecto aparte': { '.claude/project-config.json': { boardId: 'Acme/web', backend_type: 'native' } },
  'bloque specbox': { '.claude/settings.local.json': { specbox: { backend_type: 'freeform', freeform_root_absolute: '' } } },
};

test('los tres formatos de configuración quedan reconocidos como spec-driven (AC-01, AC-04)', () => {
  for (const [label, files] of Object.entries(FORMATS)) {
    const p = repo(files);
    try {
      const c = config(p.dir);
      assert.equal(c.isSpecDriven, true, label);
      assert.equal(c.recognizedBy, label === 'bloque specbox' ? 'specbox' : 'legacy', label);
    } finally {
      p.done();
    }
  }
  const nada = repo({ '.claude/settings.local.json': { permissions: {} } });
  try {
    assert.equal(config(nada.dir).isSpecDriven, false);
  } finally {
    nada.done();
  }
});

test('reconocido por primera vez: el commit en main se hace con aviso (AC-02)', () => {
  const p = repo(FORMATS['bloque specbox']);
  try {
    const r = commit(p.dir);
    assert.equal(r.code, 0);
    assert.match(r.out, /Commit en main/);
    assert.match(r.out, /commit_on_main está en «warn»/);
    assert.match(r.out, /set_enforcement_mode\(measure="commit_on_main", mode="block"\)/);
    const w = write(p.dir);
    assert.equal(w.code, 0);
    assert.match(w.out, /commit_on_main está en «warn»/);
  } finally {
    p.done();
  }
  const nativo = repo({ '.claude/settings.local.json': { specbox: { backend_type: 'native' } } });
  try {
    assert.equal(commit(nativo.dir).code, 0);
  } finally {
    nativo.done();
  }
});

test('los proyectos que ya se reconocían conservan el bloqueo (AC-03)', () => {
  for (const label of ['claves en el primer nivel', 'configuración de proyecto aparte']) {
    const p = repo(FORMATS[label]);
    try {
      const r = commit(p.dir);
      assert.equal(r.code, 2, label);
      assert.match(r.out, /COMMIT BLOQUEADO: no se hace commit en main/, label);
      assert.equal(write(p.dir).code, 2, label);
    } finally {
      p.done();
    }
  }
});

test('lo que puso una persona en la política manda en los dos casos', () => {
  const policy = (mode) => ({ schema: 1, origin: 'existing', measures: { commit_on_main: { mode, set_by: 'Ana' } }, skips: [] });
  // Reconocido por primera vez, pero la persona pidió «block».
  const nuevo = repo({ ...FORMATS['bloque specbox'], 'doc/tracking/policy.json': policy('block') });
  // Reconocido de siempre (FreeForm), pero la persona pidió «warn».
  const viejo = repo({ '.claude/project-config.json': { backend_type: 'freeform' }, 'doc/tracking/policy.json': policy('warn') });
  try {
    assert.equal(commit(nuevo.dir).code, 2);
    const r = commit(viejo.dir);
    assert.equal(r.code, 0);
    assert.match(r.out, /«warn»/);
  } finally {
    nuevo.done();
    viejo.done();
  }
});
