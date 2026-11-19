/**
 * UC-12801 AC-02 y AC-03 — los tres generadores de evidencia (API, Maestro y Patrol) llevan las citas
 * de cada prueba a results[].contract y enseñan el contrato en la tarjeta de cada criterio, con el
 * mismo contrato y el mismo bloque de código.
 * Ejecutar: node --test tests/hooks/evidence-generators-contract.test.mjs
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = resolve(fileURLToPath(import.meta.url), '../../..');
const SCRIPTS = join(repoRoot, '.quality/scripts');
const GENERATORS = ['api', 'maestro', 'patrol'].map((g) => join(SCRIPTS, `${g}-evidence-generator.js`));
const VALIDATOR = join(SCRIPTS, 'validate-results-json.js');

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
      post: [{ id: 'AC-02.post1', text: 'El total queda en 0,00 €' }],
      undefined: ['Qué pasa con una línea de importe negativo'],
    },
  },
};
const EXPECTED = [
  { id: 'AC-01', contract: { pre: ['AC-01.pre1'], post: ['AC-01.post1'] } },
  { id: 'AC-02', contract: { pre: ['AC-02.pre1'], post: ['AC-02.post1'] } },
];

const JUNIT = `<?xml version="1.0" encoding="UTF-8"?>
<testsuites><testsuite name="facturas" tests="2" failures="0">
  <testcase name="AC-01 total con dos líneas" classname="facturas" time="1.2"/>
  <testcase name="AC-02 factura sin líneas" classname="facturas" time="0.8"/>
</testsuite></testsuites>`;

function workspace(contract = CONTRACT) {
  const dir = mkdtempSync(join(tmpdir(), 'evidence-contract-'));
  const out = join(dir, 'acceptance');
  mkdirSync(out, { recursive: true });
  if (contract) writeFileSync(join(out, 'contract.json'), JSON.stringify(contract));
  // API (pytest-bdd): las citas van en las etiquetas del escenario.
  writeFileSync(join(dir, 'cucumber.json'), JSON.stringify([{ elements: [
    { name: 'AC-01 total con dos líneas', tags: [{ name: '@AC-01' }, { name: '@pre:AC-01.pre1' }, { name: '@post:AC-01.post1' }],
      steps: [{ keyword: 'Entonces ', name: 'el total es 120', result: { status: 'passed', duration: 1000000 } }] },
    { name: 'AC-02 factura sin líneas', tags: [{ name: '@AC-02' }, { name: '@pre:ac-2.PRE1' }, { name: '@post:AC-02.post1' }],
      steps: [{ keyword: 'Entonces ', name: 'el total es 0', result: { status: 'passed', duration: 1000000 } }] },
  ] }]));
  // Maestro: un comentario en la cabecera del flujo; uno por su nombre y otro solo por su criterio.
  mkdirSync(join(dir, '.maestro'));
  writeFileSync(join(dir, '.maestro/ac01.yaml'),
    '# contract: AC-01.pre1, AC-01.post1\nappId: com.acme\nname: AC-01 total con dos líneas\n---\n- launchApp\n');
  writeFileSync(join(dir, '.maestro/sin-lineas.yaml'),
    'appId: com.acme\n---\n# contract: AC-02.pre1\n# contract: AC-02.post1\n- launchApp\n');
  // Patrol: el comentario justo encima del test.
  mkdirSync(join(dir, 'patrol_test'));
  writeFileSync(join(dir, 'patrol_test/facturas_test.dart'), [
    "void main() {",
    "  // contract: AC-01.pre1, AC-01.post1",
    "  patrolTest('AC-01 total con dos líneas', (\\$) async {});",
    "  // contract: AC-02.pre1",
    "  // contract: AC-02.post1",
    "  patrolTest('AC-02 factura sin líneas', (\\$) async {});",
    "}",
  ].join('\n'));
  writeFileSync(join(dir, 'junit.xml'), JUNIT);
  return { dir, out, done: () => rmSync(dir, { recursive: true, force: true }) };
}

function generate(script, w) {
  const name = script.match(/(api|maestro|patrol)-evidence/)[1];
  const input = name === 'api' ? ['--cucumber', join(w.dir, 'cucumber.json')] : ['--junit', join(w.dir, 'junit.xml')];
  const r = spawnSync(process.execPath, [script, ...input, '--uc-id', 'UC-900', '--us-id', 'US-09',
    '--feature', 'facturas', '--screenshots', join(w.dir, 'nada'), '--output', join(w.out, 'e2e-evidence-report.html')],
  { cwd: w.dir, encoding: 'utf8' });
  assert.equal(r.status, 0, `${name}: ${r.stderr}`);
  return {
    results: JSON.parse(readFileSync(join(w.out, 'results.json'), 'utf8')),
    html: readFileSync(join(w.out, 'e2e-evidence-report.html'), 'utf8'),
  };
}

test('AC-02: los tres generadores llevan las citas de cada prueba a results[].contract', () => {
  for (const script of GENERATORS) {
    const w = workspace();
    try {
      const { results } = generate(script, w);
      assert.deepEqual(results.results.map((r) => ({ id: r.id, contract: r.contract })), EXPECTED, script);
      const check = spawnSync(process.execPath, [VALIDATOR, join(w.out, 'results.json'), '--check-contract',
        join(w.out, 'contract.json')], { encoding: 'utf8' });
      assert.equal(check.status, 0, `${script}: ${check.stdout}${check.stderr}`);
    } finally {
      w.done();
    }
  }
});

test('AC-03: el informe enseña el contrato junto al resultado de cada criterio', () => {
  for (const script of GENERATORS) {
    const w = workspace();
    try {
      const { html } = generate(script, w);
      assert.match(html, /<div class="contract"/, script);
      assert.match(html, /Hay una factura con dos líneas de 60,00 €/);
      assert.match(html, /Qué pasa con una línea de importe negativo/);
      assert.match(html, /<code>AC-01\.post1<\/code> El total queda en 120,00 € <strong title="comprobada por esta prueba">✓<\/strong>/);
    } finally {
      w.done();
    }
  }
});

test('AC-03: un criterio sin contrato lo dice en su tarjeta, y sin contract.json no hay bloque', () => {
  const partial = structuredClone(CONTRACT);
  delete partial.criteria['AC-02'];
  for (const script of GENERATORS) {
    let w = workspace(partial);
    try {
      assert.match(generate(script, w).html, /Sin contrato para este criterio/, script);
    } finally {
      w.done();
    }
    w = workspace(null);
    try {
      const { html, results } = generate(script, w);
      assert.doesNotMatch(html, /class="contract"/);
      // Las citas siguen en results.json: el validador las compara con el contrato cuando exista.
      assert.deepEqual(results.results.map((r) => ({ id: r.id, contract: r.contract })), EXPECTED);
    } finally {
      w.done();
    }
  }
});

test('un id «AC-1» encuentra su contrato y un flujo «AC-01» no se queda con «AC-010»', () => {
  const w = workspace();
  try {
    writeFileSync(join(w.dir, 'cucumber.json'), JSON.stringify([{ elements: [
      { name: 'Total', tags: [{ name: '@AC-1' }, { name: '@pre:AC-01.pre1' }, { name: '@post:AC-01.post1' }],
        steps: [{ keyword: 'Entonces ', name: 'ok', result: { status: 'passed', duration: 1 } }] },
    ] }]));
    const api = generate(GENERATORS[0], w);
    assert.doesNotMatch(api.html, /Sin contrato para este criterio/);
    assert.match(api.html, /Hay una factura con dos líneas de 60,00 €/);
    writeFileSync(join(w.dir, '.maestro/ac01.yaml'), '# contract: AC-01.pre1, AC-01.post1\nname: AC-01\n---\n- launchApp\n');
    rmSync(join(w.dir, '.maestro/sin-lineas.yaml'));
    writeFileSync(join(w.dir, 'junit.xml'), '<testsuite tests="1" failures="0"><testcase name="AC-010 otra cosa" classname="x" time="1"/></testsuite>');
    const maestro = generate(GENERATORS[1], w);
    assert.equal(maestro.results.results[0].contract, undefined);
  } finally {
    w.done();
  }
});

test('el bloque del contrato es el mismo en los tres generadores', () => {
  const blocks = GENERATORS.map((script) => {
    const text = readFileSync(script, 'utf8');
    const start = text.indexOf('// Contract (US-128 · UC-12801)');
    const end = text.indexOf('// --- end of the contract block ---');
    assert.ok(start > 0 && end > start, script);
    return text.slice(start, end);
  });
  assert.equal(blocks[1], blocks[0]);
  assert.equal(blocks[2], blocks[0]);
});
