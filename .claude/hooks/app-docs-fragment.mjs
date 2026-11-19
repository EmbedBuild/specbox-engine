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
 *
 * UC-12605 · el documento de comportamiento: en `complete_uc` pide además `with_behavior_doc` y
 * escribe la sección de la historia (sus UC cerradas con sus criterios) en
 * doc/spec/<funcionalidad>.md del mismo repositorio, junto al PRD de la historia (la funcionalidad
 * es la carpeta del PRD). Si todas las historias que define el PRD tienen sus UC cerradas, lo marca
 * como superado con la fecha y el documento. En FreeForm lo calcula con items.json
 * (lib/behavior-doc.mjs). Oculta el bloque a quien llama.
 */

import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from 'node:fs';
import { dirname, isAbsolute, join, resolve } from 'node:path';
import { parseToolName, pendingPath, withoutFields } from './lib/freeform-fragment.mjs';
import { readHookInput } from './lib/utils.mjs';
import { render, replaceZone, rowsFromItems } from './lib/roadmap.mjs';
import {
  completeStoriesFromItems,
  featureOf,
  markSuperseded,
  prdStories,
  replaceStorySection,
  sectionFromItems,
  SPEC_DIR,
} from './lib/behavior-doc.mjs';
import { locatePrd } from './lib/prd-locate.mjs';
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
const onMain = () => ['main', 'master'].includes(git(canonRoot, ['branch', '--show-current']));
const wanted = () => existsSync(docPath) && onMain();
// UC-12605: el documento de comportamiento vive junto a los PRD, en el repositorio del canon.
const specWanted = () =>
  parsed.tool === 'complete_uc' &&
  (existsSync(join(canonRoot, 'doc', 'prd')) || existsSync(join(canonRoot, 'doc', 'prds'))) &&
  onMain();

if (event === 'PreToolUse') {
  // FreeForm: la zona y el documento los calcula el hook; además, freeform-fragment ya cambia la entrada.
  if (!freeform) {
    const extra = {};
    if (toolInput.with_roadmap !== true && wanted()) extra.with_roadmap = true;
    if (toolInput.with_behavior_doc !== true && specWanted()) extra.with_behavior_doc = true;
    if (Object.keys(extra).length) {
      process.stdout.write(
        JSON.stringify({ hookSpecificOutput: { hookEventName: 'PreToolUse', updatedInput: { ...toolInput, ...extra } } }),
      );
    }
  }
  process.exit(0);
}
if (event !== 'PostToolUse') process.exit(0);

const response = payload.tool_response;
const top = topObject(response);
const sync = top?.app_docs_sync;

/** La respuesta sin la clave `key`, sea del tipo que sea (withoutFields solo quita textos). */
function dropKey(value, key, depth = 0) {
  if (depth > 6 || value == null) return value;
  if (typeof value === 'string') {
    const text = value.trim();
    if (!text.startsWith('{')) return value;
    try {
      return JSON.stringify(dropKey(JSON.parse(text), key, depth + 1));
    } catch {
      return value;
    }
  }
  if (Array.isArray(value)) return value.map((part) => dropKey(part, key, depth + 1));
  if (typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).filter(([k]) => k !== key).map(([k, v]) => [k, dropKey(v, key, depth + 1)]));
  }
  return value;
}

const hide = () => {
  const roadmap = typeof sync?.roadmap_body === 'string';
  const behavior = top?.behavior_doc != null;
  if (!roadmap && !behavior) return;
  let out = roadmap ? withoutFields(response, ['roadmap_body']) : response;
  if (behavior) out = dropKey(out, 'behavior_doc');
  process.stdout.write(JSON.stringify({ hookSpecificOutput: { hookEventName: 'PostToolUse', updatedToolOutput: out } }));
};

const writeAtomic = (path, text) => {
  mkdirSync(dirname(path), { recursive: true });
  const tmp = `${path}.${process.pid}.tmp`;
  writeFileSync(tmp, text, 'utf-8');
  renameSync(tmp, path);
};

let freeformItems;
const itemsOf = () => {
  if (freeformItems !== undefined) return freeformItems;
  waitForMerge();
  const tracking = settings.specbox?.freeform_root_absolute;
  freeformItems = readJson(join(typeof tracking === 'string' && isAbsolute(tracking) ? tracking : join(root, 'doc', 'tracking'), 'items.json'));
  return freeformItems;
};

/** UC-12605: la sección de la historia en doc/spec/<funcionalidad>.md y, si toca, el PRD superado. */
function writeBehaviorDoc() {
  let block = top?.behavior_doc;
  if (freeform || block?.render === 'client') {
    const items = itemsOf();
    const found = Array.isArray(items) ? sectionFromItems(items, toolInput.uc_id) : null;
    block = found ? { ok: true, ...found, complete_stories: completeStoriesFromItems(items), date: new Date().toISOString().slice(0, 10) } : null;
  }
  if (!block?.ok || typeof block.section !== 'string' || !block.us_id) return;
  const prdRel = locatePrd({ root: canonRoot, usId: block.us_id, includeSuperseded: true });
  if (!prdRel) return;
  const feature = featureOf(prdRel);
  const specRel = `${SPEC_DIR}/${feature}.md`;
  const specPath = join(canonRoot, specRel);
  const current = existsSync(specPath) ? readFileSync(specPath, 'utf-8') : '';
  const next = replaceStorySection(current, block.us_id, block.section, feature);
  if (next !== current) writeAtomic(specPath, next);
  const prdPath = join(canonRoot, prdRel);
  const prd = readFileSync(prdPath, 'utf-8');
  const stories = prdStories(prd);
  const complete = new Set(Array.isArray(block.complete_stories) ? block.complete_stories : []);
  const needed = stories.length ? stories : [block.us_id];
  if (needed.every((us) => complete.has(us))) {
    const marked = markSuperseded(prd, block.date || new Date().toISOString().slice(0, 10), specRel);
    if (marked !== prd) writeAtomic(prdPath, marked);
  }
}

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
      const items = itemsOf();
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
try {
  if (top && !top.error && top.success !== false && specWanted()) writeBehaviorDoc();
} catch {
  // el documento de comportamiento tampoco hace fallar la tool
}
hide();
process.exit(0);
