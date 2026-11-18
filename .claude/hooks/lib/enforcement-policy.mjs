/**
 * lib/enforcement-policy.mjs — el modo de cada medida de EP-20 visto desde los hooks (US-122 · UC-12212).
 *
 * Los hooks y el servidor leen el mismo modo del tablero:
 *
 * - FreeForm: doc/tracking/policy.json, el mismo fichero que el servidor recibe en `policy_content`
 *   (MCP remoto) o lee del disco (MCP local).
 * - native: la tool `get_enforcement_policy` con la identidad del dispositivo; la respuesta se guarda
 *   en .quality/enforcement_policy.json durante 10 minutos. Sin red se usa la última copia y, sin
 *   copia, «warn».
 * - Trello y Plane: «warn» como máximo, como en el servidor.
 *
 * Un tablero sin política es uno que ya existía: todo en «warn». El catálogo es el de
 * server/coordination/enforcement.py; tests/test_enforcement.py comprueba que coinciden.
 * Nunca lanza: una política que no se puede leer se trata como «warn».
 */

import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { cabecerasDelDispositivo, URL_POR_DEFECTO } from './heartbeat-send.mjs';
import { llamarTool } from './mcp-client.mjs';

export const MODES = ['off', 'warn', 'block'];
export const CAPPED_BACKENDS = new Set(['trello', 'plane']);
export const CACHE_MS = 10 * 60 * 1000;
export const CACHE_FILE = join('.quality', 'enforcement_policy.json');

/** Clave → modo de un proyecto nuevo. Mismo orden y valores que MEASURES en el servidor. */
export const MEASURES = {
  context_budget: 'warn',
  spec_in_pr: 'warn',
  spec_quality: 'warn',
  pending_decisions: 'warn',
  closing_evidence: 'warn',
  independent_review: 'warn',
  ac_approval: 'warn',
  drift_gate: 'warn',
  impact_radius: 'warn',
  contract_first: 'warn',
};

/** El modo de cada medida a partir de lo guardado (o null), como effective_policy del servidor. */
export function modosDe(raw, backendType) {
  const origin = raw && (raw.origin === 'new' || raw.origin === 'existing') ? raw.origin : 'existing';
  const guardadas = raw && typeof raw.measures === 'object' && raw.measures ? raw.measures : {};
  const modos = {};
  for (const [clave, nuevo] of Object.entries(MEASURES)) {
    const entrada = guardadas[clave];
    let modo = entrada && MODES.includes(entrada.mode) ? entrada.mode : origin === 'new' ? nuevo : 'warn';
    if (CAPPED_BACKENDS.has(backendType) && modo === 'block') modo = 'warn';
    modos[clave] = modo;
  }
  return { origin, backendType, modos };
}

/** El modo de una medida en una política leída con leerPolitica («warn» si no la conoce). */
export function modoDe(politica, medida) {
  const modo = politica?.modos?.[medida];
  return MODES.includes(modo) ? modo : 'warn';
}

function leerJson(ruta) {
  try {
    return JSON.parse(readFileSync(ruta, 'utf-8'));
  } catch {
    return null;
  }
}

/** La política native de la caché si es de este proyecto (y su edad), o null. */
function deLaCache(root, proyecto) {
  const copia = leerJson(join(root, CACHE_FILE));
  if (!copia || copia.project_id !== proyecto || typeof copia.fetched_at !== 'number') return null;
  return copia;
}

/**
 * La política del proyecto: { origin, backendType, modos, fuente }.
 * `fuente` dice de dónde salió: policy.json, tablero, caché, caché antigua o por defecto.
 */
export async function leerPolitica({
  root = process.cwd(),
  backendType = '',
  boardId = '',
  trackingDir = '',
  env = process.env,
  fetchImpl = fetch,
  cabeceras,
  ahora = Date.now(),
  topeMs = 2500,
} = {}) {
  if (CAPPED_BACKENDS.has(backendType)) return { ...modosDe(null, backendType), fuente: 'por defecto' };

  if (backendType === 'freeform') {
    const ruta = join(trackingDir || join(root, 'doc', 'tracking'), 'policy.json');
    const raw = existsSync(ruta) ? leerJson(ruta) : null;
    return { ...modosDe(raw, backendType), fuente: raw ? 'policy.json' : 'por defecto' };
  }

  if (backendType !== 'native' || !boardId) return { ...modosDe(null, backendType), fuente: 'por defecto' };

  const copia = deLaCache(root, boardId);
  if (copia && ahora - copia.fetched_at < CACHE_MS) return { ...modosDe(copia.policy, 'native'), fuente: 'caché' };

  if (env.SPECBOX_ENFORCEMENT_POLICY !== 'off') {
    try {
      const url = env.SPECBOX_MCP_URL || URL_POR_DEFECTO;
      const h = cabeceras ?? (await cabecerasDelDispositivo({ ...env, CLAUDE_CODE_MCP_SERVER_URL: url }));
      if (h.Authorization) {
        const r = await llamarTool({
          url,
          cabeceras: h,
          nombre: 'get_enforcement_policy',
          args: { board_id: boardId },
          topeMs,
          fetchImpl,
        });
        if (r?.success && r.policy) {
          // Se guarda lo que el servidor considera guardado: origen y modo de cada medida.
          const policy = {
            origin: r.policy.origin,
            measures: Object.fromEntries(
              Object.entries(r.policy.measures || {}).map(([k, v]) => [k, { mode: v?.mode }]),
            ),
          };
          try {
            const destino = join(root, CACHE_FILE);
            mkdirSync(dirname(destino), { recursive: true });
            writeFileSync(destino, `${JSON.stringify({ project_id: boardId, fetched_at: ahora, policy }, null, 2)}\n`);
          } catch {
            // sin caché la próxima vez se vuelve a preguntar
          }
          return { ...modosDe(policy, 'native'), fuente: 'tablero' };
        }
      }
    } catch {
      // sin red o con el tablero caído: la última copia o «warn»
    }
  }
  if (copia) return { ...modosDe(copia.policy, 'native'), fuente: 'caché antigua' };
  return { ...modosDe(null, 'native'), fuente: 'por defecto' };
}

/** El texto de un aviso o de un bloqueo de una medida: medida, motivo y cómo seguir (AC-06). */
export function textoDeMedida({ medida, modo, motivo, comoSeguir }) {
  const que = modo === 'block' ? 'SpecBox detuvo la operación' : 'Aviso de SpecBox';
  return `${que} por la medida ${medida}. Motivo: ${motivo} Cómo seguir: ${comoSeguir}`;
}
