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
 * UC-12605 · el documento de comportamiento: en `complete_uc`, `move_uc` y `add_uc` pide además
 * `with_behavior_doc` (solo a un servidor 6.47.0 o posterior, lib/server-version.mjs) y, en
 * `behavior_doc_us_ids`, las historias que define el PRD de la UC (por el marcador de UC activa o por
 * el PRD que nombra la UC). Escribe la sección de cada historia (sus UC cerradas con sus criterios) en
 * doc/spec/<funcionalidad>.md del mismo repositorio, junto al PRD de la historia (la funcionalidad es
 * la carpeta del PRD); nada si el PRD no define la historia. Un documento nuevo solo nace al cerrar
 * una UC. El PRD queda superado cuando todas sus historias están sin nada pendiente y el documento
 * tiene recién escrita la sección de cada una; si una vuelve a tener trabajo, le quita la marca que
 * puso. Escribe solo dentro del repositorio del canon y nunca a través de un enlace simbólico. En
 * FreeForm lo calcula con items.json (lib/behavior-doc.mjs). Oculta el bloque a quien llama.
 */

import { execFileSync } from 'node:child_process';
import { existsSync, lstatSync, mkdirSync, readFileSync, realpathSync, renameSync, writeFileSync } from 'node:fs';
import { dirname, isAbsolute, join, resolve } from 'node:path';
import { parseToolName, pendingPath, withoutFields } from './lib/freeform-fragment.mjs';
import { readHookInput } from './lib/utils.mjs';
import { render, replaceZone, rowsFromItems } from './lib/roadmap.mjs';
import {
  completeStoriesFromItems,
  featureOf,
  markSuperseded,
  MAX_STORIES,
  prdStories,
  replaceStorySection,
  sectionForStory,
  SPEC_DIR,
  storyIdFromItems,
  unmarkSuperseded,
} from './lib/behavior-doc.mjs';
import { locatePrd, prdForUc } from './lib/prd-locate.mjs';
import { serverAtLeast } from './lib/server-version.mjs';
import { readMarker, topObject } from './lib/uc-state.mjs';

const TOOLS = new Set(['complete_uc', 'move_uc', 'add_uc', 'delete_uc', 'mark_ac_batch']);
const SPEC_TOOLS = new Set(['complete_uc', 'move_uc', 'add_uc']);
/** Tools que dan trabajo a una historia: su PRD deja de estar superado, en cualquier rama (UC-12605). */
const REOPEN_TOOLS = new Set(['start_uc', 'import_spec', 'add_uc', 'move_uc']);
/** El primer servidor que acepta `with_behavior_doc` y `behavior_doc_us_ids`. */
const SPEC_MIN_SERVER = '6.47.0';
const DOC = join('doc', 'app', 'app_prd.md');
const MERGE_WAIT_MS = 4000;

const { event, toolName, toolInput, cwd, payload } = readHookInput();
const parsed = parseToolName(toolName);
if (!parsed || !(TOOLS.has(parsed.tool) || REOPEN_TOOLS.has(parsed.tool))) process.exit(0);

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
const hasPrds = () => existsSync(join(canonRoot, 'doc', 'prd')) || existsSync(join(canonRoot, 'doc', 'prds'));
const specWanted = () => SPEC_TOOLS.has(parsed.tool) && hasPrds() && onMain();

/** La ruta absoluta de `rel` dentro del repositorio del canon, o null si sale de él o pasa por un enlace. */
function insideCanon(rel) {
  let real;
  try {
    real = realpathSync(canonRoot);
  } catch {
    return null;
  }
  const parts = String(rel || '').split('/');
  if (!parts.length || parts.some((p) => !p || p === '.' || p === '..')) return null;
  let cur = real;
  for (const part of parts) {
    cur = join(cur, part);
    let st;
    try {
      st = lstatSync(cur);
    } catch {
      break; // no existe: lo que falta lo crea este hook, sin enlaces
    }
    if (st.isSymbolicLink()) return null;
  }
  return join(real, ...parts);
}

const readText = (rel) => {
  const path = insideCanon(rel);
  try {
    return path ? readFileSync(path, 'utf-8') : null;
  } catch {
    return null;
  }
};

/** Las historias que define el PRD de la UC (o de la historia de add_uc), hasta MAX_STORIES. */
function prdStoriesFor(input) {
  let usId = parsed.tool === 'add_uc' ? String(input.us_id || '') : '';
  if (!usId && input.uc_id) {
    const marker = readMarker(root);
    if (marker?.uc_id && String(marker.uc_id).toUpperCase() === String(input.uc_id).toUpperCase()) usId = marker.us_id || '';
  }
  const prdRel = (usId && locatePrd({ root: canonRoot, usId })) || (input.uc_id ? prdForUc(canonRoot, input.uc_id) : null);
  const text = prdRel ? readText(prdRel) : null;
  return text ? prdStories(text).slice(0, MAX_STORIES) : [];
}

if (event === 'PreToolUse') {
  // FreeForm: la zona y el documento los calcula el hook; además, freeform-fragment ya cambia la entrada.
  // start_uc e import_spec no aceptan estos parámetros: solo se miran después.
  if (!freeform && TOOLS.has(parsed.tool)) {
    const extra = {};
    if (toolInput.with_roadmap !== true && wanted()) extra.with_roadmap = true;
    if (toolInput.with_behavior_doc !== true && specWanted() && (await serverAtLeast(SPEC_MIN_SERVER, { root }))) {
      extra.with_behavior_doc = true;
      const stories = Array.isArray(toolInput.behavior_doc_us_ids) ? [] : prdStoriesFor(toolInput);
      if (stories.length) extra.behavior_doc_us_ids = stories;
    }
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

/**
 * UC-12605: las secciones de las historias del PRD en doc/spec/<funcionalidad>.md y la marca del PRD:
 * superado si todas sus historias están sin nada pendiente y sus secciones son de ahora; sin la marca
 * que puso el engine si alguna vuelve a tener trabajo.
 */
function writeBehaviorDoc() {
  const today = new Date().toISOString().slice(0, 10);
  const fromInput = parsed.tool === 'add_uc' ? { usId: toolInput.us_id } : { ucId: toolInput.uc_id };
  let block = top?.behavior_doc;
  let items = null;
  if (freeform || block?.render === 'client') {
    items = itemsOf();
    const usId = Array.isArray(items) ? storyIdFromItems(items, fromInput) : '';
    if (!usId) return;
    block = { ok: true, us_id: usId, complete_stories: completeStoriesFromItems(items), date: today };
  }
  if (!block?.ok || typeof block.us_id !== 'string' || !block.us_id) return;
  const usId = block.us_id.toUpperCase();
  const prdRel = locatePrd({ root: canonRoot, usId });
  const prdPath = prdRel ? insideCanon(prdRel) : null;
  if (!prdPath) return;
  const prd = readFileSync(prdPath, 'utf-8');
  const stories = prdStories(prd);
  // El PRD tiene que definir la historia (o llamarse como ella): el único fichero de doc/prds no basta.
  if (!stories.includes(usId) && prdRel !== `doc/prds/${usId.toLowerCase().replace(/-/g, '_')}_prd.md`) return;
  const needed = [...new Set([...stories, usId])];
  const fresh = new Map();
  if (items) {
    for (const us of needed.slice(0, MAX_STORIES + 1)) {
      const found = sectionForStory(items, us);
      if (found) fresh.set(us, found.section);
    }
  } else {
    const sections = block.sections && typeof block.sections === 'object' ? block.sections : {};
    for (const [us, text] of Object.entries(sections)) if (typeof text === 'string' && needed.includes(us)) fresh.set(us, text);
    if (!fresh.has(usId) && typeof block.section === 'string') fresh.set(usId, block.section);
  }
  const feature = featureOf(prdRel);
  const specRel = `${SPEC_DIR}/${feature}.md`;
  const specPath = insideCanon(specRel);
  if (!specPath) return;
  const exists = existsSync(specPath);
  const create = parsed.tool === 'complete_uc' || (parsed.tool === 'move_uc' && toolInput.target === 'done');
  if (exists || create) {
    const current = exists ? readFileSync(specPath, 'utf-8') : '';
    let next = current;
    for (const [us, text] of fresh) next = replaceStorySection(next, us, text, feature);
    if (next !== current) writeAtomic(specPath, next);
  }
  const complete = new Set((Array.isArray(block.complete_stories) ? block.complete_stories : []).map((u) => String(u).toUpperCase()));
  const allComplete = needed.every((us) => complete.has(us));
  let updated = prd;
  if (allComplete && (exists || create) && needed.every((us) => fresh.has(us))) {
    updated = markSuperseded(prd, block.date || today, specRel);
  } else if (!allComplete) {
    updated = unmarkSuperseded(prd, specRel);
  }
  if (updated !== prd) writeAtomic(prdPath, updated);
}

/** El PRD (ruta relativa) de una historia o, si no se sabe cuál, el que nombra la UC. */
function prdRelOf({ usId = '', ucId = '' }) {
  let us = String(usId || '').toUpperCase();
  if (!us && ucId) {
    const marker = readMarker(root);
    if (marker?.uc_id && String(marker.uc_id).toUpperCase() === String(ucId).toUpperCase()) us = String(marker.us_id || '').toUpperCase();
    if (!us && freeform) {
      const items = itemsOf();
      if (Array.isArray(items)) us = storyIdFromItems(items, { ucId });
    }
  }
  if (us) return locatePrd({ root: canonRoot, usId: us });
  return ucId ? prdForUc(canonRoot, ucId) : null;
}

/** Las historias (o la UC) a las que esta llamada deja trabajo pendiente. */
function reopened() {
  const tool = parsed.tool;
  if (tool === 'add_uc') return [{ usId: toolInput.us_id }];
  if (tool === 'move_uc') return toolInput.target === 'done' ? [] : [{ usId: top?.behavior_doc?.us_id, ucId: toolInput.uc_id }];
  if (tool === 'start_uc') return [{ usId: top?.active_uc_marker?.us_id, ucId: toolInput.uc_id }];
  if (tool !== 'import_spec') return [];
  // import_spec: las historias con alguna UC nueva o con criterios añadidos (lo que no dice uc_exists sin cambios).
  let spec = toolInput.spec;
  if (typeof spec === 'string') {
    try {
      spec = JSON.parse(spec);
    } catch {
      spec = null;
    }
  }
  const warnings = Array.isArray(top?.warnings) ? top.warnings : [];
  const unchanged = new Set(
    warnings.filter((w) => w?.code === 'uc_exists' && !(w.applied && !w.identical)).map((w) => String(w.uc_id).toUpperCase()),
  );
  return (Array.isArray(spec?.user_stories) ? spec.user_stories : [])
    .filter((us) => (Array.isArray(us?.use_cases) ? us.use_cases : []).some((uc) => !uc?.uc_id || !unchanged.has(String(uc.uc_id).toUpperCase())))
    .map((us) => ({ usId: us.us_id }));
}

/**
 * UC-12605: el PRD de una historia que vuelve a tener trabajo deja de estar superado, en cualquier
 * rama (/prd siembra con import_spec y /implement arranca con start_uc, a menudo fuera de main). Solo
 * quita la marca que puso el engine con el documento de esa funcionalidad.
 */
function unmarkReopened() {
  const seen = new Set();
  for (const target of reopened()) {
    const prdRel = prdRelOf(target);
    if (!prdRel || seen.has(prdRel)) continue;
    seen.add(prdRel);
    const path = insideCanon(prdRel);
    if (!path) continue;
    const prd = readFileSync(path, 'utf-8');
    const next = unmarkSuperseded(prd, `${SPEC_DIR}/${featureOf(prdRel)}.md`);
    if (next !== prd) writeAtomic(path, next);
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
  if (top && !top.error && top.success !== false && TOOLS.has(parsed.tool) && wanted()) {
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
try {
  if (top && !top.error && top.success !== false && REOPEN_TOOLS.has(parsed.tool) && hasPrds()) unmarkReopened();
} catch {
  // tampoco quitar la marca
}
hide();
process.exit(0);
