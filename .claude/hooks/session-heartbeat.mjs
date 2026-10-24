#!/usr/bin/env node
/**
 * session-heartbeat.mjs — el latido de la sesión al board (US-99 · UC-9901).
 * NO BLOQUEA y es silencioso: nunca escribe nada para el agente ni sale con error.
 *
 * Eventos: SessionStart, PostToolUse, Notification, UserPromptSubmit y SessionEnd. Calcula el
 * latido (UC activa, fase del pipeline, si espera un permiso o una decisión) y, si toca (al empezar,
 * al cerrar, al cambiar algo o cada dos minutos), lo manda en un proceso aparte que no se espera
 * (lib/heartbeat-send.mjs, con tope de 3 s). Solo en proyectos con board native.
 *
 * SPECBOX_HEARTBEAT=off lo apaga. SPECBOX_HEARTBEAT_DRY_RUN=<fichero> escribe el latido en ese
 * fichero en vez de enviarlo (pruebas).
 */

import { spawn } from 'node:child_process';
import { appendFileSync, existsSync, readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { getProjectConfig } from './lib/config.mjs';
import { latido, tocaEnviar } from './lib/heartbeat.mjs';
import { fileAge, git, mkdir, readHookInput, readJsonFile } from './lib/utils.mjs';

const ESTADO = '.quality/heartbeat_state.json';
/** Lo que el latido deja en el repo y nunca va a git (como read-tracker). */
const IGNORADOS = ['heartbeat_state.json', 'heartbeat_error.json', 'logs/heartbeat.log'];

function asegurarIgnorados() {
  const ruta = '.quality/.gitignore';
  let actual = '';
  try {
    actual = readFileSync(ruta, 'utf8');
  } catch {
    actual = '';
  }
  const faltan = IGNORADOS.filter((l) => !actual.split('\n').includes(l));
  if (faltan.length === 0) return;
  try {
    appendFileSync(ruta, `${actual && !actual.endsWith('\n') ? '\n' : ''}${faltan.join('\n')}\n`);
  } catch {
    // solo lectura: no pasa nada
  }
}

/** El fichero más reciente con ese nombre en .quality/evidence/<feature>/, y su edad en segundos. */
function masReciente(nombre) {
  const base = '.quality/evidence';
  if (!existsSync(base)) return { datos: null, edad: Infinity };
  let mejor = null;
  for (const feature of readdirSync(base)) {
    const ruta = join(base, feature, nombre);
    try {
      const t = statSync(ruta).mtimeMs;
      if (!mejor || t > mejor.t) mejor = { ruta, t };
    } catch {
      // no existe en esta feature
    }
  }
  if (!mejor) return { datos: null, edad: Infinity };
  return { datos: readJsonFile(mejor.ruta), edad: (Date.now() - mejor.t) / 1000 };
}

/** La rama actual sin lanzar git cuando el repo es normal (.git/HEAD). */
function ramaActual() {
  try {
    const head = readFileSync('.git/HEAD', 'utf8').trim();
    if (head.startsWith('ref: refs/heads/')) return head.slice('ref: refs/heads/'.length);
  } catch {
    // worktree o sin repo: se pregunta a git
  }
  return git('branch --show-current');
}

try {
  if (process.env.SPECBOX_HEARTBEAT === 'off') process.exit(0);
  const { event, payload } = readHookInput();
  const { boardId, backendType } = getProjectConfig();
  if (backendType !== 'native' || !boardId) process.exit(0);

  const anterior = readJsonFile(ESTADO);
  const marcador = fileAge('.quality/active_uc.json') < 86400 ? readJsonFile('.quality/active_uc.json') : null;
  const pipeline = masReciente('pipeline_state.json');
  const checkpoint = masReciente('checkpoint.json');
  const nuevo = latido({
    evento: event,
    entrada: payload,
    proyecto: boardId,
    marcador,
    rama: ramaActual(),
    pipeline: pipeline.edad < 2 * 3600 ? pipeline.datos : null,
    checkpoint: checkpoint.datos,
    checkpointEdadS: checkpoint.edad,
    anterior,
  });
  const ahora = Date.now();
  if (tocaEnviar(nuevo, anterior, ahora)) {
    mkdir('.quality');
    asegurarIgnorados();
    writeFileSync(ESTADO, JSON.stringify({ ...nuevo, sent_at: ahora }));
    if (process.env.SPECBOX_HEARTBEAT_DRY_RUN) {
      appendFileSync(process.env.SPECBOX_HEARTBEAT_DRY_RUN, `${JSON.stringify(nuevo)}\n`);
    } else {
      const enviar = join(dirname(fileURLToPath(import.meta.url)), 'lib', 'heartbeat-send.mjs');
      const hijo = spawn(process.execPath, [enviar, process.cwd(), JSON.stringify(nuevo)], {
        detached: true,
        stdio: 'ignore',
      });
      hijo.unref();
    }
  }
} catch {
  // El latido nunca molesta a la sesión.
}
process.exit(0);
