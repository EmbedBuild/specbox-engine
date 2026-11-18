#!/usr/bin/env node
/**
 * app-docs-fragment.mjs — PostToolUse: la zona «roadmap» de app_prd.md sigue al tablero (UC-12203).
 *
 * Tras complete_uc, move_uc, add_uc, delete_uc y mark_ac_batch el servidor devuelve
 * `app_docs_sync.roadmap_body` (el cuerpo de la zona calculado con el tablero). Este hook lo escribe
 * en doc/app/app_prd.md del repositorio que lo tiene: el orquestador en un proyecto multirepo (el
 * satélite no guarda copia). Con FreeForm por fragmentos (`render: "client"`) calcula el mismo
 * cuerpo con su items.json.
 *
 * Solo escribe si ese repositorio está en su rama principal (main o master): la zona sale del
 * tablero, así que en una rama de trabajo se deja para el siguiente cambio en main y dos ramas no
 * chocan al fusionar. Oculta el cuerpo de la respuesta que ve el modelo. Nunca bloquea.
 */

import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync, renameSync, writeFileSync } from 'node:fs';
import { isAbsolute, join, resolve } from 'node:path';
import { parseToolName, withoutFields } from './lib/freeform-fragment.mjs';
import { readHookInput } from './lib/utils.mjs';
import { render, replaceZone, rowsFromItems } from './lib/roadmap.mjs';
import { topObject } from './lib/uc-state.mjs';

const TOOLS = new Set(['complete_uc', 'move_uc', 'add_uc', 'delete_uc', 'mark_ac_batch']);
const DOC = join('doc', 'app', 'app_prd.md');

const { event, toolName, cwd, payload } = readHookInput();
const parsed = parseToolName(toolName);
if (event !== 'PostToolUse' || !parsed || !TOOLS.has(parsed.tool)) process.exit(0);

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
const response = payload.tool_response;
const sync = topObject(response)?.app_docs_sync;
if (!sync || sync.ok !== true || sync.zone !== 'roadmap') process.exit(0);

// El repositorio que guarda el canon: el orquestador en un satélite multirepo.
const settings = readJson(join(root, '.claude', 'settings.local.json')) || {};
const projectConfig = readJson(join(root, '.claude', 'project-config.json')) || {};
const mr = settings.multirepo || projectConfig.multirepo;
const canonRoot =
  mr?.enabled && mr?.role === 'satellite' && mr?.orchestrator
    ? isAbsolute(mr.orchestrator) ? mr.orchestrator : resolve(root, mr.orchestrator)
    : root;
const docPath = join(canonRoot, DOC);

const hide = () => {
  if (typeof sync.roadmap_body !== 'string') return;
  process.stdout.write(
    JSON.stringify({ hookSpecificOutput: { hookEventName: 'PostToolUse', updatedToolOutput: withoutFields(response, ['roadmap_body']) } }),
  );
};

try {
  const branch = git(canonRoot, ['branch', '--show-current']);
  if (!existsSync(docPath) || !['main', 'master'].includes(branch)) {
    hide();
    process.exit(0);
  }
  let body = typeof sync.roadmap_body === 'string' ? sync.roadmap_body : null;
  if (body == null && sync.render === 'client') {
    const tracking = settings.specbox?.freeform_root_absolute;
    const itemsPath = join(typeof tracking === 'string' && isAbsolute(tracking) ? tracking : join(root, 'doc', 'tracking'), 'items.json');
    const items = readJson(itemsPath);
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
} catch {
  // el canon es una ayuda: nunca la razón de que falle una tool
}
hide();
process.exit(0);
