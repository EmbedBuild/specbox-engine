/**
 * lib/freeform-fragment.mjs — FreeForm with the remote MCP, in fragments (UC-11103, UC-11102).
 *
 * In content mode every SpecBox tool used to travel with the whole
 * doc/tracking/items.json, written by the model and returned whole: ~103 KB
 * per call on a 134-item board. The freeform-fragment hook sends instead the
 * items the tool needs plus the highest US/UC/EP number of the whole board
 * (`specbox-freeform-fragment/1`), and merges what comes back into items.json.
 *
 * Pure functions (tested with node:test) plus a tiny file lock. A tool enters
 * FRAGMENT_TOOLS only with its equivalence test (tests/test_freeform_fragment_equivalence.py):
 * same answer and same board as with the whole items.json.
 */

import { mkdirSync, readdirSync, readFileSync, renameSync, rmSync, statSync, unlinkSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';

export const FRAGMENT_FORMAT = 'specbox-freeform-fragment/1';

/** The SpecBox tools that take the FreeForm board as `items_content` (server registry, checked by a test). */
export const CONTENT_TOOLS = new Set([
  'add_ac', 'add_epic', 'add_uc', 'attach_evidence', 'bulk_update_hours_from_description', 'complete_uc',
  'delete_ac', 'delete_epic', 'delete_uc', 'estimate_from_ac', 'find_next_uc', 'get_ac_status',
  'get_board_status', 'get_cross_repo_dependencies', 'get_delivery_report', 'get_epic', 'get_evidence',
  'get_satellite_queue', 'get_sprint_status', 'get_uc', 'get_us', 'get_us_progress', 'import_spec',
  'link_uc_parent', 'list_epics', 'list_uc', 'list_us', 'mark_ac', 'mark_ac_batch', 'move_uc', 'move_us',
  'set_ac_internal', 'set_ac_metadata', 'set_auth_token_placeholder', 'set_uc_satellite', 'set_us_epic',
  'setup_board', 'start_uc', 'sync_multirepo_state', 'update_ac', 'update_ac_batch', 'update_epic',
  'update_uc', 'update_uc_batch', 'update_us', 'validate_ac_quality',
].filter((t) => t !== 'set_auth_token_placeholder'));

/**
 * What each tool needs. `uc`: the UC, its criteria and, as context, its story;
 * `uc+siblings`: also the story's other UCs as context (a story's state is
 * derived from all of them); `story`: the story, its UCs and their criteria;
 * `parent-story`: only the story, as context; `epics`: every epic; `spec`: what
 * an import_spec names. Any other tool gets the whole board, as before.
 */
export const FRAGMENT_TOOLS = {
  add_uc: 'parent-story',
  add_ac: 'uc',
  update_ac: 'uc',
  delete_ac: 'uc',
  set_ac_metadata: 'uc',
  set_ac_internal: 'uc',
  get_ac_status: 'uc',
  get_uc: 'uc+siblings',
  start_uc: 'uc+siblings',
  mark_ac: 'uc+siblings',
  mark_ac_batch: 'uc+siblings',
  update_uc: 'uc+siblings',
  set_uc_satellite: 'uc+siblings',
  move_uc: 'uc+siblings',
  complete_uc: 'uc+siblings',
  get_us: 'story',
  move_us: 'story',
  update_us: 'story',
  import_spec: 'spec',
  add_epic: 'epics',
};

/** Calls that take the next number of a kind: an in-flight one reserves it (parallel calls). */
const RESERVES = { add_uc: 'UC', add_epic: 'EP' };

const KINDS = ['US', 'UC', 'EP'];
const CONTEXT_META_KEYS = ['context', 'comments', 'attachments'];
const PENDING_TTL_MS = 60 * 60 * 1000;

// ── Reading items ──────────────────────────────────────────────────────

export function parseToolName(name) {
  const m = /^mcp__(.+?)__([a-z_]+)$/.exec(name || '');
  if (!m || !/specbox/i.test(m[1])) return null;
  return { server: m[1], tool: m[2] };
}

function has(item, label) {
  return Array.isArray(item?.labels) && item.labels.includes(label);
}

/** The US-/UC-/AC-/EP- id of an item, or null. */
export function logicalId(item, kind) {
  if (!has(item, kind)) return null;
  if (kind === 'EP') return typeof item.id === 'string' ? item.id : null;
  const fromMeta = item.meta?.[`${kind.toLowerCase()}_id`];
  if (typeof fromMeta === 'string' && fromMeta) return fromMeta;
  const m = new RegExp(`^\\[?(${kind}-\\d+[a-z]?)`).exec(item.name || '');
  return m ? m[1] : null;
}

function idNumber(id, kind) {
  const m = new RegExp(`^${kind}-(\\d+)`).exec(id || '');
  return m ? Number(m[1]) : 0;
}

/** Highest US/UC/EP number on a board. */
export function maxIds(items) {
  const out = { US: 0, UC: 0, EP: 0 };
  for (const item of items) {
    for (const kind of KINDS) out[kind] = Math.max(out[kind], idNumber(logicalId(item, kind), kind));
  }
  return out;
}

// ── Choosing the fragment ──────────────────────────────────────────────

/**
 * `{full, context}` (sets of item ids) for a tool call, or null when the tool
 * gets the whole board.
 */
export function selectFragment(tool, args, items) {
  const shape = FRAGMENT_TOOLS[tool];
  if (!shape) return null;
  const full = new Set();
  const context = new Set();
  const byId = new Map(items.map((i) => [i.id, i]));
  const withId = (kind, id) => items.filter((i) => logicalId(i, kind) === id);
  const children = (parentId, label) => items.filter((i) => i.parent_id === parentId && has(i, label));
  const addUc = (uc) => {
    full.add(uc.id);
    for (const ac of children(uc.id, 'AC')) full.add(ac.id);
  };
  const addStory = (us) => {
    full.add(us.id);
    for (const uc of children(us.id, 'UC')) addUc(uc);
  };

  if (shape === 'parent-story') {
    for (const us of withId('US', args.us_id)) context.add(us.id);
  } else if (shape === 'uc' || shape === 'uc+siblings') {
    for (const uc of withId('UC', args.uc_id)) {
      addUc(uc);
      const story = byId.get(uc.parent_id);
      if (!story) continue;
      context.add(story.id);
      if (shape === 'uc+siblings') for (const sibling of children(story.id, 'UC')) context.add(sibling.id);
    }
  } else if (shape === 'story') {
    for (const us of withId('US', args.us_id)) addStory(us);
  } else if (shape === 'epics') {
    for (const ep of items.filter((i) => has(i, 'EP'))) full.add(ep.id);
  } else if (shape === 'spec') {
    const spec = typeof args.spec === 'string' ? safeJson(args.spec) : args.spec;
    for (const us of spec?.user_stories ?? []) {
      for (const item of withId('US', us?.us_id)) addStory(item);
      for (const uc of us?.use_cases ?? []) {
        for (const item of withId('UC', uc?.uc_id)) {
          addUc(item);
          const story = byId.get(item.parent_id);
          if (story) addStory(story);
        }
      }
    }
    for (const ep of items.filter((i) => has(i, 'EP'))) full.add(ep.id);
  }
  for (const id of full) context.delete(id);
  return { full, context };
}

function safeJson(text) {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

/** A context item travels without what no fragment tool reads (description, long meta). */
export function asContext(item) {
  const { description: _description, ...rest } = item;
  if (rest.meta && typeof rest.meta === 'object') {
    const meta = { ...rest.meta };
    for (const key of CONTEXT_META_KEYS) delete meta[key];
    rest.meta = meta;
  }
  return rest;
}

/**
 * The `items_content` to send and what to remember for the merge.
 * `reserved`: the numbers in-flight calls already took ({UC: [..], EP: [..]}).
 */
export function buildItemsContent({ tool, args, items, raw, reserved = {} }) {
  const selection = selectFragment(tool, args, items);
  if (!selection) return { itemsContent: raw, sent: items, whole: true, reserves: {} };
  const sent = items
    .filter((i) => selection.full.has(i.id) || selection.context.has(i.id))
    .map((i) => (selection.full.has(i.id) ? i : asContext(i)));
  const max = maxIds(items);
  for (const kind of KINDS) for (const n of reserved[kind] ?? []) max[kind] = Math.max(max[kind], n);
  const reserves = RESERVES[tool] ? { [RESERVES[tool]]: max[RESERVES[tool]] + 1 } : {};
  const itemsContent = JSON.stringify({ format: FRAGMENT_FORMAT, max_ids: max, items: sent });
  return { itemsContent, sent, whole: false, reserves };
}

// ── Merging what comes back ────────────────────────────────────────────

function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  if (value && typeof value === 'object') {
    return `{${Object.keys(value).sort().map((k) => `${JSON.stringify(k)}:${canonical(value[k])}`).join(',')}}`;
  }
  return JSON.stringify(value);
}

function same(a, b) {
  return canonical(a) === canonical(b);
}

function applyChanges(local, before, after) {
  const result = { ...local };
  for (const key of new Set([...Object.keys(before), ...Object.keys(after)])) {
    if (key === 'meta') continue;
    if (!(key in after)) delete result[key];
    else if (!(key in before) || !same(before[key], after[key])) result[key] = after[key];
  }
  if ('meta' in before || 'meta' in after) {
    const b = before.meta ?? {};
    const a = after.meta ?? {};
    const meta = { ...(local.meta ?? {}) };
    for (const key of new Set([...Object.keys(b), ...Object.keys(a)])) {
      if (!(key in a)) delete meta[key];
      else if (!(key in b) || !same(b[key], a[key])) meta[key] = a[key];
    }
    result.meta = meta;
  }
  return result;
}

/**
 * The local board after a call: each field the tool changed (compared with
 * what was sent) is written, items the tool removed are removed, new items are
 * added at the end. Fields that did not travel (a context item's description)
 * and items that did not travel stay as they are locally.
 */
export function mergeFragment(local, sent, returned) {
  const sentById = new Map(sent.map((i) => [i.id, i]));
  const returnedById = new Map(returned.map((i) => [i.id, i]));
  const localIds = new Set();
  const out = [];
  for (const item of local) {
    localIds.add(item.id);
    if (!sentById.has(item.id)) {
      out.push(item);
      continue;
    }
    const after = returnedById.get(item.id);
    if (after) out.push(applyChanges(item, sentById.get(item.id), after));
  }
  for (const item of returned) {
    if (!sentById.has(item.id) && !localIds.has(item.id)) out.push(item);
  }
  return out;
}

// ── The tool's answer ──────────────────────────────────────────────────

/** The `items_content` string inside an MCP tool response, whatever its shape. */
export function extractItemsContent(response, depth = 0) {
  if (depth > 6 || response == null) return null;
  if (typeof response === 'string') {
    const text = response.trim();
    return text.startsWith('{') ? extractItemsContent(safeJson(text), depth + 1) : null;
  }
  if (Array.isArray(response)) {
    for (const part of response) {
      const found = extractItemsContent(part, depth + 1);
      if (found != null) return found;
    }
    return null;
  }
  if (typeof response === 'object') {
    if (typeof response.items_content === 'string') return response.items_content;
    for (const value of Object.values(response)) {
      const found = extractItemsContent(value, depth + 1);
      if (found != null) return found;
    }
  }
  return null;
}

/** The same response without any `items_content` (what the model needs to see). */
export function withoutItemsContent(response, depth = 0) {
  if (depth > 6 || response == null) return response;
  if (typeof response === 'string') {
    const text = response.trim();
    if (!text.startsWith('{')) return response;
    const parsed = safeJson(text);
    if (parsed == null || extractItemsContent(parsed) == null) return response;
    return JSON.stringify(withoutItemsContent(parsed, depth + 1));
  }
  if (Array.isArray(response)) return response.map((part) => withoutItemsContent(part, depth + 1));
  if (typeof response === 'object') {
    const out = {};
    for (const [key, value] of Object.entries(response)) {
      if (key === 'items_content') continue;
      out[key] = withoutItemsContent(value, depth + 1);
    }
    return out;
  }
  return response;
}

// ── Files: pending calls, the lock and atomic writes ───────────────────

function sleep(ms) {
  Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms);
}

/** Run `fn` holding `<dir>/.lock` (a directory: mkdir is atomic). A lock older than 30 s is stale. */
export function withLock(dir, fn, { timeoutMs = 10_000, staleMs = 30_000 } = {}) {
  mkdirSync(dir, { recursive: true });
  const lock = join(dir, '.lock');
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    try {
      mkdirSync(lock);
      break;
    } catch (err) {
      if (err.code !== 'EEXIST') throw err;
      try {
        if (Date.now() - statSync(lock).mtimeMs > staleMs) rmSync(lock, { recursive: true, force: true });
      } catch {
        // gone in between: try again
      }
      if (Date.now() > deadline) throw new Error(`freeform-fragment: could not take ${lock}`);
      sleep(25);
    }
  }
  try {
    return fn();
  } finally {
    rmSync(lock, { recursive: true, force: true });
  }
}

export function writeAtomic(path, content) {
  mkdirSync(dirname(path), { recursive: true });
  const tmp = `${path}.${process.pid}.tmp`;
  writeFileSync(tmp, content, 'utf-8');
  renameSync(tmp, path);
}

export function pendingPath(dir, toolUseId) {
  return join(dir, `${String(toolUseId).replace(/[^A-Za-z0-9_-]/g, '_')}.json`);
}

/** The numbers reserved by calls still in flight; drops pending files older than an hour. */
export function reservedNumbers(dir, now = Date.now()) {
  const reserved = { UC: [], EP: [] };
  let names = [];
  try {
    names = readdirSync(dir).filter((n) => n.endsWith('.json'));
  } catch {
    return reserved;
  }
  for (const name of names) {
    const path = join(dir, name);
    const pending = safeJson(readOrNull(path));
    if (!pending || now - Date.parse(pending.created_at || 0) > PENDING_TTL_MS) {
      try {
        unlinkSync(path);
      } catch {
        // already gone
      }
      continue;
    }
    for (const [kind, n] of Object.entries(pending.reserves ?? {})) reserved[kind]?.push(n);
  }
  return reserved;
}

function readOrNull(path) {
  try {
    return readFileSync(path, 'utf-8');
  } catch {
    return null;
  }
}
