/**
 * lib/reservation-probe.mjs — spec-guard pregunta al tablero quién tiene la reserva (UC-12217).
 *
 * Antes pedía GET /api/native/reservation-status, que el servidor no tiene: fallaba siempre, se daba
 * la caché por buena y el bloqueo por reserva perdida no saltaba nunca. Ahora llama a la tool de
 * solo lectura `get_uc_reservation` con la identidad del dispositivo (`llamarTool`, tope de 3 s).
 *
 * - Una respuesta confirmada se guarda 60 s en .quality/reservation_check.json para no preguntar en
 *   cada escritura.
 * - Sin credencial, sin red o sin respuesta: `reachable: false` (se usa la reserva guardada) y una
 *   nota como mucho cada 10 minutos.
 * Nunca lanza.
 */

import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { cabecerasDelDispositivo, URL_POR_DEFECTO } from './heartbeat-send.mjs';
import { llamarTool } from './mcp-client.mjs';

export const CHECK_FILE = join('.quality', 'reservation_check.json');
export const CONFIRMED_MS = 60_000;
export const OFFLINE_NOTE_MS = 10 * 60_000;

function readState(root) {
  try {
    return JSON.parse(readFileSync(join(root, CHECK_FILE), 'utf-8')) || {};
  } catch {
    return {};
  }
}

function writeState(root, state) {
  try {
    const path = join(root, CHECK_FILE);
    mkdirSync(dirname(path), { recursive: true });
    writeFileSync(path, `${JSON.stringify(state)}\n`);
  } catch {
    // sin caché, la próxima escritura vuelve a preguntar
  }
}

/**
 * { reachable, reservation?, why? } para la reserva guardada `{ ucId, developerId }` del proyecto.
 * `why` explica por qué no se pudo comprobar (para la nota).
 */
export async function probeReservation({
  root = process.cwd(),
  projectId,
  reservation,
  env = process.env,
  fetchImpl = fetch,
  cabeceras,
  ahora = Date.now(),
  topeMs = 3000,
} = {}) {
  if (!projectId || !reservation?.ucId) return { reachable: false, why: 'el marcador no dice de qué proyecto es' };
  const state = readState(root);
  const ok = state.confirmed;
  if (ok && ok.uc_id === reservation.ucId && ok.developer_id === reservation.developerId && ahora - ok.at < CONFIRMED_MS) {
    return { reachable: true, reservation: { developer_id: ok.developer_id }, cached: true };
  }
  if (env.SPECBOX_RESERVATION_CHECK === 'off') return { reachable: false, why: 'la comprobación está apagada' };
  const url = env.SPECBOX_MCP_URL || env.SPECBOX_ENGINE_MCP_URL || URL_POR_DEFECTO;
  try {
    const h = cabeceras ?? (await cabecerasDelDispositivo({ ...env, CLAUDE_CODE_MCP_SERVER_URL: url }));
    if (!h.Authorization) return { reachable: false, why: 'este equipo no tiene credencial de SpecBox' };
    const r = await llamarTool({
      url,
      cabeceras: h,
      nombre: 'get_uc_reservation',
      args: { uc_id: reservation.ucId, project_id: projectId },
      topeMs,
      fetchImpl,
    });
    if (!r?.success) return { reachable: false, why: `el tablero no la devolvió (${r?.code || 'sin código'})` };
    const remote = r.reservation ?? null;
    if (remote?.developer_id === reservation.developerId) {
      writeState(root, { ...state, confirmed: { uc_id: reservation.ucId, developer_id: remote.developer_id, at: ahora } });
    }
    return { reachable: true, reservation: remote };
  } catch {
    return { reachable: false, why: 'sin red o sin respuesta en 3 s' };
  }
}

/** True si toca dar la nota de «no se pudo comprobar» (como mucho cada 10 minutos); la apunta. */
export function shouldNoteOffline(root = process.cwd(), ahora = Date.now()) {
  const state = readState(root);
  if (typeof state.offline_note_at === 'number' && ahora - state.offline_note_at < OFFLINE_NOTE_MS) return false;
  writeState(root, { ...state, offline_note_at: ahora });
  return true;
}
