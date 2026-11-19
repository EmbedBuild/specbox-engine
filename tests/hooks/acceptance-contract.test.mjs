/**
 * UC-12801 AC-01 y AC-02 — el contrato de cada criterio (`.claude/hooks/lib/acceptance-contract.mjs`)
 * y `validate-results-json.js --check-contract`. La paridad con el servidor está en
 * tests/test_acceptance_contract.py.
 * Ejecutar: node --test tests/hooks/acceptance-contract.test.mjs
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { copyFileSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  checkCitations, checkContract, contractReport, normalizeCondition, parseContract, parseResults,
} from '../../.claude/hooks/lib/acceptance-contract.mjs';

const repoRoot = resolve(fileURLToPath(import.meta.url), '../../..');
const VALIDATOR = join(repoRoot, '.quality/scripts/validate-results-json.js');

const CONTRACT = {
  schema: 1,
  uc_id: 'UC-900',
  criteria: {
    'AC-01': {
      pre: [{ id: 'AC-01.pre1', text: 'Hay una factura con dos líneas de 60,00 €' }],
      post: [{ id: 'AC-01.post1', text: 'El total queda en 120,00 €' }],
      undefined: [],
    },
    'AC-02': {
      pre: [{ id: 'AC-02.pre1', text: 'La factura no tiene líneas' }],
      post: [{ id: 'AC-02.post1', text: 'El total queda en 0,00 €' }, { id: 'AC-02.post2', text: 'No aparece ningún aviso' }],
      undefined: ['Qué pasa con una línea de importe negativo'],
    },
  },
};

const result = (id, scenario, contract) => ({
  id, scenario, status: 'PASS', duration_ms: 5, evidence: null, error: null, ...(contract ? { contract } : {}),
});
const run = (results) => ({
  feature: 'facturas', uc_id: 'UC-900', us_id: 'US-09', timestamp: '2026-11-19T10:00:00Z', source: 'pytest-bdd',
  stack: 'python', evidence_type: 'response-log', tests_total: results.length, tests_passed: results.length,
  tests_failed: 0, results,
});

test('normaliza los ids de las condiciones', () => {
  assert.deepEqual(normalizeCondition('ac-1.PRE01'), ['AC-01.pre1', 'AC-01', 'pre']);
  assert.equal(normalizeCondition('AC-01.post'), null);
  assert.equal(normalizeCondition(3), null);
});

test('AC-01: un contrato completo pasa y uno sin post ni undefined no', () => {
  const ok = contractReport({ contractContent: JSON.stringify(CONTRACT), criteriaIds: ['AC-01', 'AC-02'], ucId: 'UC-900' });
  assert.equal(ok.ok, true);
  const partial = structuredClone(CONTRACT);
  partial.criteria['AC-01'].post = [];
  delete partial.criteria['AC-01'].undefined;
  const contract = parseContract(JSON.stringify(partial));
  assert.deepEqual(checkContract(contract, ['AC-01', 'AC-02', 'AC-03']).incomplete,
    [{ ac_id: 'AC-01', missing: ['post', 'undefined'] }]);
  assert.deepEqual(checkContract(contract, ['AC-01', 'AC-02', 'AC-03']).missing, ['AC-03']);
});

test('AC-02: una prueba sin citas o con una condición de otro criterio no pasa', () => {
  const contract = parseContract(JSON.stringify(CONTRACT));
  const runs = parseResults(JSON.stringify(run([
    result('AC-01', 'Sin citas'),
    result('AC-02', 'Cita la de otro', { pre: ['AC-01.pre1'], post: ['AC-02.post1'] }),
  ])));
  const c = checkCitations(contract, runs);
  assert.deepEqual(c.uncited, [
    { ac_id: 'AC-01', test: 'Sin citas', missing: ['pre', 'post'] },
    { ac_id: 'AC-02', test: 'Cita la de otro', missing: ['pre'] },
  ]);
  assert.deepEqual(c.unknown.map((u) => u.problem), ['es de otro criterio (AC-01)']);
});

function workspace(results, contract = CONTRACT) {
  const dir = mkdtempSync(join(tmpdir(), 'acceptance-contract-'));
  const acceptance = join(dir, '.quality/evidence/facturas/acceptance');
  mkdirSync(acceptance, { recursive: true });
  writeFileSync(join(acceptance, 'results.json'), JSON.stringify(results));
  if (contract) writeFileSync(join(acceptance, 'contract.json'), JSON.stringify(contract));
  return { dir, results: join(acceptance, 'results.json'), contract: join(acceptance, 'contract.json') };
}

const validate = (args, env = {}) => {
  const r = spawnSync(process.execPath, args, { encoding: 'utf8', env: { ...process.env, ...env } });
  return { code: r.status, out: `${r.stdout}${r.stderr}` };
};

test('AC-02: --check-contract acepta pruebas que citan su pre y su post y avisa de lo no comprobado', () => {
  const w = workspace(run([
    result('AC-01', 'Total con dos líneas', { pre: ['AC-01.pre1'], post: ['AC-01.post1'] }),
    result('AC-02', 'Factura sin líneas', { pre: ['AC-02.pre1'], post: ['AC-02.post1'] }),
  ]));
  try {
    const r = validate([VALIDATOR, w.results, '--check-contract', w.contract]);
    assert.equal(r.code, 0, r.out);
    assert.match(r.out, /VALID/);
    assert.match(r.out, /Conditions no test checks: AC-02\.post2/);
  } finally {
    rmSync(w.dir, { recursive: true, force: true });
  }
});

test('AC-02: --check-contract falla con una prueba que no cita su contrato', () => {
  const w = workspace(run([
    result('AC-01', 'Total con dos líneas'),
    result('AC-02', 'Factura sin líneas', { pre: ['AC-02.pre1'], post: ['AC-02.post7'] }),
  ]));
  try {
    const r = validate([VALIDATOR, w.results, '--check-contract', w.contract]);
    assert.equal(r.code, 1);
    assert.match(r.out, /AC-01 «Total con dos líneas» does not cite its pre and post condition/);
    assert.match(r.out, /cites AC-02\.post7: no existe en el contrato/);
  } finally {
    rmSync(w.dir, { recursive: true, force: true });
  }
});

test('AC-01: --check-contract falla con un contrato incompleto o de otra UC', () => {
  const partial = structuredClone(CONTRACT);
  partial.uc_id = 'UC-901';
  delete partial.criteria['AC-02'].undefined;
  const w = workspace(run([result('AC-01', 'Total', { pre: ['AC-01.pre1'], post: ['AC-01.post1'] })]), partial);
  try {
    const r = validate([VALIDATOR, w.results, '--check-contract', w.contract]);
    assert.equal(r.code, 1);
    assert.match(r.out, /Contract AC-02: missing undefined/);
    assert.match(r.out, /Contract is for UC-901, results are for UC-900/);
  } finally {
    rmSync(w.dir, { recursive: true, force: true });
  }
});

test('un contract con otra forma no vale aunque no se pida --check-contract', () => {
  const w = workspace(run([result('AC-01', 'Total', 'AC-01.pre1')]), null);
  try {
    const r = validate([VALIDATOR, w.results]);
    assert.equal(r.code, 1);
    assert.match(r.out, /results\[0\]\.contract must be an object/);
  } finally {
    rmSync(w.dir, { recursive: true, force: true });
  }
});

test('--check-contract sin fichero, con un fichero que no existe o sin la librería lo dice', () => {
  const w = workspace(run([result('AC-01', 'Total', { pre: ['AC-01.pre1'], post: ['AC-01.post1'] })]));
  try {
    assert.equal(validate([VALIDATOR, w.results, '--check-contract']).code, 1);
    const missing = validate([VALIDATOR, w.results, '--check-contract', join(w.dir, 'no.json')]);
    assert.equal(missing.code, 1);
    assert.match(missing.out, /Contract not found/);
    // Un validador copiado a un proyecto sin los hooks de SpecBox no da por bueno lo que no puede mirar.
    const scripts = join(w.dir, '.quality/scripts');
    mkdirSync(scripts, { recursive: true });
    copyFileSync(VALIDATOR, join(scripts, 'validate-results-json.js'));
    const noLib = validate([join(scripts, 'validate-results-json.js'), w.results, '--check-contract', w.contract],
      { HOME: w.dir });
    assert.equal(noLib.code, 1);
    assert.match(noLib.out, /--check-contract needs \.claude\/hooks\/lib\/acceptance-contract\.mjs/);
  } finally {
    rmSync(w.dir, { recursive: true, force: true });
  }
});
