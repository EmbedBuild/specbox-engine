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

/**
 * La orden partida en llamadas (cada una, sus palabras con las comillas resueltas) por `&&`, `||`, `;`,
 * `|`, `&` y saltos de línea fuera de las comillas. El cuerpo de un heredoc y lo que va dentro de
 * `$(…)` no parten nada: un mensaje con «;» o «|» no es otra orden.
 */
function segments(text) {
  const out = [];
  let words = [];
  let cur = '';
  let has = false;
  let heredoc = null;
  const pushWord = () => {
    if (has) words.push(cur);
    cur = '';
    has = false;
  };
  const pushSeg = () => {
    pushWord();
    if (words.length) out.push(words);
    words = [];
  };
  /** `$(…)` desde `i` (en el `$`): el índice tras su `)`, con los paréntesis contados. */
  const skipSubst = (i) => {
    let depth = 0;
    let j = i + 1;
    for (; j < text.length; j += 1) {
      if (text[j] === '(') depth += 1;
      else if (text[j] === ')') {
        depth -= 1;
        if (depth === 0) return j + 1;
      }
    }
    return text.length;
  };
  for (let i = 0; i < text.length; ) {
    const ch = text[i];
    if (ch === "'") {
      const j = text.indexOf("'", i + 1);
      cur += text.slice(i + 1, j < 0 ? text.length : j);
      has = true;
      i = j < 0 ? text.length : j + 1;
    } else if (ch === '"') {
      let j = i + 1;
      while (j < text.length && text[j] !== '"') {
        if (text[j] === '\\' && j + 1 < text.length) { cur += text[j + 1]; j += 2; continue; }
        if (text[j] === '$' && text[j + 1] === '(') { const k = skipSubst(j); cur += text.slice(j, k); j = k; continue; }
        cur += text[j];
        j += 1;
      }
      has = true;
      i = j + 1;
    } else if (ch === '\\' && i + 1 < text.length) {
      cur += text[i + 1];
      has = true;
      i += 2;
    } else if (ch === '$' && text[i + 1] === '(') {
      const k = skipSubst(i);
      cur += text.slice(i, k);
      has = true;
      i = k;
    } else if (ch === '<' && text[i + 1] === '<' && text[i + 2] !== '<') {
      pushWord();
      let j = i + 2;
      if (text[j] === '-') j += 1;
      while (text[j] === ' ' || text[j] === '\t') j += 1;
      let delim = '';
      if (text[j] === "'" || text[j] === '"') {
        const q = text[j];
        const k = text.indexOf(q, j + 1);
        delim = text.slice(j + 1, k < 0 ? text.length : k);
        j = k < 0 ? text.length : k + 1;
      } else {
        while (j < text.length && /[^\s;&|<>()]/.test(text[j])) delim += text[j++];
      }
      heredoc = delim;
      i = j;
    } else if (ch === '\n') {
      if (heredoc !== null) {
        // El cuerpo del heredoc no es parte de la orden: hasta la línea con su delimitador.
        let j = i + 1;
        while (j < text.length) {
          const e = text.indexOf('\n', j);
          const line = text.slice(j, e < 0 ? text.length : e);
          j = e < 0 ? text.length : e + 1;
          if (line.trim() === heredoc) break;
        }
        heredoc = null;
        pushSeg();
        i = j;
      } else {
        pushSeg();
        i += 1;
      }
    } else if ((ch === '&' && text[i + 1] === '&') || (ch === '|' && text[i + 1] === '|')) {
      pushSeg();
      i += 2;
    } else if (ch === ';' || ch === '|' || ch === '&' || ch === '(' || ch === ')') {
      pushSeg();
      i += 1;
    } else if (/\s/.test(ch)) {
      pushWord();
      i += 1;
    } else {
      cur += ch;
      has = true;
      i += 1;
    }
  }
  pushSeg();
  return out;
}

/** Los argumentos de cada llamada a `git <verbo>` de la orden. */
function gitCalls(verb) {
  const calls = [];
  for (const w of segments(command)) {
    const g = w.findIndex((x) => x === 'git' || x.endsWith('/git'));
    if (g < 0) continue;
    let i = g + 1;
    while (i < w.length && w[i].startsWith('-')) i += ['-C', '-c', '--git-dir', '--work-tree', '--namespace'].includes(w[i]) ? 2 : 1;
    if (w[i] === verb) calls.push(w.slice(i + 1));
  }
  return calls;
}

/** Opciones de `git commit` con valor: cortas (también al final de un grupo, «-am "x"») y largas. */
const VALUE_SHORT = new Set(['m', 'F', 'C', 'c', 't']);
const VALUE_LONG = new Set(['--message', '--file', '--reuse-message', '--reedit-message', '--author', '--date',
  '--template', '--fixup', '--squash', '--cleanup', '--trailer', '--pathspec-from-file']);

let all = false;
let include = false;
let pathspecs = [];
for (const args of gitCalls('commit')) {
  for (let i = 0; i < args.length; i += 1) {
    const a = args[i];
    if (a === '--') { pathspecs.push(...args.slice(i + 1)); break; }
    if (a.startsWith('--')) {
      if (a === '--all') all = true;
      else if (a === '--include') include = true;
      else if (!a.includes('=') && VALUE_LONG.has(a)) i += 1;
      continue;
    }
    if (a.startsWith('-') && a.length > 1) {
      // Un grupo de opciones cortas: «-am», «-qm», «-mtexto».
      for (let k = 1; k < a.length; k += 1) {
        const c = a[k];
        if (c === 'a') all = true;
        else if (c === 'i') include = true;
        else if (VALUE_SHORT.has(c)) { if (k === a.length - 1) i += 1; break; }
      }
      continue;
    }
    pathspecs.push(a);
  }
}
pathspecs = pathspecs.filter(Boolean);

const pendingAdds = gitCalls('add');
const pendingRms = gitCalls('rm');
const files = new Set();
const fromDisk = new Set();
const addIndex = () => {
  for (const f of list0(gitx(['diff', '--cached', '--name-only', '-z', '--no-renames'], { raw: true }))) files.add(f);
  if (all) {
    for (const f of list0(gitx(['diff', '--name-only', '-z', '--no-renames', 'HEAD'], { raw: true }))) {
      files.add(f);
      fromDisk.add(f);
    }
  }
};
if (pathspecs.length) {
  // `git commit <ruta>` commitea esas rutas tal como están en el disco (también borradas); con `-i`,
  // además lo que hay en el índice. Si las rutas no resuelven nada, se mira el índice.
  const byPath = list0(gitx(['diff', '--name-only', '-z', '--no-renames', 'HEAD', '--', ...pathspecs], { raw: true }));
  for (const f of byPath) {
    files.add(f);
    fromDisk.add(f);
  }
  if (include || !byPath.length) addIndex();
} else {
  addIndex();
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
  // La rama por defecto del remoto (origin/HEAD, p. ej. origin/develop) y, si no, main o master.
  const defaultRef = gitx(['rev-parse', '--abbrev-ref', 'origin/HEAD']);
  const refs = [...(defaultRef && defaultRef !== 'origin/HEAD' ? [defaultRef] : []), 'origin/main', 'main', 'origin/master', 'master', 'HEAD'];
  for (const ref of refs) {
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
// El primer commit de un repositorio no tiene HEAD: su intento se identifica con el commit nulo.
const head = gitx(['rev-parse', '--verify', '-q', 'HEAD']) || '0'.repeat(40);
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
