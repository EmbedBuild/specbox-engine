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
 */

import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync, unlinkSync } from 'node:fs';
import { isAbsolute, join } from 'node:path';
import { isRemoteMcp } from './lib/freeform-path.mjs';
import {
  CONTENT_TOOLS,
  buildItemsContent,
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

const { event, toolName, toolInput, cwd, payload } = readHookInput();
const parsed = parseToolName(toolName);
if (!parsed || !CONTENT_TOOLS.has(parsed.tool) || !payload.tool_use_id) process.exit(0);

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
const stateDir = join(root, '.quality', 'freeform-fragments');
const pending = pendingPath(stateDir, payload.tool_use_id);

if (event === 'PreToolUse') pre();
else if (event === 'PostToolUse') post();
process.exit(0);

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
  process.stdout.write(
    JSON.stringify({
      hookSpecificOutput: {
        hookEventName: 'PreToolUse',
        updatedInput: { ...toolInput, items_content: built.itemsContent },
      },
    }),
  );
}

function post() {
  if (!existsSync(pending)) return;
  const response = payload.tool_response;
  const content = extractItemsContent(response);
  if (content == null) {
    unlinkSync(pending); // a read, or an error: nothing to merge
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
    process.stdout.write(
      JSON.stringify({
        hookSpecificOutput: {
          hookEventName: 'PostToolUse',
          updatedToolOutput: withoutItemsContent(response),
          additionalContext:
            `SpecBox: el tablero ya está guardado en ${itemsPath.replace(`${root}/`, '')}` +
            (changes ? ` (${changes > 0 ? '+' : ''}${changes} elementos)` : '') +
            '. No lo escribas a mano.',
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
