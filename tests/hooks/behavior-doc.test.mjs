/**
 * UC-12605 — una spec viva por funcionalidad: el hook app-docs-fragment escribe el documento de
 * comportamiento y marca el PRD superado.
 *
 * - AC-01: tras complete_uc la sección de la historia (sus UC cerradas con sus criterios) queda en
 *   doc/spec/<funcionalidad>.md; con FreeForm la calcula con items.json; se regenera, no se duplica.
 * - AC-02: cuando todas las historias que define el PRD tienen sus UC cerradas, el PRD queda marcado
 *   como superado, con la fecha y el documento que lo sustituye.
 * - AC-04: en un satélite multirepo el documento queda en el orquestador, junto a los PRD.
 * - Solo en la rama principal; el bloque no llega al modelo; el localizador salta los superados.
 * Ejecutar: node --test tests/hooks/behavior-doc.test.mjs
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  completeStoriesFromItems,
  featureOf,
  markSuperseded,
  replaceStorySection,
  sectionFromItems,
} from '../../.claude/hooks/lib/behavior-doc.mjs';
import { locatePrd } from '../../.claude/hooks/lib/prd-locate.mjs';

const repoRoot = resolve(fileURLToPath(import.meta.url), '../../..');
const HOOK = join(repoRoot, '.claude/hooks/app-docs-fragment.mjs');

const PRD = '# PRD: Cobros\n\n<!-- @specbox:prd format="2" -->\n\n## US-01 — Cobrar\n\n### UC-001: Cobrar con tarjeta\n- [ ] **AC-01**: El cobro queda registrado\n';
const SECTION = [
  '<!-- @specbox:spec us="US-01" start -->',
  '## US-01 — Cobrar',
  '',
  '### UC-001: Cobrar con tarjeta',
  '',
  '- [x] **AC-01**: El cobro queda registrado',
  '',
  '<!-- @specbox:spec us="US-01" end -->',
].join('\n');

/** items.json de FreeForm: US-01 con UC-001 (hecha) y UC-002 (en `uc2state`). */
const ITEMS = (uc2state = 'backlog') => [
  { id: 'us1', name: 'US-01: Cobrar', labels: ['US'], state: 'in_progress', meta: { us_id: 'US-01' } },
  { id: 'uc1', name: 'UC-001: Cobrar con tarjeta', labels: ['UC'], state: 'done', parent_id: 'us1', meta: { uc_id: 'UC-001' } },
  { id: 'ac1', name: '[AC-01] El cobro queda registrado', labels: ['AC'], state: 'done', parent_id: 'uc1', meta: { ac_id: 'AC-01' } },
  { id: 'uc2', name: 'UC-002: Devolver', labels: ['UC'], state: uc2state, parent_id: 'us1', meta: { uc_id: 'UC-002' } },
  { id: 'ac2', name: '[AC-01] La devolución queda registrada', labels: ['AC'], state: uc2state === 'done' ? 'done' : 'backlog', parent_id: 'uc2', meta: { ac_id: 'AC-01' } },
];

function repo(dir, branch, files = {}) {
  mkdirSync(dir, { recursive: true });
  spawnSync('git', ['init', '-q', '-b', branch], { cwd: dir });
  for (const [rel, content] of Object.entries(files)) {
    mkdirSync(dirname(join(dir, rel)), { recursive: true });
    writeFileSync(join(dir, rel), typeof content === 'string' ? content : JSON.stringify(content));
  }
  return dir;
}

function run(dir, event, toolInput, response) {
  const payload = { hook_event_name: event, tool_name: 'mcp__SpecBox-MCP__complete_uc', tool_input: toolInput, tool_response: response, cwd: dir };
  const r = spawnSync(process.execPath, [HOOK], { cwd: dir, input: JSON.stringify(payload), encoding: 'utf8' });
  return { code: r.status, out: r.stdout ? JSON.parse(r.stdout) : null };
}

const remote = (body) => [{ type: 'text', text: JSON.stringify(body) }];
const BLOCK = (complete = []) => ({ ok: true, us_id: 'US-01', section: SECTION, complete_stories: complete, date: '2026-11-19', spec_dir: 'doc/spec' });

test('AC-01: la sección de la historia queda en doc/spec/<funcionalidad>.md y no llega al modelo', () => {
  const base = mkdtempSync(join(tmpdir(), 'spec-doc-'));
  try {
    const dir = repo(join(base, 'p'), 'main', { 'doc/prd/cobros/prd.md': PRD });
    const pre = run(dir, 'PreToolUse', { board_id: 'Acme/x', uc_id: 'UC-001' });
    assert.equal(pre.out.hookSpecificOutput.updatedInput.with_behavior_doc, true);
    const r = run(dir, 'PostToolUse', { board_id: 'Acme/x', uc_id: 'UC-001' }, remote({ uc_id: 'UC-001', behavior_doc: BLOCK() }));
    assert.equal(r.code, 0);
    const doc = readFileSync(join(dir, 'doc/spec/cobros.md'), 'utf-8');
    assert.match(doc, /^# Comportamiento: cobros/);
    assert.match(doc, /### UC-001: Cobrar con tarjeta\n\n- \[x\] \*\*AC-01\*\*: El cobro queda registrado/);
    assert.ok(!JSON.stringify(r.out.hookSpecificOutput.updatedToolOutput).includes('behavior_doc'));
    // Se regenera: otro cierre sustituye la sección, no la duplica.
    run(dir, 'PostToolUse', { uc_id: 'UC-001' }, remote({ uc_id: 'UC-001', behavior_doc: BLOCK() }));
    assert.equal(readFileSync(join(dir, 'doc/spec/cobros.md'), 'utf-8').split('@specbox:spec us="US-01" start').length, 2);
    assert.equal(readFileSync(join(dir, 'doc/prd/cobros/prd.md'), 'utf-8'), PRD); // historia sin cerrar: el PRD sigue vigente
  } finally {
    rmSync(base, { recursive: true, force: true });
  }
});

test('AC-02: con todas sus historias cerradas el PRD queda superado, con la fecha y el documento', () => {
  const base = mkdtempSync(join(tmpdir(), 'spec-doc-'));
  try {
    const dir = repo(join(base, 'p'), 'main', { 'doc/prd/cobros/prd.md': PRD });
    run(dir, 'PostToolUse', { uc_id: 'UC-002' }, remote({ uc_id: 'UC-002', behavior_doc: BLOCK(['US-01']) }));
    const prd = readFileSync(join(dir, 'doc/prd/cobros/prd.md'), 'utf-8');
    assert.match(prd, /<!-- @specbox:prd format="2" -->\n<!-- @specbox:prd status="superseded" date="2026-11-19" by="doc\/spec\/cobros.md" -->/);
    assert.equal(markSuperseded(prd, '2027-01-01', 'x'), prd); // la marca no se repite
    // El PRD superado ya no sale al buscar el de una historia nueva; el hook sí lo encuentra.
    assert.equal(locatePrd({ root: dir, usId: 'US-01' }), null);
    assert.equal(locatePrd({ root: dir, usId: 'US-01', includeSuperseded: true }), 'doc/prd/cobros/prd.md');
  } finally {
    rmSync(base, { recursive: true, force: true });
  }
});

test('AC-04: en un satélite el documento queda en el orquestador, junto a los PRD', () => {
  const base = mkdtempSync(join(tmpdir(), 'spec-doc-'));
  try {
    const orq = repo(join(base, 'manager'), 'main', { 'doc/prd/cobros/prd.md': PRD });
    const sat = repo(join(orq, 'repositorios', 'engine'), 'feature/UC-001-x', {
      '.claude/settings.local.json': { multirepo: { enabled: true, role: 'satellite', orchestrator: '../..' } },
    });
    const pre = run(sat, 'PreToolUse', { uc_id: 'UC-001' });
    assert.equal(pre.out.hookSpecificOutput.updatedInput.with_behavior_doc, true);
    run(sat, 'PostToolUse', { uc_id: 'UC-001' }, remote({ uc_id: 'UC-001', behavior_doc: BLOCK() }));
    assert.ok(existsSync(join(orq, 'doc/spec/cobros.md')));
    assert.equal(existsSync(join(sat, 'doc/spec')), false);
  } finally {
    rmSync(base, { recursive: true, force: true });
  }
});

test('en una rama de trabajo del canon no pide ni escribe el documento', () => {
  const base = mkdtempSync(join(tmpdir(), 'spec-doc-'));
  try {
    const dir = repo(join(base, 'p'), 'feature/UC-001-x', { 'doc/prd/cobros/prd.md': PRD });
    const pre = run(dir, 'PreToolUse', { uc_id: 'UC-001' });
    assert.equal(pre.out, null);
    run(dir, 'PostToolUse', { uc_id: 'UC-001' }, remote({ uc_id: 'UC-001', behavior_doc: BLOCK(['US-01']) }));
    assert.equal(existsSync(join(dir, 'doc/spec')), false);
  } finally {
    rmSync(base, { recursive: true, force: true });
  }
});

test('AC-01/AC-02 FreeForm: el hook calcula la sección y las historias completas con items.json', () => {
  const base = mkdtempSync(join(tmpdir(), 'spec-doc-'));
  try {
    const dir = repo(join(base, 'p'), 'main', {
      'doc/prd/cobros/prd.md': PRD,
      '.claude/settings.local.json': { specbox: { backend_type: 'freeform' } },
      'doc/tracking/items.json': ITEMS('done'),
    });
    assert.equal(run(dir, 'PreToolUse', { uc_id: 'UC-002' }).out, null); // FreeForm no pide nada al servidor
    run(dir, 'PostToolUse', { uc_id: 'UC-002' }, remote({ uc_id: 'UC-002', completed_at: 'x' }));
    const doc = readFileSync(join(dir, 'doc/spec/cobros.md'), 'utf-8');
    assert.match(doc, /### UC-001: Cobrar con tarjeta/);
    assert.match(doc, /### UC-002: Devolver\n\n- \[x\] \*\*AC-01\*\*: La devolución queda registrada/);
    assert.match(readFileSync(join(dir, 'doc/prd/cobros/prd.md'), 'utf-8'), /status="superseded"/);
  } finally {
    rmSync(base, { recursive: true, force: true });
  }
});

test('lib: la sección de FreeForm, las historias completas, la funcionalidad y la sustitución', () => {
  assert.equal(sectionFromItems(ITEMS(), 'UC-001').section, SECTION);
  assert.deepEqual(completeStoriesFromItems(ITEMS()), []);
  assert.deepEqual(completeStoriesFromItems(ITEMS('done')), ['US-01']);
  assert.deepEqual(completeStoriesFromItems(ITEMS('archived')), ['US-01']); // una UC sustituida no cuenta
  assert.equal(sectionFromItems(ITEMS(), 'UC-999'), null);
  assert.equal(featureOf('doc/prd/cobros/prd.md'), 'cobros');
  assert.equal(featureOf('doc/prds/us_01_prd.md'), 'us_01');
  const doc = replaceStorySection('', 'US-01', SECTION, 'cobros');
  const other = SECTION.replaceAll('US-01', 'US-02');
  const both = replaceStorySection(doc, 'US-02', other, 'cobros');
  assert.ok(both.indexOf('US-01') < both.indexOf('US-02'));
  assert.equal(replaceStorySection(both, 'US-01', SECTION, 'cobros'), both);
});
