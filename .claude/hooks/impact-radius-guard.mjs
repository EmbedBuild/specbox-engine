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
 *     autopilot. La aprobación es un `skip_enforcement(measure="impact_radius", uc_id, reason)` desde
 *     la sesión que habla con la persona (un subagente, o una llamada sin el contexto de Claude Code,
 *     no puede darla), también por adelantado en el triaje de /implement. El hook la gasta en este
 *     intento con el commit (HEAD) y la huella del contenido que decide la clase: el tablero la
 *     guarda (native: tool `use_enforcement_skip`; FreeForm: doc/tracking/policy.json). Repetir el
 *     mismo commit tras un fallo reutiliza la aprobación; otro contenido u otro commit piden otra.
 * - «off»: no clasifica.
 *
 * Los ficheros salen del índice, de los `git add`/`git rm` de la misma orden, de `-a` y de las rutas
 * de `git commit <ruta>`, con los borrados y sin renombres (lo que sale de una carpeta de migraciones
 * cuenta), y con su nombre tal cual (sin las comillas de `core.quotePath`). Git se llama sin shell.
 * Globs del proyecto en `specbox.impact` (o `impact`) del .claude/settings.json de la rama base
 * (origin/main, si no main, si no HEAD): una rama no afloja su propia medida.
 */

import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { appendFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, isAbsolute, join } from 'node:path';
import { readHookInput, gitDirForCommand, readJsonFile } from './lib/utils.mjs';
import { getProjectConfig } from './lib/config.mjs';
import { blockWith, noteWith } from './lib/output.mjs';
import { leerPolitica, modoDe } from './lib/enforcement-policy.mjs';
import { recordEnforcementEvent, recordCorrectionIfBlocked } from './lib/enforcement-events.mjs';
import { cabecerasDelDispositivo, URL_POR_DEFECTO } from './lib/heartbeat-send.mjs';
import { llamarTool } from './lib/mcp-client.mjs';
import { classifyCommit, describe } from './lib/impact-radius.mjs';

const MEASURE = 'impact_radius';
const LOG = join('.quality', 'logs', 'impact-radius.jsonl');
const MAX_USED_SKIPS = 20;

const { toolInput, cwd } = readHookInput();
const command = String(toolInput.command || '');
if (!/\bgit\b[^;&|]*\bcommit\b/.test(command)) process.exit(0);
try {
  process.chdir(gitDirForCommand(command, cwd));
} catch {
  process.exit(0);
}
const root = process.cwd();

/** git sin shell: los argumentos (rutas incluidas) nunca se interpretan. '' si falla. */
function gitx(args, { raw = false } = {}) {
  try {
    const out = execFileSync('git', ['-c', 'core.quotePath=false', ...args], {
      cwd: root, encoding: 'utf-8', stdio: ['ignore', 'pipe', 'ignore'], maxBuffer: 64 * 1024 * 1024,
    });
    return raw ? out : out.trim();
  } catch {
    return '';
  }
}
const list0 = (out) => out.split('\0').filter(Boolean);

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

// ── Los ficheros del commit ─────────────────────────────────────────

/** Las palabras de la orden (comillas respetadas), sin interpretar nada. */
function words(text) {
  const out = [];
  const re = /"((?:[^"\\]|\\.)*)"|'([^']*)'|(\S+)/g;
  for (const m of text.matchAll(re)) out.push(m[1] ?? m[2] ?? m[3]);
  return out;
}

/** Los trozos de la orden que son una llamada a `git <verbo>` (separados por &&, ;, ||, |). */
function gitCalls(verb) {
  return command.split(/&&|\|\||;|\|/).map((part) => words(part.trim())).filter((w) => {
    const g = w.indexOf('git');
    if (g < 0) return false;
    let i = g + 1;
    while (i < w.length && w[i].startsWith('-')) i += w[i] === '-C' || w[i] === '-c' ? 2 : 1;
    return w[i] === verb;
  }).map((w) => {
    let i = w.indexOf('git') + 1;
    while (i < w.length && w[i].startsWith('-')) i += w[i] === '-C' || w[i] === '-c' ? 2 : 1;
    return w.slice(i + 1);
  });
}

const VALUE_OPTS = new Set(['-m', '--message', '-F', '--file', '-C', '--reuse-message', '-c', '--reedit-message',
  '--author', '--date', '-t', '--template', '--fixup', '--squash', '--cleanup', '--trailer', '--pathspec-from-file']);

const [commitArgs = []] = gitCalls('commit');
let all = false;
let pathspecs = [];
for (let i = 0; i < commitArgs.length; i += 1) {
  const a = commitArgs[i];
  if (a === '--') { pathspecs.push(...commitArgs.slice(i + 1)); break; }
  if (VALUE_OPTS.has(a)) { i += 1; continue; }
  if (/^--[\w-]+=/.test(a) || /^-[mFCct].+/.test(a)) continue;
  if (a === '-a' || a === '--all' || (/^-[a-zA-Z]+$/.test(a) && a.includes('a') && !a.startsWith('--'))) { all = true; continue; }
  if (a.startsWith('-')) continue;
  pathspecs.push(a);
}
pathspecs = pathspecs.filter(Boolean);

const pendingAdds = gitCalls('add');
const pendingRms = gitCalls('rm');
const files = new Set();
const fromDisk = new Set();
if (pathspecs.length) {
  // `git commit <ruta>` commitea esas rutas tal como están en el disco (también borradas).
  for (const f of list0(gitx(['diff', '--name-only', '-z', '--no-renames', 'HEAD', '--', ...pathspecs], { raw: true }))) {
    files.add(f);
    fromDisk.add(f);
  }
} else {
  for (const f of list0(gitx(['diff', '--cached', '--name-only', '-z', '--no-renames'], { raw: true }))) files.add(f);
  if (all) {
    for (const f of list0(gitx(['diff', '--name-only', '-z', '--no-renames', 'HEAD'], { raw: true }))) {
      files.add(f);
      fromDisk.add(f);
    }
  }
}
for (const args of pendingAdds) {
  const paths = args.filter((a) => !a.startsWith('-'));
  const everything = args.some((a) => ['-A', '--all', '.', '-u', '--update'].includes(a)) || !paths.length;
  const scope = everything ? [] : ['--', ...paths];
  for (const f of list0(gitx(['diff', '--name-only', '-z', '--no-renames', 'HEAD', ...scope], { raw: true }))) {
    files.add(f);
    fromDisk.add(f);
  }
  if (!args.includes('-u') && !args.includes('--update')) {
    for (const f of list0(gitx(['ls-files', '-z', '--others', '--exclude-standard', ...scope], { raw: true }))) {
      files.add(f);
      fromDisk.add(f);
    }
  }
}
for (const args of pendingRms) {
  for (const f of args.filter((a) => !a.startsWith('-'))) {
    for (const tracked of list0(gitx(['ls-files', '-z', '--', f], { raw: true }))) files.add(tracked);
  }
}
if (!files.size) process.exit(0);

/** La configuración de la rama base: la de la rama misma no cuenta (no puede aflojar su medida). */
function impactSettings() {
  for (const ref of ['origin/main', 'main', 'origin/master', 'master', 'HEAD']) {
    const text = gitx(['show', `${ref}:.claude/settings.json`]);
    if (!text) continue;
    try {
      const json = JSON.parse(text);
      const impact = json?.specbox?.impact ?? json?.impact;
      return impact && typeof impact === 'object' ? impact : {};
    } catch {
      return {};
    }
  }
  return {};
}

/** El texto que va al commit: del disco si la orden lo añade o lo commitea por ruta; si no, del índice. */
function after(path) {
  if (fromDisk.has(path)) {
    try {
      return existsSync(join(root, path)) ? readFileSync(join(root, path), 'utf-8') : '';
    } catch {
      return '';
    }
  }
  return gitx(['show', `:${path}`], { raw: true });
}
const versions = (path) => ({ before: gitx(['show', `HEAD:${path}`], { raw: true }), after: after(path) });

const result = classifyCommit([...files], impactSettings(), versions);
const ucId = marker?.uc_id || '';
const head = gitx(['rev-parse', 'HEAD']);
const deciding = result.deciding.map((f) => f.path).sort();

function log(outcome, extra = {}) {
  try {
    mkdirSync(dirname(join(root, LOG)), { recursive: true });
    appendFileSync(join(root, LOG), `${JSON.stringify({
      at: new Date().toISOString(),
      uc_id: ucId || null,
      branch: gitx(['branch', '--show-current']),
      class: result.class,
      needs_approval: result.needs_approval,
      mode,
      outcome,
      files: result.classes,
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

// «block» y contrato o migración: hace falta la aprobación de una persona, gastada en este intento.

/** La huella de lo que se aprueba: cada fichero que decide la clase con el contenido que va al commit. */
const fingerprint = createHash('sha256')
  .update(deciding.map((path) => `${path}\0${createHash('sha256').update(after(path)).digest('hex')}`).join('\n'))
  .digest('hex');

/** FreeForm: el mismo `use_skip` del servidor sobre policy.json. */
function useFreeform() {
  const path = join(trackingDir, 'policy.json');
  const raw = readJsonFile(path);
  if (!raw || typeof raw !== 'object') return null;
  const used = Array.isArray(raw.used_skips) ? raw.used_skips.filter((u) => u && typeof u === 'object') : [];
  const again = used.find((u) => u.measure === MEASURE && u.uc_id === ucId && u.head === head && u.fingerprint === fingerprint);
  if (again?.skip) return { skip: again.skip, reused: true };
  const skips = Array.isArray(raw.skips) ? raw.skips : [];
  const i = skips.findIndex((s) => s?.measure === MEASURE && s?.uc_id === ucId);
  if (i < 0) return null;
  const skip = skips[i];
  const entry = { measure: MEASURE, uc_id: ucId, head, fingerprint, skip, at: new Date().toISOString() };
  try {
    writeFileSync(path, `${JSON.stringify({
      ...raw, skips: [...skips.slice(0, i), ...skips.slice(i + 1)], used_skips: [...used, entry].slice(-MAX_USED_SKIPS),
    }, null, 2)}\n`);
  } catch {
    return null;
  }
  return { skip, reused: false };
}

/** native: la tool use_enforcement_skip con la identidad del dispositivo. */
async function useNative() {
  if (process.env.SPECBOX_ENFORCEMENT_POLICY === 'off') return null;
  try {
    const url = process.env.SPECBOX_MCP_URL || URL_POR_DEFECTO;
    const cabeceras = await cabecerasDelDispositivo({ ...process.env, CLAUDE_CODE_MCP_SERVER_URL: url });
    if (!cabeceras.Authorization) return null;
    const r = await llamarTool({
      url, cabeceras, nombre: 'use_enforcement_skip',
      args: { board_id: boardId, measure: MEASURE, uc_id: ucId, head, fingerprint }, topeMs: 4000,
    });
    return r?.success && r.skip ? { skip: r.skip, reused: !!r.reused } : null;
  } catch {
    return null;
  }
}

const approval = ucId && /^[0-9a-f]{40}/.test(head)
  ? (backendType === 'freeform' ? useFreeform() : backendType === 'native' ? await useNative() : null)
  : null;

if (approval) {
  const { skip, reused } = approval;
  log('approved', { approval: { by: skip.by, at: skip.at, reason: skip.reason, reused, fingerprint } });
  if (!reused) await recordCorrectionIfBlocked({ root, config: board, measure: MEASURE, ucId, by: 'impact-radius-guard' });
  noteWith('PreToolUse', line, [
    `Aprobado por ${skip.by || 'una persona'} (${skip.at || 'sin fecha'}): «${skip.reason || ''}». El commit sigue.`,
  ]);
  process.exit(0);
}

log('blocked', { fingerprint });
if (ucId) await recordEnforcementEvent({ root, config: board, measure: MEASURE, ucId, outcome: 'blocked', by: 'impact-radius-guard' });
blockWith(`COMMIT DETENIDO por la medida impact_radius. ${line}`, [
  'Un cambio de contrato de API o de migración de datos necesita la aprobación de una persona antes del commit, en cualquier nivel de autopilot.',
  ucId
    ? `Para seguir: enseña a la persona todas las clases y los ficheros de arriba y, si lo aprueba, llama a skip_enforcement(measure="impact_radius", uc_id="${ucId}", reason="<qué se aprueba y por qué>") desde la sesión principal (un subagente no puede). La aprobación vale para este commit con este contenido: luego repite el commit.`
    : 'No hay UC activa: empieza la UC con start_uc, pide la aprobación (skip_enforcement con measure="impact_radius" y su uc_id) y repite el commit.',
  'Si el cambio no debía tocar el contrato o la migración, quita esos ficheros del commit.',
]);
