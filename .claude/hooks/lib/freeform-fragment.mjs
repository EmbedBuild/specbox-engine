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
  'add_ac', 'add_epic', 'add_uc', 'approve_criteria', 'attach_evidence', 'bulk_update_hours_from_description', 'complete_uc',
  'delete_ac', 'delete_epic', 'delete_uc', 'estimate_from_ac', 'find_next_uc', 'get_ac_status',
  'get_board_status', 'get_closed_uc_files', 'get_cross_repo_dependencies', 'get_delivery_report', 'get_epic', 'get_evidence',
  'get_satellite_queue', 'get_sprint_status', 'get_uc', 'get_us', 'get_us_progress', 'import_spec',
  'link_uc_parent', 'list_epics', 'list_uc', 'list_us', 'mark_ac', 'mark_ac_batch', 'move_uc', 'move_us',
  'record_review_verdict',
  'set_ac_internal', 'set_ac_metadata', 'set_auth_token_placeholder', 'set_uc_satellite', 'set_us_epic',
  'setup_board', 'start_uc', 'sync_multirepo_state', 'update_ac', 'update_ac_batch', 'update_epic',
  'update_uc', 'update_uc_batch', 'update_us', 'validate_ac_quality',
].filter((t) => t !== 'set_auth_token_placeholder'));

/**
 * What each tool needs. `uc`: the UC, its criteria and, as context, its story;
 * `uc+siblings`: also the story's other UCs as context (a story's state is
 * derived from all of them); `story`: the story, its UCs and their criteria;
 * `parent-story`: only the story, as context (add_uc also gets the ids of the story's
 * UCs as skeletons, UC-12214); `epics`: every epic; `spec`: what an import_spec
 * names. Any other tool gets the whole board, as before.
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
  record_review_verdict: 'uc+siblings',
  get_us: 'story',
  move_us: 'story',
  update_us: 'story',
  import_spec: 'spec',
  add_epic: 'epics',
};

/** Calls that take the next number of a kind: an in-flight one reserves it (parallel calls). */
const RESERVES = { add_uc: 'UC', add_epic: 'EP' };

const KINDS = ['US', 'UC', 'EP'];
// UC-12603: closed_files (los ficheros de la PR de una UC cerrada) tampoco viaja en el contexto.
const CONTEXT_META_KEYS = ['context', 'comments', 'attachments', 'closed_files'];
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

/**
 * UC-12214: a UC that only has to say who it is (add_uc numbering): its id, its story and its
 * parent. The merge compares what comes back with what was sent, so a skeleton the server leaves
 * alone changes nothing in items.json.
 */
export function asSkeleton(item) {
  const meta = {};
  for (const key of ['uc_id', 'us_id']) if (item.meta?.[key]) meta[key] = item.meta[key];
  return { id: item.id, name: item.name, labels: item.labels, parent_id: item.parent_id ?? null, meta };
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
  const max = maxIds(items);
  for (const kind of KINDS) for (const n of reserved[kind] ?? []) max[kind] = Math.max(max[kind], n);
  let reserves = RESERVES[tool] ? { [RESERVES[tool]]: max[RESERVES[tool]] + 1 } : {};
  const payload = { format: FRAGMENT_FORMAT, max_ids: max };

  // UC-12214: when the story follows its own series (UC-{story}{NN}), the server needs the ids of
  // the story's UCs to continue it; with correlative numbering the board maximum is enough. It
  // also gets the numbers parallel calls took and any UC elsewhere that already has the id it is
  // about to give, to refuse a conflict instead of creating a duplicate. They travel as skeletons,
  // and only when needed: the cost of creating a UC must not grow with the board (UC-11103).
  const skeletons = new Set();
  if (tool === 'add_uc') {
    const wanted = args?.uc_id || null;
    const next = wanted ? null : nextUcId(items, args?.us_id, reserved.UC ?? []);
    const id = wanted ?? next.id;
    const series = next?.numbering === 'story';
    const storyIds = new Set(items.filter((i) => logicalId(i, 'US') === args?.us_id).map((i) => i.id));
    for (const item of items) {
      const uc = logicalId(item, 'UC');
      if (!uc || selection.full.has(item.id)) continue;
      const sibling = storyIds.has(item.parent_id) || item.meta?.us_id === args?.us_id;
      if ((series && sibling) || uc === id) skeletons.add(item.id);
    }
    reserves = next ? { UC: next.number } : {};
    if ((reserved.UC ?? []).length) payload.reserved = { UC: [...reserved.UC] };
  }

  const sent = items
    .filter((i) => selection.full.has(i.id) || selection.context.has(i.id) || skeletons.has(i.id))
    .map((i) => (selection.full.has(i.id) ? i : skeletons.has(i.id) ? asSkeleton(i) : asContext(i)));
  payload.items = sent;
  const itemsContent = JSON.stringify(payload);
  return { itemsContent, sent, whole: false, reserves };
}

const STORY_NUMBER = /^US-(\d+)$/;

/**
 * UC-12214: the id add_uc gives a new UC — the same rule as the server (choose_uc_id).
 * When every UC of the story follows `UC-{story number}{NN}`, the next of that series;
 * otherwise the next number of the whole board. `reservedUc`: numbers in-flight calls took.
 */
export function nextUcId(items, usId, reservedUc = []) {
  const reserved = new Set(reservedUc);
  const byId = new Map(items.map((i) => [i.id, i]));
  const owners = new Map();
  for (const item of items) {
    const uc = logicalId(item, 'UC');
    if (!uc) continue;
    let owner = item.meta?.us_id || '';
    if (!owner) owner = logicalId(byId.get(item.parent_id), 'US') || '';
    owners.set(uc, owner);
  }
  const story = STORY_NUMBER.exec(usId || '');
  const siblings = [...owners].filter(([, owner]) => owner === usId).map(([uc]) => uc);
  if (story && siblings.length) {
    const series = new RegExp(`^UC-${story[1]}(\\d{2,})$`);
    const matches = siblings.map((uc) => series.exec(uc));
    if (matches.every(Boolean)) {
      const pad = (nn) => String(nn).padStart(2, '0');
      let nn = Math.max(...matches.map((m) => Number(m[1]))) + 1;
      while (reserved.has(Number(`${story[1]}${pad(nn)}`))) nn += 1;
      return { id: `UC-${story[1]}${pad(nn)}`, number: Number(`${story[1]}${pad(nn)}`), numbering: 'story' };
    }
  }
  const top = Math.max(0, ...[...owners.keys()].map((uc) => idNumber(uc, 'UC')), ...reserved);
  return { id: `UC-${String(top + 1).padStart(3, '0')}`, number: top + 1, numbering: 'board' };
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

/**
 * Meta lists that only grow and that two calls in parallel can both add to: when a call changes one,
 * its entries are joined by id with what is local, never replaced (UC-12501: two criteria retired at
 * the same time from the same UC keep both).
 */
const APPEND_ONLY_META = new Set(['retired_criteria']);
/** UC-12603: los ficheros de una UC cerrada se suman, no se sustituyen (dos cierres a la vez). */
const UNION_META = new Set(['closed_files']);

function unionValues(local, incoming) {
  return [...new Set([...(Array.isArray(local) ? local : []), ...(Array.isArray(incoming) ? incoming : [])])];
}

function unionById(local, incoming) {
  const out = Array.isArray(local) ? [...local] : [];
  const known = new Set(out.map((e) => e?.id));
  for (const entry of Array.isArray(incoming) ? incoming : []) {
    if (!known.has(entry?.id)) {
      out.push(entry);
      known.add(entry?.id);
    }
  }
  return out;
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
      else if (!(key in b) || !same(b[key], a[key])) {
        meta[key] = APPEND_ONLY_META.has(key)
          ? unionById(meta[key], a[key])
          : UNION_META.has(key)
            ? unionValues(meta[key], a[key])
            : a[key];
      }
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

/** The string field `key` inside an MCP tool response, whatever its shape. */
export function extractField(response, key, depth = 0) {
  if (depth > 6 || response == null) return null;
  if (typeof response === 'string') {
    const text = response.trim();
    return text.startsWith('{') ? extractField(safeJson(text), key, depth + 1) : null;
  }
  if (Array.isArray(response)) {
    for (const part of response) {
      const found = extractField(part, key, depth + 1);
      if (found != null) return found;
    }
    return null;
  }
  if (typeof response === 'object') {
    if (typeof response[key] === 'string') return response[key];
    for (const value of Object.values(response)) {
      const found = extractField(value, key, depth + 1);
      if (found != null) return found;
    }
  }
  return null;
}

/** The same response without any field in `keys` (what the model needs to see). */
export function withoutFields(response, keys, depth = 0) {
  if (depth > 6 || response == null) return response;
  if (typeof response === 'string') {
    const text = response.trim();
    if (!text.startsWith('{')) return response;
    const parsed = safeJson(text);
    if (parsed == null || keys.every((k) => extractField(parsed, k) == null)) return response;
    return JSON.stringify(withoutFields(parsed, keys, depth + 1));
  }
  if (Array.isArray(response)) return response.map((part) => withoutFields(part, keys, depth + 1));
  if (typeof response === 'object') {
    const out = {};
    for (const [key, value] of Object.entries(response)) {
      if (keys.includes(key)) continue;
      out[key] = withoutFields(value, keys, depth + 1);
    }
    return out;
  }
  return response;
}

/** The `items_content` string inside an MCP tool response, whatever its shape. */
export function extractItemsContent(response) {
  return extractField(response, 'items_content');
}

/** The same response without any `items_content` (nor `policy_content` or `event_line`, UC-12212/12213). */
export function withoutItemsContent(response) {
  return withoutFields(response, ['items_content', 'policy_content', 'event_line']);
}

// ── The EP-20 policy, doc/tracking/policy.json (UC-12212) ─────────────

/** The tools that read or change the policy: they get the file as `policy_content`. */
export const POLICY_TOOLS = new Set([
  'get_enforcement_policy', 'set_enforcement_mode', 'skip_enforcement',
  'get_enforcement_impact', 'record_enforcement_event',
]);
/** Of those, the ones whose answer is the new file. */
export const POLICY_WRITERS = new Set(['set_enforcement_mode', 'skip_enforcement']);
/** The ones that measure the board: they also get items.json and the events (UC-12213). */
export const POLICY_BOARD_TOOLS = new Set(['set_enforcement_mode', 'get_enforcement_impact']);
/** The ones whose answer carries an `event_line` for doc/tracking/enforcement_events.jsonl. */
export const POLICY_EVENT_TOOLS = new Set(['skip_enforcement', 'record_enforcement_event']);

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
