/**
 * UC-12605 — una spec viva por funcionalidad: el hook app-docs-fragment escribe el documento de
 * comportamiento y pone o quita la marca de PRD superado.
 *
 * - AC-01: tras complete_uc la sección de cada historia del PRD (sus UC cerradas con sus criterios)
 *   queda en doc/spec/<funcionalidad>.md; con FreeForm la calcula con items.json; se regenera, no se
 *   duplica; solo pide el bloque a un servidor 6.47.0 o posterior.
 * - AC-02: cuando todas las historias que define el PRD están sin nada pendiente y sus secciones son
 *   de ahora, el PRD queda superado, con la fecha y el documento; si una vuelve a tener trabajo
 *   (move_uc, add_uc), pierde la marca que puso el engine.
 * - AC-04: en un satélite multirepo el documento queda en el orquestador, junto a los PRD.
 * - Solo en la rama principal; el bloque no llega al modelo; nada fuera del canon ni por enlaces.
 * Ejecutar: node --test tests/hooks/behavior-doc.test.mjs
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  completeStoriesFromItems,
  featureOf,
  isSuperseded,
  markSuperseded,
  prdStories,
  replaceStorySection,
  sectionFromItems,
  unmarkSuperseded,
} from '../../.claude/hooks/lib/behavior-doc.mjs';
import { locatePrd, prdForUc } from '../../.claude/hooks/lib/prd-locate.mjs';
import { atLeast, CACHE_FILE, healthUrl, serverVersion } from '../../.claude/hooks/lib/server-version.mjs';

const repoRoot = resolve(fileURLToPath(import.meta.url), '../../..');
const HOOK = join(repoRoot, '.claude/hooks/app-docs-fragment.mjs');
/** Un MCP que no responde (puerto cerrado): las pruebas nunca salen a la red. */
const MCP_URL = 'http://127.0.0.1:9/mcp';

const PRD = '# PRD: Cobros\n\n<!-- @specbox:prd format="2" -->\n\n## US-01 — Cobrar\n\n### UC-001: Cobrar con tarjeta\n- [ ] **AC-01**: El cobro queda registrado\n';
const PRD2 = PRD.replace('### UC-001', '## US-02 — Devolver\n\n### UC-010: Devolver\n- [ ] **AC-01**: x\n\n### UC-001');
const MARK = '<!-- @specbox:prd status="superseded" date="2026-11-19" by="doc/spec/cobros.md" -->';
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

/** Un repo git en `branch` con `files`, y la versión del servidor en caché (null: sin caché). */
function repo(dir, branch, files = {}, version = '6.47.0') {
  mkdirSync(dir, { recursive: true });
  spawnSync('git', ['init', '-q', '-b', branch], { cwd: dir });
  for (const [rel, content] of Object.entries(files)) {
    mkdirSync(dirname(join(dir, rel)), { recursive: true });
    writeFileSync(join(dir, rel), typeof content === 'string' ? content : JSON.stringify(content));
  }
  if (version) serverIs(dir, version);
  return dir;
}

function serverIs(dir, version) {
  mkdirSync(join(dir, '.quality', 'logs'), { recursive: true });
  writeFileSync(join(dir, CACHE_FILE), JSON.stringify({ url: healthUrl(MCP_URL), version, at: Date.now() }));
}

function run(dir, event, toolInput, response, tool = 'complete_uc') {
  const payload = { hook_event_name: event, tool_name: `mcp__SpecBox-MCP__${tool}`, tool_input: toolInput, tool_response: response, cwd: dir };
  const r = spawnSync(process.execPath, [HOOK], {
    cwd: dir, input: JSON.stringify(payload), encoding: 'utf8', env: { ...process.env, SPECBOX_MCP_URL: MCP_URL },
  });
  return { code: r.status, out: r.stdout ? JSON.parse(r.stdout) : null, stderr: r.stderr };
}

const remote = (body) => [{ type: 'text', text: JSON.stringify(body) }];
const BLOCK = (complete = [], sections = { 'US-01': SECTION }) => ({
  ok: true, us_id: 'US-01', section: SECTION, sections, complete_stories: complete, date: '2026-11-19', spec_dir: 'doc/spec',
});
const read = (dir, rel) => readFileSync(join(dir, rel), 'utf-8');

function withDir(fn) {
  const base = mkdtempSync(join(tmpdir(), 'spec-doc-'));
  try {
    fn(base);
  } finally {
    rmSync(base, { recursive: true, force: true });
  }
}

test('AC-01: la sección de la historia queda en doc/spec/<funcionalidad>.md y no llega al modelo', () => withDir((base) => {
  const dir = repo(join(base, 'p'), 'main', { 'doc/prd/cobros/prd.md': PRD2 });
  // El marcador de UC activa da la historia; el PRD, las demás que define.
  writeFileSync(join(dir, '.quality/active_uc.json'), JSON.stringify({ uc_id: 'UC-001', us_id: 'US-01' }));
  const pre = run(dir, 'PreToolUse', { board_id: 'Acme/x', uc_id: 'UC-001' });
  assert.equal(pre.out.hookSpecificOutput.updatedInput.with_behavior_doc, true);
  assert.deepEqual(pre.out.hookSpecificOutput.updatedInput.behavior_doc_us_ids, ['US-01', 'US-02']);
  const r = run(dir, 'PostToolUse', { board_id: 'Acme/x', uc_id: 'UC-001' }, remote({ uc_id: 'UC-001', behavior_doc: BLOCK() }));
  assert.equal(r.code, 0);
  const doc = read(dir, 'doc/spec/cobros.md');
  assert.match(doc, /^# Comportamiento: cobros/);
  assert.match(doc, /### UC-001: Cobrar con tarjeta\n\n- \[x\] \*\*AC-01\*\*: El cobro queda registrado/);
  assert.ok(!JSON.stringify(r.out.hookSpecificOutput.updatedToolOutput).includes('behavior_doc'));
  // Se regenera: otro cierre sustituye la sección, no la duplica.
  run(dir, 'PostToolUse', { uc_id: 'UC-001' }, remote({ uc_id: 'UC-001', behavior_doc: BLOCK() }));
  assert.equal(read(dir, 'doc/spec/cobros.md').split('@specbox:spec us="US-01" start').length, 2);
  assert.equal(read(dir, 'doc/prd/cobros/prd.md'), PRD2); // historias sin cerrar: el PRD sigue vigente
}));

test('AC-01: sin marcador, el PRD que nombra la UC da las historias; un servidor anterior no recibe el parámetro', () => withDir((base) => {
  const dir = repo(join(base, 'p'), 'main', { 'doc/prd/cobros/prd.md': PRD2 });
  const pre = run(dir, 'PreToolUse', { uc_id: 'UC-010' });
  assert.deepEqual(pre.out.hookSpecificOutput.updatedInput.behavior_doc_us_ids, ['US-01', 'US-02']);
  serverIs(dir, '6.46.0');
  assert.equal(run(dir, 'PreToolUse', { uc_id: 'UC-010' }).out, null);
  // Sin caché y sin respuesta del servidor (puerto cerrado), tampoco.
  rmSync(join(dir, CACHE_FILE));
  assert.equal(run(dir, 'PreToolUse', { uc_id: 'UC-010' }).out, null);
}));

test('AC-02: con todas sus historias cerradas y sus secciones de ahora, el PRD queda superado', () => withDir((base) => {
  const dir = repo(join(base, 'p'), 'main', { 'doc/prd/cobros/prd.md': PRD });
  run(dir, 'PostToolUse', { uc_id: 'UC-002' }, remote({ uc_id: 'UC-002', behavior_doc: BLOCK(['US-01']) }));
  const prd = read(dir, 'doc/prd/cobros/prd.md');
  assert.match(prd, /<!-- @specbox:prd format="2" -->\n<!-- @specbox:prd status="superseded" date="2026-11-19" by="doc\/spec\/cobros.md" -->/);
  assert.equal(markSuperseded(prd, '2027-01-01', 'x'), prd); // la marca no se repite
  // Un PRD superado sigue siendo el de su historia.
  assert.equal(locatePrd({ root: dir, usId: 'US-01' }), 'doc/prd/cobros/prd.md');
}));

test('AC-02: un PRD de dos historias no queda superado si el documento no tiene las dos secciones de ahora', () => withDir((base) => {
  const dir = repo(join(base, 'p'), 'main', { 'doc/prd/cobros/prd.md': PRD2 });
  run(dir, 'PostToolUse', { uc_id: 'UC-001' }, remote({ uc_id: 'UC-001', behavior_doc: BLOCK(['US-01', 'US-02']) }));
  assert.equal(read(dir, 'doc/prd/cobros/prd.md'), PRD2);
  const both = { 'US-01': SECTION, 'US-02': SECTION.replaceAll('US-01', 'US-02') };
  run(dir, 'PostToolUse', { uc_id: 'UC-001' }, remote({ uc_id: 'UC-001', behavior_doc: BLOCK(['US-01', 'US-02'], both) }));
  assert.ok(isSuperseded(read(dir, 'doc/prd/cobros/prd.md')));
  assert.match(read(dir, 'doc/spec/cobros.md'), /us="US-02" start/);
}));

test('AC-02: si una historia vuelve a tener trabajo, el PRD pierde la marca que puso el engine', () => withDir((base) => {
  const marked = markSuperseded(PRD, '2026-11-19', 'doc/spec/cobros.md');
  const dir = repo(join(base, 'p'), 'main', { 'doc/prd/cobros/prd.md': marked, 'doc/spec/cobros.md': `# Comportamiento: cobros\n\n${SECTION}\n` });
  const pre = run(dir, 'PreToolUse', { us_id: 'US-01', name: 'Anular' }, undefined, 'add_uc');
  assert.equal(pre.out.hookSpecificOutput.updatedInput.with_behavior_doc, true);
  run(dir, 'PostToolUse', { us_id: 'US-01' }, remote({ uc_id: 'UC-003', behavior_doc: BLOCK([]) }), 'add_uc');
  assert.equal(read(dir, 'doc/prd/cobros/prd.md'), PRD);
  // Una marca puesta a mano (otro documento) se queda.
  const byHand = PRD.replace('<!-- @specbox:prd format="2" -->', `<!-- @specbox:prd format="2" -->\n${MARK.replace('cobros.md', 'otro.md')}`);
  writeFileSync(join(dir, 'doc/prd/cobros/prd.md'), byHand);
  run(dir, 'PostToolUse', { uc_id: 'UC-001', target: 'in_progress' }, remote({ uc_id: 'UC-001', behavior_doc: BLOCK([]) }), 'move_uc');
  assert.equal(read(dir, 'doc/prd/cobros/prd.md'), byHand);
}));

test('move_uc y add_uc no crean un documento nuevo; move_uc a «done» sí', () => withDir((base) => {
  const dir = repo(join(base, 'p'), 'main', { 'doc/prd/cobros/prd.md': PRD });
  run(dir, 'PostToolUse', { uc_id: 'UC-001', target: 'review' }, remote({ uc_id: 'UC-001', behavior_doc: BLOCK() }), 'move_uc');
  run(dir, 'PostToolUse', { us_id: 'US-01' }, remote({ uc_id: 'UC-003', behavior_doc: BLOCK() }), 'add_uc');
  assert.equal(existsSync(join(dir, 'doc/spec')), false);
  run(dir, 'PostToolUse', { uc_id: 'UC-001', target: 'done' }, remote({ uc_id: 'UC-001', behavior_doc: BLOCK() }), 'move_uc');
  assert.ok(existsSync(join(dir, 'doc/spec/cobros.md')));
}));

test('un PRD que no define la historia no recibe nada (el único fichero de doc/prds no basta)', () => withDir((base) => {
  const other = '# PRD: Avisos\n\n## US-07 — Avisar\n';
  const dir = repo(join(base, 'p'), 'main', { 'doc/prds/avisos.md': other });
  assert.equal(locatePrd({ root: dir, usId: 'US-01' }), 'doc/prds/avisos.md');
  run(dir, 'PostToolUse', { uc_id: 'UC-001' }, remote({ uc_id: 'UC-001', behavior_doc: BLOCK(['US-01']) }));
  assert.equal(existsSync(join(dir, 'doc/spec')), false);
  assert.equal(read(dir, 'doc/prds/avisos.md'), other);
}));

test('no escribe fuera del canon ni a través de un enlace simbólico', () => withDir((base) => {
  const outside = join(base, 'fuera');
  mkdirSync(outside, { recursive: true });
  const dir = repo(join(base, 'p'), 'main', { 'doc/prd/cobros/prd.md': PRD });
  mkdirSync(join(dir, 'doc'), { recursive: true });
  symlinkSync(outside, join(dir, 'doc/spec'));
  run(dir, 'PostToolUse', { uc_id: 'UC-002' }, remote({ uc_id: 'UC-002', behavior_doc: BLOCK(['US-01']) }));
  assert.equal(existsSync(join(outside, 'cobros.md')), false);
  assert.equal(read(dir, 'doc/prd/cobros/prd.md'), PRD); // sin documento, el PRD no se marca
}));

test('AC-04: en un satélite el documento queda en el orquestador, junto a los PRD', () => withDir((base) => {
  const orq = repo(join(base, 'manager'), 'main', { 'doc/prd/cobros/prd.md': PRD });
  const sat = repo(join(orq, 'repositorios', 'engine'), 'feature/UC-001-x', {
    '.claude/settings.local.json': { multirepo: { enabled: true, role: 'satellite', orchestrator: '../..' } },
  });
  const pre = run(sat, 'PreToolUse', { uc_id: 'UC-001' });
  assert.equal(pre.out.hookSpecificOutput.updatedInput.with_behavior_doc, true);
  run(sat, 'PostToolUse', { uc_id: 'UC-001' }, remote({ uc_id: 'UC-001', behavior_doc: BLOCK() }));
  assert.ok(existsSync(join(orq, 'doc/spec/cobros.md')));
  assert.equal(existsSync(join(sat, 'doc/spec')), false);
}));

test('en una rama de trabajo del canon no pide ni escribe el documento', () => withDir((base) => {
  const dir = repo(join(base, 'p'), 'feature/UC-001-x', { 'doc/prd/cobros/prd.md': PRD });
  assert.equal(run(dir, 'PreToolUse', { uc_id: 'UC-001' }).out, null);
  run(dir, 'PostToolUse', { uc_id: 'UC-001' }, remote({ uc_id: 'UC-001', behavior_doc: BLOCK(['US-01']) }));
  assert.equal(existsSync(join(dir, 'doc/spec')), false);
}));

test('AC-01/AC-02 FreeForm: el hook calcula las secciones y las historias completas con items.json', () => withDir((base) => {
  const dir = repo(join(base, 'p'), 'main', {
    'doc/prd/cobros/prd.md': PRD,
    '.claude/settings.local.json': { specbox: { backend_type: 'freeform' } },
    'doc/tracking/items.json': ITEMS('done'),
  });
  assert.equal(run(dir, 'PreToolUse', { uc_id: 'UC-002' }).out, null); // FreeForm no pide nada al servidor
  run(dir, 'PostToolUse', { uc_id: 'UC-002' }, remote({ uc_id: 'UC-002', completed_at: 'x' }));
  const doc = read(dir, 'doc/spec/cobros.md');
  assert.match(doc, /### UC-001: Cobrar con tarjeta/);
  assert.match(doc, /### UC-002: Devolver\n\n- \[x\] \*\*AC-01\*\*: La devolución queda registrada/);
  assert.match(read(dir, 'doc/prd/cobros/prd.md'), /status="superseded"/);
  // UC-002 vuelve a trabajo: la sección pierde la UC y el PRD, la marca.
  writeFileSync(join(dir, 'doc/tracking/items.json'), JSON.stringify(ITEMS('in_progress')));
  run(dir, 'PostToolUse', { uc_id: 'UC-002', target: 'in_progress' }, remote({ uc_id: 'UC-002' }), 'move_uc');
  assert.doesNotMatch(read(dir, 'doc/spec/cobros.md'), /UC-002/);
  assert.equal(read(dir, 'doc/prd/cobros/prd.md'), PRD);
}));

test('lib: la marca solo cuenta como línea propia de la cabecera, fuera de código', () => {
  const marked = markSuperseded(PRD, '2026-11-19', 'doc/spec/cobros.md');
  assert.ok(isSuperseded(marked));
  assert.equal(unmarkSuperseded(marked, 'doc/spec/cobros.md'), PRD);
  assert.equal(unmarkSuperseded(marked, 'doc/spec/otro.md'), marked);
  assert.equal(isSuperseded(`${PRD}\nLa marca:\n\n${MARK}\n`), false); // en el cuerpo
  assert.equal(isSuperseded(PRD.replace('\n\n## US-01', `\n\n\`\`\`\n${MARK}\n\`\`\`\n\n## US-01`)), false); // en código
  assert.equal(isSuperseded(PRD.replace('\n\n## US-01', `\n\nVa así: ${MARK}\n\n## US-01`)), false); // en una frase
  assert.deepEqual(prdStories('# PRD\n\n> US-01 y US-07\n\n```\n# US-99\n```\n## US-03\ncita US-44\n'), ['US-01', 'US-07', 'US-03']);
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

test('lib: el PRD de una UC y la versión del servidor', async () => withDirAsync(async (base) => {
  const dir = repo(join(base, 'p'), 'main', { 'doc/prd/cobros/prd.md': PRD2, 'doc/prd/otro/prd.md': '# PRD\n\n## US-09\n- [ ] UC-0101 y UC-01000 no cuentan\n' }, null);
  assert.equal(prdForUc(dir, 'UC-010'), 'doc/prd/cobros/prd.md');
  assert.equal(prdForUc(dir, 'UC-404'), null);
  assert.equal(prdForUc(dir, 'no'), null);
  assert.ok(atLeast('6.47.0', '6.47.0') && atLeast('6.48.1', '6.47.0') && atLeast('7.0.0', '6.47.0'));
  assert.ok(!atLeast('6.46.9', '6.47.0') && !atLeast(null, '6.47.0') && !atLeast('x', '6.47.0'));
  assert.equal(healthUrl('https://mcp.specbox.build/mcp'), 'https://mcp.specbox.build/health');
  let calls = 0;
  const fetchImpl = async () => {
    calls += 1;
    return { ok: true, json: async () => ({ status: 'ok', version: '6.47.0' }) };
  };
  const env = { SPECBOX_MCP_URL: 'https://mcp.example/mcp' };
  assert.equal(await serverVersion({ root: dir, env, fetchImpl, now: 1000 }), '6.47.0');
  assert.equal(await serverVersion({ root: dir, env, fetchImpl, now: 2000 }), '6.47.0');
  assert.equal(calls, 1); // la segunda sale de la caché
  assert.equal(await serverVersion({ root: dir, env, fetchImpl, now: 1000 + 11 * 60 * 1000 }), '6.47.0');
  assert.equal(calls, 2); // pasados 10 minutos se vuelve a preguntar
  const failing = async () => { throw new Error('sin red'); };
  assert.equal(await serverVersion({ root: dir, env: { SPECBOX_MCP_URL: 'https://otro/mcp' }, fetchImpl: failing, now: 5 }), null);
}));

async function withDirAsync(fn) {
  const base = mkdtempSync(join(tmpdir(), 'spec-doc-'));
  try {
    await fn(base);
  } finally {
    rmSync(base, { recursive: true, force: true });
  }
}
