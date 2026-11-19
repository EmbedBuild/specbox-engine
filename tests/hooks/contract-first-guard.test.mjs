/**
 * UC-12801 AC-03 y AC-06 — la medida contract_first: sin contrato no hay pruebas de aceptación.
 *
 * Los hooks reales sobre un repositorio con un tablero FreeForm:
 * - contract-first-guard, antes de escribir en una carpeta de aceptación: en «block» detiene la
 *   escritura de una UC sin contrato completo y lo registra en el tablero; en «warn» avisa y deja
 *   seguir; en «off» calla. No mira las UC de /fix ni lo que no es de aceptación; una UC anterior a
 *   la regla solo recibe la nota; con el contrato completo pasa y el bloqueo cuenta como corregido.
 * - e2e-gate, al hacer commit de pruebas o de evidencia: la misma medida, también con pruebas que no
 *   citan su contrato.
 * Ejecutar: node --test tests/hooks/contract-first-guard.test.mjs
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = resolve(fileURLToPath(import.meta.url), '../../..');
const GUARD = join(repoRoot, '.claude/hooks/contract-first-guard.mjs');
const GATE = join(repoRoot, '.claude/hooks/e2e-gate.mjs');

const CONTRACT = {
  schema: 1,
  uc_id: 'UC-701',
  criteria: {
    'AC-01': {
      pre: [{ id: 'AC-01.pre1', text: 'Hay una factura con dos líneas de 60,00 €' }],
      post: [{ id: 'AC-01.post1', text: 'El total queda en 120,00 €' }],
      undefined: [],
    },
    'AC-02': {
      pre: [{ id: 'AC-02.pre1', text: 'La factura no tiene líneas' }],
      post: [{ id: 'AC-02.post1', text: 'El total queda en 0,00 €' }],
      undefined: ['Qué pasa con una línea negativa'],
    },
  },
};

function write(dir, rel, content) {
  mkdirSync(dirname(join(dir, rel)), { recursive: true });
  writeFileSync(join(dir, rel), typeof content === 'string' ? content : JSON.stringify(content, null, 2));
}

function git(dir, ...args) {
  const r = spawnSync('git', args, { cwd: dir, encoding: 'utf8' });
  assert.equal(r.status, 0, r.stderr);
  return r.stdout.trim();
}

function project({ mode = 'block', marker = {}, contract = null } = {}) {
  const dir = mkdtempSync(join(tmpdir(), 'contract-first-'));
  git(dir, 'init', '-q', '-b', 'main');
  git(dir, 'config', 'user.email', 't@t.t');
  git(dir, 'config', 'user.name', 't');
  write(dir, '.claude/settings.local.json', { specbox: { backend_type: 'freeform' } });
  write(dir, 'README.md', 'x\n');
  git(dir, 'add', '-A');
  git(dir, 'commit', '-q', '-m', 'base');
  git(dir, 'checkout', '-q', '-b', 'feature/UC-701-total');
  write(dir, 'doc/tracking/policy.json', { schema: 1, origin: 'existing', skips: [], measures: { contract_first: { mode } } });
  write(dir, '.quality/active_uc.json', { uc_id: 'UC-701', feature: 'facturas', ac_ids: ['AC-01', 'AC-02'], ...marker });
  if (contract) write(dir, '.quality/evidence/facturas/acceptance/contract.json', contract);
  return dir;
}

function hook(script, dir, tool, toolInput) {
  const r = spawnSync(process.execPath, [script], {
    cwd: dir,
    input: JSON.stringify({ hook_event_name: 'PreToolUse', tool_name: tool, tool_input: toolInput, cwd: dir }),
    encoding: 'utf8',
    env: { ...process.env, SPECBOX_ENFORCEMENT_POLICY: 'off' },
  });
  let note = '';
  try { note = JSON.parse(r.stdout || '{}').hookSpecificOutput?.additionalContext || ''; } catch { /* sin nota */ }
  return { code: r.status, stderr: r.stderr, note, stdout: r.stdout };
}

const writeTest = (dir, rel = 'tests/acceptance/features/UC-701.feature') =>
  hook(GUARD, dir, 'Write', { file_path: join(dir, rel), content: '# language: es\n' });
const events = (dir) => {
  const path = join(dir, 'doc/tracking/enforcement_events.jsonl');
  return existsSync(path) ? readFileSync(path, 'utf8').trim().split('\n').map((l) => JSON.parse(l)) : [];
};

test('AC-03: en «block», una UC sin contrato no escribe pruebas de aceptación y queda en el tablero', () => {
  const dir = project();
  try {
    const r = writeTest(dir);
    assert.equal(r.code, 2);
    assert.match(r.stderr, /CONTRACT FIRST/);
    assert.match(r.stderr, /medida contract_first\. Motivo: UC-701 no tiene contrato \(\.quality\/evidence\/facturas\/acceptance\/contract\.json\)/);
    assert.match(r.stderr, /check_acceptance_contract/);
    assert.deepEqual(events(dir).map((e) => [e.measure, e.uc_id, e.outcome]), [['contract_first', 'UC-701', 'blocked']]);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test('AC-03: un contrato incompleto también detiene, y uno completo pasa y cuenta como corregido', () => {
  const partial = structuredClone(CONTRACT);
  delete partial.criteria['AC-02'];
  partial.criteria['AC-01'].post = [];
  const dir = project({ contract: partial });
  try {
    const r = writeTest(dir, 'e2e/acceptance/steps/total.steps.ts');
    assert.equal(r.code, 2);
    assert.match(r.stderr, /criterios sin contrato: AC-02; incompletos: AC-01 \(sin post\)/);
    write(dir, '.quality/evidence/facturas/acceptance/contract.json', CONTRACT);
    const ok = writeTest(dir, 'e2e/acceptance/steps/total.steps.ts');
    assert.equal(ok.code, 0);
    assert.equal(`${ok.stdout}${ok.stderr}`.trim(), '');
    assert.deepEqual(events(dir).map((e) => e.outcome), ['blocked', 'passed']);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test('AC-06: en «warn», la escritura sigue y la nota dice qué falta', () => {
  const dir = project({ mode: 'warn' });
  try {
    const r = hook(GUARD, dir, 'Edit', { file_path: join(dir, '.maestro/flows/AC-01.yaml'), old_string: 'a', new_string: 'b' });
    assert.equal(r.code, 0);
    assert.match(r.note, /Medida contract_first en «warn»: la escritura sigue\. Motivo: UC-701 no tiene contrato/);
    assert.deepEqual(events(dir), []);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test('en «off», con una UC de /fix o fuera de las carpetas de aceptación no dice nada', () => {
  for (const [opts, rel] of [
    [{ mode: 'off' }, 'tests/acceptance/x.feature'],
    [{ marker: { no_prd_reason: 'Arreglo con /fix: el total sale a cero' } }, 'tests/acceptance/x.feature'],
    [{}, 'tests/test_total.py'],
    [{}, 'src/acceptance/x.ts'],
  ]) {
    const dir = project(opts);
    try {
      const r = writeTest(dir, rel);
      assert.equal(r.code, 0, `${JSON.stringify(opts)} ${rel}`);
      assert.equal(`${r.stdout}${r.stderr}`.trim(), '', `${JSON.stringify(opts)} ${rel}`);
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  }
});

test('una UC anterior a la regla solo recibe la nota, aunque la medida esté en «block»', () => {
  const dir = project({ marker: { predates_rule: ['contract_first'] } });
  try {
    const r = writeTest(dir);
    assert.equal(r.code, 0);
    assert.match(r.note, /UC-701 es anterior a la regla: la escritura sigue/);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

// ── e2e-gate: la misma medida al hacer commit ─────────────────────────────────────────────────

const result = (id, contract) => ({
  id, scenario: `${id} escenario`, status: 'PASS', duration_ms: 3, evidence: null, error: null, ...(contract ? { contract } : {}),
});

function withEvidence(dir, results) {
  const out = '.quality/evidence/facturas/acceptance';
  write(dir, `${out}/results.json`, {
    feature: 'facturas', uc_id: 'UC-701', us_id: 'US-07', timestamp: '2026-11-19T10:00:00Z', source: 'pytest-bdd',
    stack: 'python', evidence_type: 'response-log', tests_total: results.length, tests_passed: results.length,
    tests_failed: 0, results,
  });
  write(dir, `${out}/e2e-evidence-report.html`,
    `<!DOCTYPE html><html><body>UC-701 Pass Rate AC-01 "status" ${'x'.repeat(1200)}</body></html>`);
  mkdirSync(join(dir, '.quality/scripts'), { recursive: true });
  copyFileSync(join(repoRoot, '.quality/scripts/validate-results-json.js'), join(dir, '.quality/scripts/validate-results-json.js'));
  git(dir, 'add', '-f', out);
}

const commit = (dir) => hook(GATE, dir, 'Bash', { command: 'git commit -m "UC-701: pruebas"' });

test('AC-03: e2e-gate detiene en «block» el commit de pruebas de aceptación sin contrato', () => {
  const dir = project();
  try {
    write(dir, 'tests/acceptance/features/UC-701.feature', '# language: es\n');
    git(dir, 'add', 'tests/acceptance/features/UC-701.feature');
    const r = commit(dir);
    assert.equal(r.code, 2);
    assert.match(r.stderr, /E2E GATE: pruebas de aceptación sin su contrato/);
    assert.match(r.stderr, /UC-701 no tiene contrato/);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test('AC-03: e2e-gate detiene la evidencia cuyas pruebas no citan su contrato y deja la que sí', () => {
  const dir = project({ contract: CONTRACT });
  try {
    withEvidence(dir, [result('AC-01'), result('AC-02', { pre: ['AC-02.pre1'], post: ['AC-02.post1'] })]);
    const r = commit(dir);
    assert.equal(r.code, 2, r.stderr);
    assert.match(r.stderr, /no citan el contrato: «AC-01 escenario» \(AC-01\) no cita su pre ni su post/);
    withEvidence(dir, [
      result('AC-01', { pre: ['AC-01.pre1'], post: ['AC-01.post1'] }),
      result('AC-02', { pre: ['AC-02.pre1'], post: ['AC-02.post1'] }),
    ]);
    const ok = commit(dir);
    assert.equal(ok.code, 0, ok.stderr);
    assert.equal(`${ok.stdout}${ok.stderr}`.trim(), '');
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test('AC-06: e2e-gate en «warn» deja el commit con la nota', () => {
  const dir = project({ mode: 'warn' });
  try {
    write(dir, 'tests/acceptance/features/UC-701.feature', '# language: es\n');
    git(dir, 'add', 'tests/acceptance/features/UC-701.feature');
    const r = commit(dir);
    assert.equal(r.code, 0);
    assert.match(r.note, /Medida contract_first en «warn»: el commit sigue/);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
