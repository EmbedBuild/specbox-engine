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
