#!/usr/bin/env node
/**
 * freeform-fragment.mjs — FreeForm with the remote MCP, without the whole board (UC-11103, UC-11102).
 *
 * PreToolUse (SpecBox tools that take `items_content`): in a FreeForm project
 * whose SpecBox MCP is remote, puts in `items_content` only the part of
 * doc/tracking/items.json the tool needs, with the highest US/UC/EP number of
 * the whole board (`specbox-freeform-fragment/1`); tools without a fragment get
 * the whole file. The model neither reads nor writes the board.
 *
 * PostToolUse: merges what the tool changed into items.json (field by field
 * against what was sent, under a lock, atomically) and hides `items_content`
 * from the answer the model sees.
 *
 * Never blocks a call: when it cannot act it stays silent and the call goes as
 * the model wrote it. A failed merge exits 2 with what was not saved; the
 * fragment stays in .quality/freeform-fragments/ for recovery.
 *
 * The EP-20 policy (UC-12212): the policy tools get doc/tracking/policy.json as
 * `policy_content` (and the git author as `actor`); what set_enforcement_mode and
 * skip_enforcement return is written back. A new board from setup_board writes
 * the policy only when the project has none. UC-12213: set_enforcement_mode and
 * get_enforcement_impact also get items.json (`board_content`) and the blocks
 * (`events_content`); the `event_line` of skip_enforcement and
 * record_enforcement_event is appended to doc/tracking/enforcement_events.jsonl.
 *
 * UC-12401: complete_uc gets the policy like start_uc (its measure is closing_evidence) and what
 * both return is saved the same way; mark_ac and mark_ac_batch get the git author as `marked_by`,
 * which FreeForm keeps with the verdict and the receipt of each criterion. UC-12501: delete_ac gets
 * it as `retired_by`, kept with the retired criterion in the UC's meta.
 *
 * UC-12402: start_uc and record_review_verdict get the Claude Code context (lib/agent-identity.mjs);
 * the agent-identity hook leaves these calls to this one.
 */

import { execFileSync } from 'node:child_process';
import { appendFileSync, existsSync, mkdirSync, readFileSync, unlinkSync } from 'node:fs';
import { dirname, isAbsolute, join } from 'node:path';
import { isRemoteMcp } from './lib/freeform-path.mjs';
import {
  CONTENT_TOOLS,
  POLICY_BOARD_TOOLS,
  POLICY_EVENT_TOOLS,
  POLICY_TOOLS,
  POLICY_WRITERS,
  buildItemsContent,
  extractField,
  extractItemsContent,
  mergeFragment,
  parseToolName,
  pendingPath,
  reservedNumbers,
  withLock,
  withoutItemsContent,
  writeAtomic,
} from './lib/freeform-fragment.mjs';
import { readHookInput } from './lib/utils.mjs';
import { IDENTITY_TOOLS, identityFields } from './lib/agent-identity.mjs';

/**
 * The tools whose measures read the board's policy and may record a block (UC-12301, UC-12401);
 * find_next_uc reads it to skip or reorder UCs whose criteria are not approved (UC-12502).
 */
const GATE_TOOLS = new Set(['start_uc', 'complete_uc', 'find_next_uc']);
/**
 * The tools whose author FreeForm keeps, and the argument it goes in: who marked a criterion
 * (UC-12401), who retired one (UC-12501) and who approved a UC's criteria (UC-12502).
 */
const AUTHOR_ARGS = {
  mark_ac: 'marked_by', mark_ac_batch: 'marked_by', delete_ac: 'retired_by', approve_criteria: 'approved_by',
};

const { event, toolName, toolInput, cwd, payload } = readHookInput();
const parsed = parseToolName(toolName);
const isPolicyTool = !!parsed && POLICY_TOOLS.has(parsed.tool);
if (!parsed || !(CONTENT_TOOLS.has(parsed.tool) || isPolicyTool) || !payload.tool_use_id) process.exit(0);

const root = (() => {
  try {
    return execFileSync('git', ['-C', cwd, 'rev-parse', '--show-toplevel'], {
      encoding: 'utf-8',
      stdio: ['ignore', 'pipe', 'ignore'],
    }).trim() || cwd;
  } catch {
    return cwd;
  }
})();
const settings = readJson(join(root, '.claude', 'settings.local.json'))?.specbox ?? {};
if (settings.backend_type !== 'freeform' || !isRemoteMcp({ cwd: root })) process.exit(0);

const trackingDir =
  typeof settings.freeform_root_absolute === 'string' && isAbsolute(settings.freeform_root_absolute)
    ? settings.freeform_root_absolute
    : join(root, 'doc', 'tracking');
const itemsPath = join(trackingDir, 'items.json');
const policyPath = join(trackingDir, 'policy.json');
const eventsPath = join(trackingDir, 'enforcement_events.jsonl');
const stateDir = join(root, '.quality', 'freeform-fragments');
const pending = pendingPath(stateDir, payload.tool_use_id);

if (isPolicyTool) {
  if (event === 'PreToolUse') prePolicy();
  else if (event === 'PostToolUse') postPolicy();
  process.exit(0);
}
if (event === 'PreToolUse') pre();
else if (event === 'PostToolUse') post();
process.exit(0);

function gitAuthor() {
  try {
    return execFileSync('git', ['-C', root, 'config', 'user.name'], {
      encoding: 'utf-8',
      stdio: ['ignore', 'pipe', 'ignore'],
    }).trim();
  } catch {
    return '';
  }
}

function prePolicy() {
  if (typeof toolInput.policy_content === 'string') return; // explicit content wins
  const read = (path) => (existsSync(path) ? readFileSync(path, 'utf-8') : '');
  const updatedInput = { ...toolInput, policy_content: read(policyPath) };
  if (POLICY_BOARD_TOOLS.has(parsed.tool)) {
    // UC-12213: the impact report needs the open UCs and the blocks of the last days.
    if (typeof toolInput.board_content !== 'string') updatedInput.board_content = read(itemsPath) || '[]';
    if (typeof toolInput.events_content !== 'string') updatedInput.events_content = read(eventsPath);
  }
  const author = gitAuthor();
  if (author && !toolInput.actor) updatedInput.actor = author.slice(0, 80);
  // UC-12606: skip_enforcement needs the context too (a subagent cannot approve impact_radius).
  if (IDENTITY_TOOLS.has(parsed.tool)) {
    delete updatedInput.client_session_id;
    delete updatedInput.client_agent_id;
    delete updatedInput.client_agent_type;
    Object.assign(updatedInput, identityFields(payload));
  }
  process.stdout.write(JSON.stringify({ hookSpecificOutput: { hookEventName: 'PreToolUse', updatedInput } }));
}

function postPolicy() {
  const response = payload.tool_response;
  const notes = [];
  try {
    const line = POLICY_EVENT_TOOLS.has(parsed.tool) ? extractField(response, 'event_line') : null;
    if (line != null) {
      JSON.parse(line);
      mkdirSync(dirname(eventsPath), { recursive: true });
      appendFileSync(eventsPath, `${line}\n`, 'utf-8');
      notes.push(`el registro en ${eventsPath.replace(`${root}/`, '')}`);
    }
    const content = POLICY_WRITERS.has(parsed.tool) ? extractField(response, 'policy_content') : null;
    if (content != null) {
      JSON.parse(content);
      writeAtomic(policyPath, content.endsWith('\n') ? content : `${content}\n`);
      notes.unshift(`la política en ${policyPath.replace(`${root}/`, '')}`);
    }
  } catch (err) {
    process.stderr.write(
      `SpecBox freeform-fragment: no se pudo guardar lo que devolvió ${parsed.tool} (${err.message}). ` +
        'Repite la llamada antes de seguir.\n',
    );
    process.exit(2);
  }
  const visible = ['policy_content', 'event_line'].some((k) => extractField(response, k) != null);
  if (!visible && notes.length === 0) return; // a read without anything to hide, or an error
  writeHidden(response, notes.length ? `SpecBox: guardado ${notes.join(' y ')}. No lo escribas a mano.` : null);
}

function writeHidden(response, note) {
  const out = { hookEventName: 'PostToolUse', updatedToolOutput: withoutItemsContent(response) };
  if (note) out.additionalContext = note;
  process.stdout.write(JSON.stringify({ hookSpecificOutput: out }));
}

/** setup_board of a new board: the policy with origin «new», only if the project has none. */
function savePolicyOfNewBoard(response) {
  if (parsed.tool !== 'setup_board' || existsSync(policyPath)) return false;
  const content = extractField(response, 'policy_content');
  if (content == null) return false;
  try {
    JSON.parse(content);
    writeAtomic(policyPath, content.endsWith('\n') ? content : `${content}\n`);
    return true;
  } catch {
    return false;
  }
}

function pre() {
  const raw = existsSync(itemsPath) ? readFileSync(itemsPath, 'utf-8') : '[]';
  const items = parseJson(raw);
  if (!Array.isArray(items)) return; // another dialect: leave the call as it is
  const given = toolInput.items_content;
  if (typeof given === 'string' && given.trim() !== raw.trim()) return; // explicit content wins

  const built = withLock(stateDir, () => {
    const result = buildItemsContent({
      tool: parsed.tool,
      args: toolInput,
      items,
      raw,
      reserved: reservedNumbers(stateDir),
    });
    writeAtomic(
      pending,
      JSON.stringify({
        tool: parsed.tool,
        created_at: new Date().toISOString(),
        whole: result.whole,
        reserves: result.reserves,
        sent: result.sent,
      }),
    );
    return result;
  });
  const updatedInput = { ...toolInput, items_content: built.itemsContent };
  // UC-12211, UC-12401: start_uc and complete_uc check measures of the board's policy.
  if (GATE_TOOLS.has(parsed.tool) && typeof toolInput.policy_content !== 'string' && existsSync(policyPath)) {
    updatedInput.policy_content = readFileSync(policyPath, 'utf-8');
  }
  // UC-12401: who marked each criterion, kept with its verdict and its receipt. UC-12501: who
  // retired one, kept with the retired criterion.
  const authorArg = AUTHOR_ARGS[parsed.tool];
  if (authorArg && !toolInput[authorArg]) {
    const author = gitAuthor();
    if (author) updatedInput[authorArg] = author.slice(0, 100);
  }
  // UC-12402: the Claude Code context that calls (this hook owns the call; agent-identity steps aside).
  if (IDENTITY_TOOLS.has(parsed.tool)) {
    delete updatedInput.client_session_id;
    delete updatedInput.client_agent_id;
    delete updatedInput.client_agent_type;
    Object.assign(updatedInput, identityFields(payload));
  }
  process.stdout.write(JSON.stringify({ hookSpecificOutput: { hookEventName: 'PreToolUse', updatedInput } }));
}

/**
 * start_uc (UC-12301) and complete_uc (UC-12401): a block they record (`event_line`) and a skip they
 * spend (`policy_content`) go where the policy tools write them. Returns the note for the agent, or null.
 */
function saveGateEnforcement(response) {
  if (!GATE_TOOLS.has(parsed.tool)) return null;
  const saved = [];
  try {
    const lines = (extractField(response, 'event_line') || '').split('\n').filter((l) => l.trim());
    if (lines.length) {
      for (const line of lines) JSON.parse(line);
      mkdirSync(dirname(eventsPath), { recursive: true });
      appendFileSync(eventsPath, lines.map((l) => `${l}\n`).join(''), 'utf-8');
      saved.push(`el registro en ${eventsPath.replace(`${root}/`, '')}`);
    }
    const policy = extractField(response, 'policy_content');
    if (policy != null) {
      JSON.parse(policy);
      writeAtomic(policyPath, policy.endsWith('\n') ? policy : `${policy}\n`);
      saved.unshift(`la política en ${policyPath.replace(`${root}/`, '')}`);
    }
  } catch (err) {
    process.stderr.write(
      `SpecBox freeform-fragment: no se pudo guardar lo que devolvió ${parsed.tool} (${err.message}). ` +
        'Repite la llamada antes de seguir.\n',
    );
    process.exit(2);
  }
  return saved.length ? `SpecBox: guardado ${saved.join(' y ')}. No lo escribas a mano.` : null;
}

function post() {
  if (!existsSync(pending)) return;
  const response = payload.tool_response;
  const startNote = saveGateEnforcement(response);
  const content = extractItemsContent(response);
  if (content == null) {
    unlinkSync(pending); // a read, or an error: nothing to merge
    if (startNote) writeHidden(response, startNote); // a start_uc or complete_uc that a measure stopped
    return;
  }
  try {
    const sentInfo = JSON.parse(readFileSync(pending, 'utf-8'));
    const back = JSON.parse(content);
    const returned = Array.isArray(back) ? back : back?.items;
    if (!Array.isArray(returned)) throw new Error('the answer carries no items');
    const changes = withLock(stateDir, () => {
      const local = existsSync(itemsPath) ? JSON.parse(readFileSync(itemsPath, 'utf-8')) : [];
      const merged = mergeFragment(local, sentInfo.sent, returned);
      writeAtomic(itemsPath, `${JSON.stringify(merged, null, 2)}\n`);
      unlinkSync(pending);
      return merged.length - local.length;
    });
    const policySaved = savePolicyOfNewBoard(response);
    process.stdout.write(
      JSON.stringify({
        hookSpecificOutput: {
          hookEventName: 'PostToolUse',
          updatedToolOutput: withoutItemsContent(response),
          additionalContext:
            `SpecBox: el tablero ya está guardado en ${itemsPath.replace(`${root}/`, '')}` +
            (changes ? ` (${changes > 0 ? '+' : ''}${changes} elementos)` : '') +
            (policySaved ? `, con su política en ${policyPath.replace(`${root}/`, '')}` : '') +
            '. No lo escribas a mano.' +
            (startNote ? ` ${startNote}` : ''),
        },
      }),
    );
  } catch (err) {
    process.stderr.write(
      `SpecBox freeform-fragment: no se pudo guardar en ${itemsPath} lo que cambió ${parsed.tool} ` +
        `(${err.message}). La respuesta está intacta y lo enviado queda en ${pending}: ` +
        'vuelve a leer el tablero antes de seguir y repite la llamada si el cambio no está.\n',
    );
    process.exit(2);
  }
}

function readJson(path) {
  try {
    return JSON.parse(readFileSync(path, 'utf-8'));
  } catch {
    return null;
  }
}

function parseJson(text) {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}
