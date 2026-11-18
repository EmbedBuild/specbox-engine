#!/usr/bin/env node
/**
 * app-docs-fragment.mjs — la zona «roadmap» de app_prd.md sigue al tablero (UC-12203, UC-12218).
 *
 * Tools: complete_uc, move_uc, add_uc, delete_uc y mark_ac_batch.
 *
 * PreToolUse: pide la zona al servidor (`with_roadmap: true`) solo si hace falta: el repositorio que
 * guarda el canon (el orquestador en multirepo; el satélite no guarda copia) tiene
 * doc/app/app_prd.md y está en su rama principal. Sin pedirla, el servidor responde como antes y la
 * zona no gasta contexto (UC-12218). En FreeForm no se pide: la calcula este hook.
 *
 * PostToolUse: escribe en esa zona el cuerpo que devolvió el servidor (`app_docs_sync.roadmap_body`)
 * y lo quita de la respuesta que ve el modelo. En FreeForm espera a que freeform-fragment haya
 * fusionado items.json y calcula el mismo cuerpo con él (lib/roadmap.mjs).
 *
 * Solo en main o master: la zona sale del tablero, así que en una rama de trabajo se deja para el
 * siguiente cambio en main y dos ramas no chocan al fusionar. Nunca bloquea.
 */

import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync, renameSync, writeFileSync } from 'node:fs';
import { isAbsolute, join, resolve } from 'node:path';
import { parseToolName, pendingPath, withoutFields } from './lib/freeform-fragment.mjs';
import { readHookInput } from './lib/utils.mjs';
import { render, replaceZone, rowsFromItems } from './lib/roadmap.mjs';
import { topObject } from './lib/uc-state.mjs';

const TOOLS = new Set(['complete_uc', 'move_uc', 'add_uc', 'delete_uc', 'mark_ac_batch']);
const DOC = join('doc', 'app', 'app_prd.md');
const MERGE_WAIT_MS = 4000;

const { event, toolName, toolInput, cwd, payload } = readHookInput();
const parsed = parseToolName(toolName);
if (!parsed || !TOOLS.has(parsed.tool)) process.exit(0);

const git = (dir, args) => {
  try {
    return execFileSync('git', ['-C', dir, ...args], { encoding: 'utf-8', stdio: ['ignore', 'pipe', 'ignore'] }).trim();
  } catch {
    return '';
  }
};
const readJson = (path) => {
  try {
    return JSON.parse(readFileSync(path, 'utf-8'));
  } catch {
    return null;
  }
};

const root = git(cwd, ['rev-parse', '--show-toplevel']) || cwd;
const settings = readJson(join(root, '.claude', 'settings.local.json')) || {};
const projectConfig = readJson(join(root, '.claude', 'project-config.json')) || {};
const backendType = projectConfig.backend_type || settings.backend_type || settings.specbox?.backend_type || '';
const freeform = backendType === 'freeform';
const mr = settings.multirepo || projectConfig.multirepo;
const canonRoot =
  mr?.enabled && mr?.role === 'satellite' && mr?.orchestrator
    ? isAbsolute(mr.orchestrator) ? mr.orchestrator : resolve(root, mr.orchestrator)
    : root;
const docPath = join(canonRoot, DOC);
const wanted = () => existsSync(docPath) && ['main', 'master'].includes(git(canonRoot, ['branch', '--show-current']));

if (event === 'PreToolUse') {
  // FreeForm: la zona la calcula el hook; además, freeform-fragment ya cambia la entrada.
  if (!freeform && toolInput.with_roadmap !== true && wanted()) {
    process.stdout.write(
      JSON.stringify({ hookSpecificOutput: { hookEventName: 'PreToolUse', updatedInput: { ...toolInput, with_roadmap: true } } }),
    );
  }
  process.exit(0);
}
if (event !== 'PostToolUse') process.exit(0);

const response = payload.tool_response;
const top = topObject(response);
const sync = top?.app_docs_sync;

const hide = () => {
  if (typeof sync?.roadmap_body !== 'string') return;
  process.stdout.write(
    JSON.stringify({ hookSpecificOutput: { hookEventName: 'PostToolUse', updatedToolOutput: withoutFields(response, ['roadmap_body']) } }),
  );
};

/** FreeForm: espera a que freeform-fragment fusione lo que cambió la tool en items.json. */
function waitForMerge() {
  if (!payload.tool_use_id) return;
  const pending = pendingPath(join(root, '.quality', 'freeform-fragments'), payload.tool_use_id);
  const until = Date.now() + MERGE_WAIT_MS;
  while (existsSync(pending) && Date.now() < until) {
    Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 50);
  }
}

try {
  if (top && !top.error && top.success !== false && wanted()) {
    let body = sync?.ok === true && typeof sync.roadmap_body === 'string' ? sync.roadmap_body : null;
    if (body == null && freeform) {
      waitForMerge();
      const tracking = settings.specbox?.freeform_root_absolute;
      const items = readJson(join(typeof tracking === 'string' && isAbsolute(tracking) ? tracking : join(root, 'doc', 'tracking'), 'items.json'));
      if (Array.isArray(items)) body = render(rowsFromItems(items));
    }
    if (body != null) {
      const current = readFileSync(docPath, 'utf-8');
      const next = replaceZone(current, 'roadmap', body);
      if (next != null && next !== current) {
        const tmp = `${docPath}.${process.pid}.tmp`;
        writeFileSync(tmp, next, 'utf-8');
        renameSync(tmp, docPath);
      }
    }
  }
} catch {
  // el canon es una ayuda: nunca la razón de que falle una tool
}
hide();
process.exit(0);
