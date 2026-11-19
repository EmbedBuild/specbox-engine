/**
 * UC-12210 — el presupuesto de contexto se mide y puede bloquear.
 *
 * - AC-01: cada lanzamiento de subagente queda en .quality/logs/context-budget.jsonl con sus tokens y el modo.
 * - AC-02: en «block», un subagente que se pasa no se lanza y el mensaje da tamaño, presupuesto y cómo seguir.
 * - AC-03: la documentación dice el modo por defecto y cómo cambiarlo, y el guard sin configuración hace eso.
 * - AC-04: un ajuste del proyecto gana; sin él, manda la política del tablero (aquí, FreeForm policy.json).
 * Sin red: FreeForm lee doc/tracking/policy.json. Ejecutar: node --test tests/hooks/context-budget-policy.test.mjs
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { spawnWithStdin } from './_spawn-stdin.mjs';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = resolve(fileURLToPath(import.meta.url), '../../..');
const HOOK = join(repoRoot, '.claude/hooks/context-budget-guard.mjs');
const BIG = 'x'.repeat(80000); // ~20.000 tokens, por encima de 16.000
const SMALL = 'x'.repeat(400);

function project(files = {}) {
  const dir = mkdtempSync(join(tmpdir(), 'context-budget-'));
  for (const [rel, content] of Object.entries(files)) {
    mkdirSync(dirname(join(dir, rel)), { recursive: true });
    writeFileSync(join(dir, rel), typeof content === 'string' ? content : JSON.stringify(content));
  }
  return { dir, done: () => rmSync(dir, { recursive: true, force: true }) };
}

function launch(dir, prompt) {
  const r = spawnWithStdin(process.execPath, [HOOK], JSON.stringify({ tool_name: 'Agent', tool_input: { description: 'x', prompt } }), {
    cwd: dir,
    encoding: 'utf8',
    env: { ...process.env, SPECBOX_ENFORCEMENT_POLICY: 'off' },
  });
  let note = '';
  try { note = JSON.parse(r.stdout || '{}').hookSpecificOutput?.additionalContext || ''; } catch { /* sin nota */ }
  return { code: r.status, stderr: r.stderr, note };
}

const lines = (dir, rel) => (existsSync(join(dir, rel)) ? readFileSync(join(dir, rel), 'utf8').trim().split('\n').map((l) => JSON.parse(l)) : []);
const FREEFORM = { '.claude/settings.local.json': { specbox: { backend_type: 'freeform' } } };
const policy = (mode) => ({ 'doc/tracking/policy.json': { schema: 1, origin: 'new', measures: { context_budget: { mode } }, skips: [] } });

test('cada lanzamiento queda registrado con sus tokens y el modo aplicado (AC-01)', () => {
  const p = project();
  try {
    launch(p.dir, SMALL);
    launch(p.dir, BIG);
    const log = lines(p.dir, '.quality/logs/context-budget.jsonl');
    assert.equal(log.length, 2);
    assert.deepEqual(log.map((l) => [l.outcome, l.mode, l.budget]), [['under', 'warn', 16000], ['warned', 'warn', 16000]]);
    assert.ok(log[1].tokens > 16000 && log[0].tokens < 200);
    assert.equal(log[0].tool, 'Agent');
  } finally {
    p.done();
  }
});

test('en «block» por la política, un subagente que se pasa no se lanza y el mensaje dice por qué (AC-02)', () => {
  const p = project({ ...FREEFORM, ...policy('block') });
  try {
    const r = launch(p.dir, BIG);
    assert.equal(r.code, 2);
    for (const part of ['context_budget', 'tokens', 'el presupuesto es 16000', 'de más', 'Recorta el encargo', 'no se ha lanzado']) {
      assert.ok(r.stderr.includes(part), part);
    }
    assert.equal(launch(p.dir, SMALL).code, 0);
    assert.equal(lines(p.dir, '.quality/logs/context-budget.jsonl')[0].source, 'política (policy.json)');
  } finally {
    p.done();
  }
});

test('un ajuste del proyecto gana; el «warn» de la plantilla no cuenta como ajuste (AC-04)', () => {
  // Ajuste local: gana a la política.
  const local = project({ ...policy('block'), '.claude/settings.local.json': { specbox: { backend_type: 'freeform', implement: { task_isolation: { task_budget_mode: 'warn' } } } } });
  // El «warn» que escribe la plantilla en settings.json no tapa el «block» de la política.
  const plantilla = project({ ...FREEFORM, ...policy('block'), '.claude/settings.json': { implement: { task_isolation: { task_budget_tokens: 16000, task_budget_mode: 'warn' } } } });
  // Un valor cambiado en settings.json (el antiguo «strict») sí es un ajuste del proyecto.
  const cambiado = project({ ...FREEFORM, ...policy('warn'), '.claude/settings.json': { implement: { task_isolation: { task_budget_mode: 'strict' } } } });
  try {
    assert.equal(launch(local.dir, BIG).code, 0);
    assert.equal(launch(plantilla.dir, BIG).code, 2);
    assert.equal(launch(cambiado.dir, BIG).code, 2);
  } finally {
    local.done();
    plantilla.done();
    cambiado.done();
  }
});

test('sin configuración el guard avisa, como dice la documentación (AC-03)', () => {
  const p = project();
  try {
    const r = launch(p.dir, BIG);
    assert.equal(r.code, 0);
    assert.match(r.note, /medida context_budget en «warn»/);
  } finally {
    p.done();
  }
  const claude = readFileSync(join(repoRoot, 'CLAUDE.md'), 'utf8');
  const row = claude.split('\n').find((l) => l.startsWith('| context-budget-guard |'));
  assert.ok(row, 'la tabla de hooks de CLAUDE.md tiene la fila del guard');
  assert.match(row, /«warn» by default/);
  assert.match(row, /set_enforcement_mode\(measure="context_budget", mode="block"\)/);
});

test('un bloqueo y su corrección quedan en el registro del tablero FreeForm (UC-12213)', () => {
  const p = project({ ...FREEFORM, ...policy('block'), '.quality/active_uc.json': { uc_id: 'UC-7', feature: 'UC-7' } });
  try {
    assert.equal(launch(p.dir, BIG).code, 2);
    assert.equal(launch(p.dir, SMALL).code, 0);
    assert.equal(launch(p.dir, SMALL).code, 0); // ya corregido: no se repite
    const events = lines(p.dir, 'doc/tracking/enforcement_events.jsonl');
    assert.deepEqual(events.map((e) => [e.measure, e.uc_id, e.outcome]), [['context_budget', 'UC-7', 'blocked'], ['context_budget', 'UC-7', 'passed']]);
  } finally {
    p.done();
  }
});
