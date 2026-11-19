/**
 * UC-11103 / UC-11102 — the freeform-fragment hook on real files.
 *
 * PreToolUse puts the fragment in items_content and remembers what it sent;
 * PostToolUse merges what came back into doc/tracking/items.json and hides
 * items_content from the model. The server side and the equivalence of each
 * tool live in tests/test_freeform_fragment*.py.
 *
 * Ejecutar: node --test tests/hooks/freeform-fragment.test.mjs
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, utimesSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  FRAGMENT_FORMAT,
  asContext,
  extractItemsContent,
  mergeFragment,
  nextUcId,
  reservedNumbers,
  withLock,
  withoutItemsContent,
} from '../../.claude/hooks/lib/freeform-fragment.mjs';

const repoRoot = resolve(fileURLToPath(import.meta.url), '../../..');
const HOOK = join(repoRoot, '.claude/hooks/freeform-fragment.mjs');
const REMOTE = { SPECBOX_ENGINE_MCP_URL: 'https://mcp.example.test/mcp' };

const US = { id: 'item-us1', name: 'US-01: Pagos', description: 'larga', state: 'in_progress', parent_id: null, labels: ['US'], meta: { us_id: 'US-01', context: 'x' } };
const UC = { id: 'item-uc1', name: 'UC-007: Cobrar', description: 'larga', state: 'backlog', parent_id: 'item-us1', labels: ['UC'], meta: { uc_id: 'UC-007', us_id: 'US-01' } };
const AC = { id: 'ac-1', name: '[AC-01] Queda registrado', state: 'backlog', parent_id: 'item-uc1', labels: ['AC'], meta: { ac_id: 'AC-01' } };
const OTHER = { id: 'item-us2', name: 'US-02: Otra', description: 'otra', state: 'backlog', parent_id: null, labels: ['US'], meta: { us_id: 'US-02' } };

function project({ backend = 'freeform', items = [US, UC, AC, OTHER] } = {}) {
  const dir = mkdtempSync(join(tmpdir(), 'freeform-fragment-'));
  spawnSync('git', ['init', '-q'], { cwd: dir });
  const write = (rel, content) => {
    mkdirSync(dirname(join(dir, rel)), { recursive: true });
    writeFileSync(join(dir, rel), content);
  };
  write('.claude/settings.local.json', JSON.stringify({ specbox: { backend_type: backend } }));
  if (items) write('doc/tracking/items.json', `${JSON.stringify(items, null, 2)}\n`);
  return {
    dir,
    items: () => JSON.parse(readFileSync(join(dir, 'doc/tracking/items.json'), 'utf-8')),
    pending: () => (existsSync(join(dir, '.quality/freeform-fragments')) ? readdirSync(join(dir, '.quality/freeform-fragments')).filter((f) => f.endsWith('.json')) : []),
    done: () => rmSync(dir, { recursive: true, force: true }),
  };
}

function hook(p, event, tool, input, extra = {}, env = REMOTE) {
  const payload = { hook_event_name: event, tool_name: `mcp__SpecBox-MCP__${tool}`, tool_input: input, cwd: p.dir, ...extra };
  const res = spawnSync(process.execPath, [HOOK], { cwd: p.dir, input: JSON.stringify(payload), encoding: 'utf8', env: { ...process.env, ...env } });
  return { code: res.status, out: res.stdout ? JSON.parse(res.stdout) : null, stderr: res.stderr };
}

/** What the server would answer, as MCP content: the fragment with a new UC added under US-01. */
function serverAnswer(sentContent, newUc) {
  const fragment = JSON.parse(sentContent);
  fragment.items.push(newUc);
  fragment.max_ids.UC = Math.max(fragment.max_ids.UC, Number(newUc.meta.uc_id.slice(3)));
  const result = { uc_id: newUc.meta.uc_id, items_content: JSON.stringify(fragment) };
  return [{ type: 'text', text: JSON.stringify(result) }];
}

test('add_uc: Pre sends the parent story as context and the board maximum; Post merges and hides items_content', () => {
  const p = project();
  try {
    const pre = hook(p, 'PreToolUse', 'add_uc', { board_id: 'ff', us_id: 'US-01', name: 'Reembolsar' }, { tool_use_id: 'toolu_1' });
    assert.equal(pre.code, 0);
    const sent = JSON.parse(pre.out.hookSpecificOutput.updatedInput.items_content);
    assert.equal(sent.format, FRAGMENT_FORMAT);
    assert.deepEqual(sent.max_ids, { US: 2, UC: 7, EP: 0 });
    assert.deepEqual(sent.items.map((i) => i.id), ['item-us1']);
    assert.equal(sent.items[0].description, undefined); // context: no description, no meta.context
    assert.equal(sent.items[0].meta.context, undefined);
    assert.equal(pre.out.hookSpecificOutput.permissionDecision, undefined); // the user's permissions still apply
    assert.deepEqual(p.pending(), ['toolu_1.json']);

    const newUc = { id: 'item-uc2', name: 'UC-008: Reembolsar', state: 'backlog', parent_id: 'item-us1', labels: ['UC'], meta: { uc_id: 'UC-008' } };
    const response = serverAnswer(pre.out.hookSpecificOutput.updatedInput.items_content, newUc);
    const post = hook(p, 'PostToolUse', 'add_uc', {}, { tool_use_id: 'toolu_1', tool_response: response });
    assert.equal(post.code, 0, post.stderr);

    const board = p.items();
    assert.deepEqual(board.map((i) => i.id), ['item-us1', 'item-uc1', 'ac-1', 'item-us2', 'item-uc2']);
    assert.equal(board[0].description, 'larga'); // what did not travel stays
    assert.equal(board[0].meta.context, 'x');
    assert.equal(extractItemsContent(post.out.hookSpecificOutput.updatedToolOutput), null);
    assert.match(post.out.hookSpecificOutput.additionalContext, /\+1 elementos/);
    assert.deepEqual(p.pending(), []);
  } finally {
    p.done();
  }
});

test('two add_uc in flight: the second one counts the number the first reserved', () => {
  const p = project();
  try {
    const a = hook(p, 'PreToolUse', 'add_uc', { board_id: 'ff', us_id: 'US-01', name: 'A' }, { tool_use_id: 'toolu_a' });
    const b = hook(p, 'PreToolUse', 'add_uc', { board_id: 'ff', us_id: 'US-02', name: 'B' }, { tool_use_id: 'toolu_b' });
    const ua = JSON.parse(a.out.hookSpecificOutput.updatedInput.items_content).max_ids.UC;
    const ub = JSON.parse(b.out.hookSpecificOutput.updatedInput.items_content).max_ids.UC;
    assert.deepEqual([ua, ub], [7, 8]); // the server assigns UC-008 and UC-009
  } finally {
    p.done();
  }
});

test('get_uc: the UC and its criteria whole, the story as context; a read leaves the board as it was', () => {
  const p = project();
  try {
    const before = readFileSync(join(p.dir, 'doc/tracking/items.json'), 'utf-8');
    const pre = hook(p, 'PreToolUse', 'get_uc', { board_id: 'ff', uc_id: 'UC-007' }, { tool_use_id: 'toolu_r' });
    const sent = JSON.parse(pre.out.hookSpecificOutput.updatedInput.items_content);
    assert.deepEqual(sent.items.map((i) => i.id).sort(), ['ac-1', 'item-uc1', 'item-us1']);
    assert.equal(sent.items.find((i) => i.id === 'item-uc1').description, 'larga');
    const post = hook(p, 'PostToolUse', 'get_uc', {}, { tool_use_id: 'toolu_r', tool_response: [{ type: 'text', text: '{"uc_id":"UC-007"}' }] });
    assert.equal(post.code, 0);
    assert.equal(post.out, null);
    assert.equal(readFileSync(join(p.dir, 'doc/tracking/items.json'), 'utf-8'), before);
    assert.deepEqual(p.pending(), []);
  } finally {
    p.done();
  }
});

test('a tool without a fragment gets the whole items.json, written by the hook and not by the model', () => {
  const p = project();
  try {
    const pre = hook(p, 'PreToolUse', 'list_us', { board_id: 'ff' }, { tool_use_id: 'toolu_l' });
    assert.equal(pre.out.hookSpecificOutput.updatedInput.items_content, readFileSync(join(p.dir, 'doc/tracking/items.json'), 'utf-8'));
  } finally {
    p.done();
  }
});

test('it stays out of the way: not FreeForm, local MCP, explicit content, another server, no tool_use_id', () => {
  const native = project({ backend: 'native' });
  const local = project();
  try {
    assert.equal(hook(native, 'PreToolUse', 'add_uc', { us_id: 'US-01' }, { tool_use_id: 't' }).out, null);
    // A local MCP: no URL and no ~/.claude.json declaring a remote SpecBox-MCP.
    assert.equal(hook(local, 'PreToolUse', 'add_uc', { us_id: 'US-01' }, { tool_use_id: 't' }, { SPECBOX_ENGINE_MCP_URL: '', HOME: local.dir }).out, null);
    assert.equal(hook(local, 'PreToolUse', 'add_uc', { us_id: 'US-01', items_content: '[]' }, { tool_use_id: 't' }).out, null);
    assert.equal(hook(local, 'PreToolUse', 'add_uc', { us_id: 'US-01' }).out, null);
    const other = spawnSync(process.execPath, [HOOK], {
      cwd: local.dir, encoding: 'utf8', env: { ...process.env, ...REMOTE },
      input: JSON.stringify({ hook_event_name: 'PreToolUse', tool_name: 'mcp__github__add_uc', tool_input: {}, tool_use_id: 't', cwd: local.dir }),
    });
    assert.equal(other.stdout, '');
    assert.deepEqual(local.pending(), []);
  } finally {
    native.done();
    local.done();
  }
});

test('a merge that fails exits 2, says what was not saved and keeps what was sent', () => {
  const p = project();
  try {
    hook(p, 'PreToolUse', 'add_uc', { board_id: 'ff', us_id: 'US-01', name: 'X' }, { tool_use_id: 'toolu_x' });
    const post = hook(p, 'PostToolUse', 'add_uc', {}, { tool_use_id: 'toolu_x', tool_response: { items_content: '{"format":"x"}' } });
    assert.equal(post.code, 2);
    assert.match(post.stderr, /no se pudo guardar/);
    assert.deepEqual(p.pending(), ['toolu_x.json']);
    assert.equal(p.items().length, 4);
  } finally {
    p.done();
  }
});

// ── Pure pieces ────────────────────────────────────────────────────────

test('mergeFragment writes only the fields that changed, meta key by key, and removes what the tool removed', () => {
  const local = [{ ...US, meta: { ...US.meta, epic_id: 'EP-01' } }, UC, AC, OTHER];
  const sent = [asContext(US), UC, AC];
  const returned = [
    { ...asContext(US), state: 'review', meta: { us_id: 'US-01', done_at: 'now' } },
    { ...UC, state: 'review' },
  ];
  const merged = mergeFragment(local, sent, returned);
  assert.deepEqual(merged.map((i) => i.id), ['item-us1', 'item-uc1', 'item-us2']); // AC removed
  assert.equal(merged[0].state, 'review');
  assert.equal(merged[0].description, 'larga');
  assert.deepEqual(merged[0].meta, { us_id: 'US-01', context: 'x', epic_id: 'EP-01', done_at: 'now' });
  assert.equal(merged[1].state, 'review');
});

test('two criteria retired in parallel from the same UC keep both (UC-12501)', () => {
  const ac2 = { ...AC, id: 'item-ac2', name: '[AC-02] Segundo' };
  const local0 = [US, UC, AC, ac2];
  const sentA = [asContext(US), UC, AC, ac2];
  const sentB = [asContext(US), UC, AC, ac2];
  const retiredA = { id: 'AC-01', text: 'x', reason: 'la cubre otra historia', retired_at: 'a' };
  const retiredB = { id: 'AC-02', text: 'Segundo', reason: 'la cubre otra historia', retired_at: 'b' };
  const returnedA = [asContext(US), { ...UC, meta: { ...UC.meta, retired_criteria: [retiredA] } }, ac2];
  const returnedB = [asContext(US), { ...UC, meta: { ...UC.meta, retired_criteria: [retiredB] } }, AC];
  const afterA = mergeFragment(local0, sentA, returnedA);
  const afterB = mergeFragment(afterA, sentB, returnedB);
  const uc = afterB.find((i) => i.id === UC.id);
  assert.deepEqual(uc.meta.retired_criteria.map((r) => r.id), ['AC-01', 'AC-02']);
  assert.deepEqual(afterB.filter((i) => i.labels?.includes('AC')).map((i) => i.id), []);
});

test('items_content is found and removed in any response shape', () => {
  const inner = { uc_id: 'UC-1', items_content: '{"items":[]}' };
  for (const shape of [inner, [{ type: 'text', text: JSON.stringify(inner) }], { content: [{ type: 'text', text: JSON.stringify(inner) }], structuredContent: inner }]) {
    assert.equal(extractItemsContent(shape), '{"items":[]}');
    const clean = withoutItemsContent(shape);
    assert.equal(extractItemsContent(clean), null);
    assert.match(JSON.stringify(clean), /UC-1/);
  }
});

test('reservations expire after an hour and a stale lock is taken over', () => {
  const dir = mkdtempSync(join(tmpdir(), 'freeform-fragment-state-'));
  try {
    writeFileSync(join(dir, 'old.json'), JSON.stringify({ created_at: '2020-01-01T00:00:00Z', reserves: { UC: 99 } }));
    writeFileSync(join(dir, 'new.json'), JSON.stringify({ created_at: new Date().toISOString(), reserves: { UC: 12 } }));
    assert.deepEqual(reservedNumbers(dir), { UC: [12], EP: [] });
    assert.equal(existsSync(join(dir, 'old.json')), false);

    mkdirSync(join(dir, '.lock'));
    const old = new Date(Date.now() - 60_000);
    utimesSync(join(dir, '.lock'), old, old);
    assert.equal(withLock(dir, () => 'ok', { timeoutMs: 2000 }), 'ok');
    assert.equal(existsSync(join(dir, '.lock')), false);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

// UC-12214 — add_uc sigue la serie de la historia; el hook calcula el mismo id que el servidor.
test('nextUcId: the story series, the board maximum and the reserved numbers', () => {
  const story = (id, us) => ({ id: `item-${us}`, name: `${us}: H`, labels: ['US'], meta: { us_id: us } });
  const uc = (id, us) => ({ id: `item-${id}`, name: `${id}: C`, labels: ['UC'], parent_id: `item-${us}`, meta: { uc_id: id } });
  const items = [
    story('', 'US-122'), uc('UC-12201', 'US-122'), uc('UC-12213', 'US-122'),
    story('', 'US-128'), uc('UC-12801', 'US-128'),
    story('', 'US-01'), uc('UC-001', 'US-01'), uc('UC-050', 'US-01'),
  ];
  assert.deepEqual(nextUcId(items, 'US-122'), { id: 'UC-12214', number: 12214, numbering: 'story' });
  assert.deepEqual(nextUcId(items, 'US-122', [12214]), { id: 'UC-12215', number: 12215, numbering: 'story' });
  // US-01 no sigue la serie UC-01NN: el siguiente del tablero.
  assert.deepEqual(nextUcId(items, 'US-01'), { id: 'UC-12802', number: 12802, numbering: 'board' });
  assert.deepEqual(nextUcId(items, 'US-999'), { id: 'UC-12802', number: 12802, numbering: 'board' });
});

// UC-12212 — la política de EP-20 viaja en policy_content y vuelve a doc/tracking/policy.json.
test('policy tools: Pre sends policy.json and the git author; Post saves what set/skip return', () => {
  const p = project();
  try {
    spawnSync('git', ['config', 'user.name', 'Ana Prueba'], { cwd: p.dir });
    const policyPath = join(p.dir, 'doc/tracking/policy.json');
    // Sin fichero: llega vacío (el servidor lo trata como un tablero que ya existía).
    const read = hook(p, 'PreToolUse', 'get_enforcement_policy', {}, { tool_use_id: 'toolu_p0' });
    assert.equal(read.out.hookSpecificOutput.updatedInput.policy_content, '');
    assert.equal(read.out.hookSpecificOutput.updatedInput.actor, 'Ana Prueba');

    writeFileSync(policyPath, `${JSON.stringify({ schema: 1, origin: 'new', measures: {}, skips: [] })}\n`);
    const pre = hook(p, 'PreToolUse', 'set_enforcement_mode', { measure: 'spec_quality', mode: 'block' }, { tool_use_id: 'toolu_p1' });
    assert.equal(JSON.parse(pre.out.hookSpecificOutput.updatedInput.policy_content).origin, 'new');

    const changed = { schema: 1, origin: 'new', measures: { spec_quality: { mode: 'block', set_by: 'Ana Prueba' } }, skips: [] };
    const response = [{ type: 'text', text: JSON.stringify({ success: true, mode: 'block', policy_content: JSON.stringify(changed) }) }];
    const post = hook(p, 'PostToolUse', 'set_enforcement_mode', {}, { tool_use_id: 'toolu_p1', tool_response: response });
    assert.equal(post.code, 0, post.stderr);
    assert.deepEqual(JSON.parse(readFileSync(policyPath, 'utf-8')), changed);
    assert.ok(!JSON.stringify(post.out.hookSpecificOutput.updatedToolOutput).includes('policy_content'));
    assert.match(post.out.hookSpecificOutput.additionalContext, /policy\.json/);

    // Una lectura no escribe nada; con MCP local el hook no interviene.
    const readPost = hook(p, 'PostToolUse', 'get_enforcement_policy', {}, { tool_use_id: 'toolu_p2', tool_response: [{ type: 'text', text: JSON.stringify({ success: true, policy_content: '{"origin":"existing"}' }) }] });
    assert.equal(readPost.code, 0);
    assert.equal(JSON.parse(readFileSync(policyPath, 'utf-8')).origin, 'new');
    const local = hook(p, 'PreToolUse', 'get_enforcement_policy', {}, { tool_use_id: 'toolu_p3' }, { SPECBOX_ENGINE_MCP_URL: '', HOME: p.dir });
    assert.equal(local.out, null);
  } finally {
    p.done();
  }
});

test('setup_board of a new board writes the policy only when the project has none', () => {
  const p = project({ items: [] });
  try {
    const policyPath = join(p.dir, 'doc/tracking/policy.json');
    const answer = (origin) => [{ type: 'text', text: JSON.stringify({ board_id: 'ff-1', items_content: '[]', policy_content: JSON.stringify({ schema: 1, origin, measures: {}, skips: [] }) }) }];
    hook(p, 'PreToolUse', 'setup_board', { board_name: 'Nuevo' }, { tool_use_id: 'toolu_s1' });
    const post = hook(p, 'PostToolUse', 'setup_board', {}, { tool_use_id: 'toolu_s1', tool_response: answer('new') });
    assert.equal(post.code, 0, post.stderr);
    assert.equal(JSON.parse(readFileSync(policyPath, 'utf-8')).origin, 'new');
    assert.match(post.out.hookSpecificOutput.additionalContext, /con su política/);

    writeFileSync(policyPath, `${JSON.stringify({ schema: 1, origin: 'existing', measures: {}, skips: [] })}\n`);
    hook(p, 'PreToolUse', 'setup_board', { board_name: 'Otra vez' }, { tool_use_id: 'toolu_s2' });
    hook(p, 'PostToolUse', 'setup_board', {}, { tool_use_id: 'toolu_s2', tool_response: answer('new') });
    assert.equal(JSON.parse(readFileSync(policyPath, 'utf-8')).origin, 'existing');
  } finally {
    p.done();
  }
});

// UC-12213 — el informe recibe el tablero y los bloqueos; los eventos que vuelven se apuntan.
test('impact tools get items.json and the events; event_line is appended to enforcement_events.jsonl', () => {
  const p = project();
  try {
    const eventsPath = join(p.dir, 'doc/tracking/enforcement_events.jsonl');
    writeFileSync(eventsPath, '{"measure":"spec_quality","uc_id":"UC-007","outcome":"blocked","at":"2026-11-18T09:00:00+00:00"}\n');
    const pre = hook(p, 'PreToolUse', 'get_enforcement_impact', {}, { tool_use_id: 'toolu_i1' });
    const input = pre.out.hookSpecificOutput.updatedInput;
    assert.deepEqual(JSON.parse(input.board_content).map((i) => i.id), ['item-us1', 'item-uc1', 'ac-1', 'item-us2']);
    assert.match(input.events_content, /"outcome":"blocked"/);
    assert.equal(input.policy_content, '');

    const skipPre = hook(p, 'PreToolUse', 'skip_enforcement', { measure: 'spec_quality', uc_id: 'UC-007', reason: 'x' }, { tool_use_id: 'toolu_i2' });
    assert.equal(skipPre.out.hookSpecificOutput.updatedInput.board_content, undefined); // un salto no necesita el tablero

    const line = JSON.stringify({ measure: 'spec_quality', uc_id: 'UC-007', outcome: 'passed', at: '2026-11-18T10:00:00+00:00' });
    const post = hook(p, 'PostToolUse', 'record_enforcement_event', {}, {
      tool_use_id: 'toolu_i3',
      tool_response: [{ type: 'text', text: JSON.stringify({ success: true, recorded: true, event_line: line }) }],
    });
    assert.equal(post.code, 0, post.stderr);
    const lines = readFileSync(eventsPath, 'utf-8').trim().split('\n');
    assert.equal(lines.length, 2);
    assert.equal(JSON.parse(lines[1]).outcome, 'passed');
    assert.ok(!JSON.stringify(post.out.hookSpecificOutput.updatedToolOutput).includes('event_line'));
    assert.match(post.out.hookSpecificOutput.additionalContext, /enforcement_events\.jsonl/);
  } finally {
    p.done();
  }
});

// UC-12301 — start_uc detenido por spec_quality: el bloqueo se apunta y el tablero queda como estaba.
test('start_uc: a block is appended to the events, a spent skip saves the policy, both hidden from the model', () => {
  const p = project();
  try {
    const eventsPath = join(p.dir, 'doc/tracking/enforcement_events.jsonl');
    const policyPath = join(p.dir, 'doc/tracking/policy.json');
    const policy = { schema: 1, origin: 'new', measures: { spec_quality: { mode: 'block' } }, skips: [] };
    writeFileSync(policyPath, `${JSON.stringify(policy)}\n`);
    const before = readFileSync(join(p.dir, 'doc/tracking/items.json'), 'utf-8');

    const pre = hook(p, 'PreToolUse', 'start_uc', { board_id: 'ff', uc_id: 'UC-007' }, { tool_use_id: 'toolu_g1' });
    assert.equal(JSON.parse(pre.out.hookSpecificOutput.updatedInput.policy_content).measures.spec_quality.mode, 'block');

    const line = JSON.stringify({ measure: 'spec_quality', uc_id: 'UC-007', outcome: 'blocked', at: '2026-11-18T10:00:00+00:00', by: 'start_uc' });
    const blocked = { success: false, code: 'AC_QUALITY_BELOW_THRESHOLD', error: 'SpecBox detuvo la operación…', event_line: line };
    const post = hook(p, 'PostToolUse', 'start_uc', {}, { tool_use_id: 'toolu_g1', tool_response: [{ type: 'text', text: JSON.stringify(blocked) }] });
    assert.equal(post.code, 0, post.stderr);
    assert.equal(JSON.parse(readFileSync(eventsPath, 'utf-8').trim()).outcome, 'blocked');
    assert.equal(readFileSync(join(p.dir, 'doc/tracking/items.json'), 'utf-8'), before);
    const shown = JSON.stringify(post.out.hookSpecificOutput.updatedToolOutput);
    assert.ok(!shown.includes('event_line') && shown.includes('AC_QUALITY_BELOW_THRESHOLD'));
    assert.deepEqual(p.pending(), []);

    // Un salto gastado: start_uc arranca, el tablero se fusiona y la política vuelve sin el salto.
    hook(p, 'PreToolUse', 'start_uc', { board_id: 'ff', uc_id: 'UC-007' }, { tool_use_id: 'toolu_g2' });
    const fragment = JSON.parse(readdirSync(join(p.dir, '.quality/freeform-fragments')).length
      ? readFileSync(join(p.dir, '.quality/freeform-fragments', p.pending()[0]), 'utf-8') : '{}');
    const sent = fragment.sent ? fragment.sent.map((i) => (i.id === 'item-uc1' ? { ...i, state: 'in_progress' } : i)) : [];
    const spent = { ...policy, skips: [] };
    const started = { status: 'in_progress', items_content: JSON.stringify({ format: 'specbox-freeform-fragment/1', items: sent, max_ids: { US: 2, UC: 7, EP: 0 } }), policy_content: JSON.stringify(spent) };
    const post2 = hook(p, 'PostToolUse', 'start_uc', {}, { tool_use_id: 'toolu_g2', tool_response: [{ type: 'text', text: JSON.stringify(started) }] });
    assert.equal(post2.code, 0, post2.stderr);
    assert.deepEqual(JSON.parse(readFileSync(policyPath, 'utf-8')), spent);
    assert.equal(p.items().find((i) => i.id === 'item-uc1').state, 'in_progress');
    assert.ok(!JSON.stringify(post2.out.hookSpecificOutput.updatedToolOutput).includes('policy_content'));
    assert.match(post2.out.hookSpecificOutput.additionalContext, /policy\.json/);
  } finally {
    p.done();
  }
});

// UC-12401 — complete_uc lleva la política como start_uc; mark_ac lleva quién marcó.
test('complete_uc gets the policy and its block is saved; mark_ac and mark_ac_batch get the git author', () => {
  const p = project();
  try {
    const eventsPath = join(p.dir, 'doc/tracking/enforcement_events.jsonl');
    const policy = { schema: 1, origin: 'new', measures: { closing_evidence: { mode: 'block' } }, skips: [] };
    writeFileSync(join(p.dir, 'doc/tracking/policy.json'), `${JSON.stringify(policy)}\n`);
    const before = readFileSync(join(p.dir, 'doc/tracking/items.json'), 'utf-8');

    const pre = hook(p, 'PreToolUse', 'complete_uc', { board_id: 'ff', uc_id: 'UC-007' }, { tool_use_id: 'toolu_c1' });
    assert.equal(JSON.parse(pre.out.hookSpecificOutput.updatedInput.policy_content).measures.closing_evidence.mode, 'block');
    const line = JSON.stringify({ measure: 'closing_evidence', uc_id: 'UC-007', outcome: 'blocked', at: '2026-11-18T10:00:00+00:00', by: 'complete_uc' });
    const blocked = { success: false, code: 'AC_WITHOUT_PASSING_EVIDENCE', error: 'SpecBox detuvo la operación…', event_line: line };
    const post = hook(p, 'PostToolUse', 'complete_uc', {}, { tool_use_id: 'toolu_c1', tool_response: [{ type: 'text', text: JSON.stringify(blocked) }] });
    assert.equal(post.code, 0, post.stderr);
    assert.equal(JSON.parse(readFileSync(eventsPath, 'utf-8').trim()).measure, 'closing_evidence');
    assert.equal(readFileSync(join(p.dir, 'doc/tracking/items.json'), 'utf-8'), before);
    assert.ok(!JSON.stringify(post.out.hookSpecificOutput.updatedToolOutput).includes('event_line'));
    assert.deepEqual(p.pending(), []);

    spawnSync('git', ['config', 'user.name', 't'], { cwd: p.dir });
    for (const tool of ['mark_ac', 'mark_ac_batch']) {
      const marked = hook(p, 'PreToolUse', tool, { board_id: 'ff', uc_id: 'UC-007' }, { tool_use_id: `toolu_${tool}` });
      assert.equal(marked.out.hookSpecificOutput.updatedInput.marked_by, 't', tool);
      const given = hook(p, 'PreToolUse', tool, { board_id: 'ff', uc_id: 'UC-007', marked_by: 'Ana' }, { tool_use_id: `toolu_${tool}2` });
      assert.equal(given.out.hookSpecificOutput.updatedInput.marked_by, 'Ana', `${tool}: lo que manda el cliente gana`);
    }
    // UC-12501: who retired a criterion, kept with it in the UC's meta.
    const retired = hook(p, 'PreToolUse', 'delete_ac', { board_id: 'ff', uc_id: 'UC-007', ac_id: 'AC-01', reason: 'la cubre otra' }, { tool_use_id: 'toolu_del' });
    assert.equal(retired.out.hookSpecificOutput.updatedInput.retired_by, 't');
    assert.equal(retired.out.hookSpecificOutput.updatedInput.marked_by, undefined);
  } finally {
    p.done();
  }
});

// UC-12402 — start_uc y record_review_verdict llevan el contexto de Claude Code (este hook es el dueño).
test('start_uc and record_review_verdict get the Claude Code context, not what the model sent', () => {
  const p = project();
  try {
    for (const tool of ['start_uc', 'record_review_verdict']) {
      const pre = hook(p, 'PreToolUse', tool, { board_id: 'ff', uc_id: 'UC-007', client_session_id: 'del modelo' },
        { tool_use_id: `toolu_id_${tool}`, session_id: 'sess-1', agent_id: 'agent-9', agent_type: 'general-purpose' });
      const input = pre.out.hookSpecificOutput.updatedInput;
      assert.equal(input.client_session_id, 'sess-1', tool);
      assert.equal(input.client_agent_id, 'agent-9', tool);
      assert.equal(input.client_agent_type, 'general-purpose', tool);
      assert.equal(typeof input.items_content, 'string', tool);
    }
  } finally {
    p.done();
  }
});

test('UC-12603: closed_files no viaja en el contexto y dos cierres a la vez se suman', () => {
  const sibling = { id: 'uc2', name: 'UC-702', labels: ['UC'], state: 'done', meta: { uc_id: 'UC-702', closed_files: ['a.py'] } };
  assert.equal(asContext(sibling).meta.closed_files, undefined);
  const uc = { id: 'uc1', name: 'UC-701', labels: ['UC'], state: 'review', meta: { uc_id: 'UC-701' } };
  // En el disco ya hay lo de otro cierre; lo que vuelve trae lo de este: se juntan.
  const local = [{ ...uc, meta: { ...uc.meta, closed_files: ['otro.py'] } }];
  const returned = [{ ...uc, state: 'done', meta: { ...uc.meta, closed_files: ['este.py'] } }];
  const [merged] = mergeFragment(local, [uc], returned);
  assert.deepEqual(merged.meta.closed_files, ['otro.py', 'este.py']);
  assert.equal(merged.state, 'done');
});

test('UC-12603: las listas por repositorio se suman por repositorio y la unión respeta el tope', () => {
  const uc = { id: 'uc1', name: 'UC-701', labels: ['UC'], state: 'review', meta: { uc_id: 'UC-701' } };
  const local = [{ ...uc, meta: { ...uc.meta, closed_files_by_repo: { 'o/engine': ['a.py'] } } }];
  const returned = [{ ...uc, state: 'done', meta: { ...uc.meta, closed_files_by_repo: { 'o/cloud': ['x.tsx'] } } }];
  const [merged] = mergeFragment(local, [uc], returned);
  assert.deepEqual(merged.meta.closed_files_by_repo, { 'o/engine': ['a.py'], 'o/cloud': ['x.tsx'] });
  const full = Array.from({ length: 1000 }, (_, i) => `f${i}.py`);
  const [capped] = mergeFragment(
    [{ ...uc, meta: { ...uc.meta, closed_files: full } }],
    [uc],
    [{ ...uc, meta: { ...uc.meta, closed_files: ['nuevo.py'] } }],
  );
  assert.equal(capped.meta.closed_files.length, 1000);
  assert.equal(capped.meta.closed_files.at(-1), 'nuevo.py');
});

test('UC-12603: closed_files_by_repo tampoco viaja en el contexto', () => {
  const sibling = { id: 'uc2', name: 'UC-702', labels: ['UC'], state: 'done', meta: { uc_id: 'UC-702', closed_files_by_repo: { 'o/r': ['a.py'] } } };
  assert.equal(asContext(sibling).meta.closed_files_by_repo, undefined);
});
