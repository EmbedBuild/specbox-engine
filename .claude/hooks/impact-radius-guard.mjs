#!/usr/bin/env node
/**
 * impact-radius-guard.mjs — PreToolUse sobre `git commit` (US-126 · UC-12606, medida `impact_radius`).
 *
 * Clasifica el commit por lo que tocan sus ficheros (lib/impact-radius.mjs): contrato de API,
 * migración de datos, dependencias o código interno. La clase va en el mensaje del hook (AC-01) y
 * queda en .quality/logs/impact-radius.jsonl con los ficheros que la decidieron (AC-03).
 *
 * - Interno o dependencias: no pide aprobación (AC-03); en «warn» y en «block» solo lo dice.
 * - Contrato de API o migración de datos (AC-02 y AC-04):
 *   - en «warn», lo dice y el commit sigue;
 *   - en «block», el commit se detiene hasta que una persona lo aprueba, en cualquier nivel de
 *     autopilot. La aprobación es un `skip_enforcement(measure="impact_radius", uc_id, reason)` de la
 *     sesión que habla con la persona (un subagente no puede darla), también por adelantado en el
 *     triaje de /implement. El hook la gasta en este commit (native: tool `use_enforcement_skip`;
 *     FreeForm: doc/tracking/policy.json) y apunta el HEAD: si el commit falla y se repite sin que
 *     HEAD cambie, la misma aprobación vale; tras un commit hecho, no.
 * - «off»: no clasifica.
 *
 * Globs del proyecto en `specbox.impact` (o `impact`) de .claude/settings.json: `api_globs`,
 * `migration_globs` y `signature_globs` (ficheros cuyas funciones públicas son contrato: cuenta un
 * cambio en sus parámetros, no en su cuerpo). Revisa el repo sobre el que actúa la orden.
 */

import { appendFileSync, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, isAbsolute, join } from 'node:path';
import { readHookInput, gitDirForCommand, git, commitFiles, readJsonFile } from './lib/utils.mjs';
import { getProjectConfig } from './lib/config.mjs';
import { blockWith, noteWith } from './lib/output.mjs';
import { leerPolitica, modoDe } from './lib/enforcement-policy.mjs';
import { recordEnforcementEvent, recordCorrectionIfBlocked } from './lib/enforcement-events.mjs';
import { cabecerasDelDispositivo, URL_POR_DEFECTO } from './lib/heartbeat-send.mjs';
import { llamarTool } from './lib/mcp-client.mjs';
import { classifyCommit, describe } from './lib/impact-radius.mjs';

const MEASURE = 'impact_radius';
const LOG = join('.quality', 'logs', 'impact-radius.jsonl');
const APPROVED = join('.quality', 'impact-radius-approved.json');

const { toolInput, cwd } = readHookInput();
const command = String(toolInput.command || '');
if (!/\bgit\b[^;&|]*\bcommit\b/.test(command)) process.exit(0);
try {
  process.chdir(gitDirForCommand(command, cwd));
} catch {
  process.exit(0);
}
const root = process.cwd();

const config = getProjectConfig();
const marker = readJsonFile(join('.quality', 'active_uc.json'));
// El tablero de la UC activa manda (en un satélite, el del orquestador); si no, el del proyecto.
const boardId = marker?.board_id || config.boardId;
const backendType = marker?.board_id && marker.board_id !== config.boardId
  ? (marker.reservation?.backend === 'native' || /^[\w.-]+\/[\w.-]+$/.test(marker.board_id) ? 'native' : config.backendType)
  : config.backendType;
if (!boardId && !backendType) process.exit(0);
const board = { ...config, boardId, backendType };
const trackingDir = config.freeformRoot && isAbsolute(config.freeformRoot) ? config.freeformRoot : join(root, 'doc', 'tracking');

const politica = await leerPolitica({ root, backendType, boardId, trackingDir });
const mode = modoDe(politica, MEASURE);
if (mode === 'off') process.exit(0);

const files = commitFiles(command);
if (!files.length) process.exit(0);

function impactSettings() {
  for (const file of ['.claude/settings.json', '.claude/settings.local.json']) {
    const json = readJsonFile(join(root, file));
    const impact = json?.specbox?.impact ?? json?.impact;
    if (impact && typeof impact === 'object') return impact;
  }
  return {};
}

/** El texto en HEAD y el que va al commit (el del índice; con `commit -a`, el del disco). */
function versions(path) {
  const before = git(`show HEAD:${JSON.stringify(path)}`);
  let after = git(`show :${JSON.stringify(path)}`);
  if (/\scommit\b[^;&|]*\s(-[a-zA-Z]*a[a-zA-Z]*|--all)\b/.test(command) || (!after && existsSync(path))) {
    try {
      after = readFileSync(path, 'utf-8');
    } catch { /* borrado */ }
  }
  return { before, after };
}

const result = classifyCommit(files, impactSettings(), versions);
const ucId = marker?.uc_id || '';
const head = git('rev-parse HEAD');
const deciding = (result.classes[result.class] ?? []).map((f) => f.path).sort();

function log(outcome, extra = {}) {
  try {
    mkdirSync(dirname(join(root, LOG)), { recursive: true });
    appendFileSync(join(root, LOG), `${JSON.stringify({
      at: new Date().toISOString(),
      uc_id: ucId || null,
      branch: git('branch --show-current'),
      class: result.class,
      needs_approval: result.needs_approval,
      mode,
      outcome,
      files: result.classes[result.class] ?? [],
      counts: Object.fromEntries(Object.entries(result.classes).map(([k, v]) => [k, v.length])),
      ...extra,
    })}\n`);
  } catch { /* sin registro, el commit no cambia */ }
}

const line = describe(result);
if (!result.needs_approval || mode !== 'block') {
  log(result.needs_approval ? 'noted' : 'passed');
  const extra = result.needs_approval
    ? [`La medida impact_radius está en «warn»: el commit sigue. En «block» necesitaría la aprobación de una persona (skip_enforcement(measure="impact_radius", uc_id="${ucId || 'UC-…'}", reason=…)).`]
    : [];
  noteWith('PreToolUse', line, extra);
  process.exit(0);
}

// «block» y contrato o migración: hace falta la aprobación de una persona.

/** La aprobación ya gastada en un intento anterior de este mismo commit (HEAD sin cambiar). */
function reusable() {
  const prev = readJsonFile(join(root, APPROVED));
  if (!prev) return null;
  if (prev.head === head && prev.uc_id === ucId && deciding.every((f) => prev.files?.includes(f))) return prev.skip;
  rmSync(join(root, APPROVED), { force: true });
  return null;
}

/** FreeForm: gasta el salto pendiente más antiguo de la medida en la UC, en policy.json. */
function takeFreeform() {
  const path = join(trackingDir, 'policy.json');
  const raw = readJsonFile(path);
  const skips = Array.isArray(raw?.skips) ? raw.skips : [];
  const i = skips.findIndex((s) => s?.measure === MEASURE && s?.uc_id === ucId);
  if (i < 0) return null;
  const skip = skips[i];
  try {
    writeFileSync(path, `${JSON.stringify({ ...raw, skips: [...skips.slice(0, i), ...skips.slice(i + 1)] }, null, 2)}\n`);
  } catch {
    return null;
  }
  return skip;
}

/** native: la tool use_enforcement_skip con la identidad del dispositivo. */
async function takeNative() {
  if (process.env.SPECBOX_ENFORCEMENT_POLICY === 'off') return null;
  try {
    const url = process.env.SPECBOX_MCP_URL || URL_POR_DEFECTO;
    const cabeceras = await cabecerasDelDispositivo({ ...process.env, CLAUDE_CODE_MCP_SERVER_URL: url });
    if (!cabeceras.Authorization) return null;
    const r = await llamarTool({
      url, cabeceras, nombre: 'use_enforcement_skip', args: { board_id: boardId, measure: MEASURE, uc_id: ucId }, topeMs: 4000,
    });
    return r?.success && r.skip ? r.skip : null;
  } catch {
    return null;
  }
}

let skip = ucId ? reusable() : null;
let fresh = false;
if (!skip && ucId) {
  skip = backendType === 'freeform' ? takeFreeform() : backendType === 'native' ? await takeNative() : null;
  fresh = !!skip;
}

if (skip) {
  try {
    mkdirSync(dirname(join(root, APPROVED)), { recursive: true });
    writeFileSync(join(root, APPROVED), JSON.stringify({ head, uc_id: ucId, files: deciding, skip }));
  } catch { /* sin copia: un reintento pedirá otra aprobación */ }
  log('approved', { approval: { by: skip.by, at: skip.at, reason: skip.reason, reused: !fresh } });
  if (fresh) await recordCorrectionIfBlocked({ root, config: board, measure: MEASURE, ucId, by: 'impact-radius-guard' });
  noteWith('PreToolUse', line, [
    `Aprobado por ${skip.by || 'una persona'} (${skip.at || 'sin fecha'}): «${skip.reason || ''}». El commit sigue.`,
  ]);
  process.exit(0);
}

log('blocked');
if (ucId) await recordEnforcementEvent({ root, config: board, measure: MEASURE, ucId, outcome: 'blocked', by: 'impact-radius-guard' });
blockWith(`COMMIT DETENIDO por la medida impact_radius. ${line}`, [
  'Un cambio de contrato de API o de migración de datos necesita la aprobación de una persona antes del commit, en cualquier nivel de autopilot.',
  ucId
    ? `Para seguir: enseña a la persona la clase y los ficheros y, si lo aprueba, llama a skip_enforcement(measure="impact_radius", uc_id="${ucId}", reason="<por qué se aprueba>") desde la sesión principal (un subagente no puede). Luego repite el commit.`
    : 'No hay UC activa: empieza la UC con start_uc, pide la aprobación (skip_enforcement con measure="impact_radius" y su uc_id) y repite el commit.',
  'Si el cambio no debía tocar el contrato o la migración, quita esos ficheros del commit.',
]);
