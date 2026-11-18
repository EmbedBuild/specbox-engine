/**
 * lib/uc-usage.mjs — los tokens nuevos de una transcripción de Claude Code (US-124 · UC-12403).
 *
 * Claude Code guarda cada sesión en un JSONL; cada respuesta del modelo lleva `message.usage`
 * (`input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`) y
 * puede aparecer en varias líneas con el mismo `message.id`: se cuenta una vez, con su último uso.
 * Las de los subagentes van en `<sesión>/subagents/agent-<id>.jsonl`. El formato no está
 * documentado: una línea que no se reconoce no cuenta, y si nada se reconoce no se envía nada
 * (la UC queda «estimado»). De la transcripción solo salen esas cuatro cifras: nunca texto.
 *
 * Puro salvo `leerDesde` (lee el fichero). Lo usan el hook `uc-usage.mjs` y sus pruebas.
 */

import { createHash } from 'node:crypto';
import { closeSync, openSync, readSync, statSync } from 'node:fs';
import { dirname, join } from 'node:path';

export const CAMPOS = ['input_tokens', 'output_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens'];
/** Ids de respuesta ya contados que guarda el cursor (los últimos). */
export const MAX_IDS = 500;
/** Lo más que se lee de una vez: con más atraso, solo la cola. */
export const MAX_LECTURA = 32 * 1024 * 1024;

const AGENTE = /^[A-Za-z0-9_.:-]{1,128}$/;

/** Qué transcripción leer: la del subagente si el evento es suyo; si no, la de la sesión. */
export function transcriptDe(entrada = {}) {
  const agente = typeof entrada.agent_id === 'string' && AGENTE.test(entrada.agent_id) ? entrada.agent_id : '';
  if (agente) {
    if (typeof entrada.agent_transcript_path === 'string' && entrada.agent_transcript_path) {
      return { ruta: entrada.agent_transcript_path, agente, principal: false };
    }
    if (typeof entrada.transcript_path === 'string' && entrada.transcript_path && entrada.session_id) {
      const ruta = join(dirname(entrada.transcript_path), String(entrada.session_id), 'subagents', `agent-${agente}.jsonl`);
      return { ruta, agente, principal: false };
    }
    return null;
  }
  if (typeof entrada.transcript_path === 'string' && entrada.transcript_path) {
    return { ruta: entrada.transcript_path, agente: '', principal: true };
  }
  return null;
}

/** El fichero del cursor de una transcripción, dentro de `dir`. */
export function rutaCursor(dir, ruta) {
  return join(dir, `${createHash('sha1').update(ruta).digest('hex').slice(0, 16)}.json`);
}

/**
 * Las líneas completas desde `offset` y el offset nuevo (en bytes). Si el fichero encogió, desde
 * el principio; con más de `tope` bytes pendientes, solo la cola, desde un principio de línea.
 */
export function leerDesde(ruta, offset = 0, tope = MAX_LECTURA) {
  const tam = statSync(ruta).size;
  let inicio = Number.isInteger(offset) && offset >= 0 && offset <= tam ? offset : 0;
  let saltarPrimera = false;
  if (tam - inicio > tope) {
    inicio = tam - tope;
    saltarPrimera = true;
  }
  if (tam === inicio) return { lineas: [], offset: inicio };
  const buf = Buffer.alloc(tam - inicio);
  const fd = openSync(ruta, 'r');
  try {
    readSync(fd, buf, 0, buf.length, inicio);
  } finally {
    closeSync(fd);
  }
  const ultimo = buf.lastIndexOf(0x0a);
  if (ultimo < 0) return { lineas: [], offset: inicio };
  let desde = 0;
  if (saltarPrimera) desde = buf.indexOf(0x0a) + 1;
  const lineas = buf.subarray(desde, ultimo).toString('utf8').split('\n');
  return { lineas, offset: inicio + ultimo + 1 };
}

/**
 * Los tokens de `lineas`: cada respuesta (`message.id`) una vez, con el último uso que trae, sin
 * las ya contadas (`vistos`), sin las de los subagentes en la transcripción principal y sin las
 * anteriores a `desde` (cuando empezó la UC). Devuelve las cuatro cifras, `messages` (respuestas
 * contadas) e `ids` (las nuevas, para el cursor). Nada más sale de la transcripción.
 */
export function sumarUso(lineas, vistos = [], { principal = false, desde = null } = {}) {
  const previos = new Set(vistos);
  const limite = desde ? Date.parse(desde) : NaN;
  const ultimos = new Map();
  for (const linea of lineas) {
    if (!linea || !linea.trim()) continue;
    let d;
    try {
      d = JSON.parse(linea);
    } catch {
      continue;
    }
    if (principal && d?.isSidechain === true) continue;
    const m = d?.message;
    const uso = m?.usage;
    if (!uso || typeof uso !== 'object' || typeof m.id !== 'string' || !m.id) continue;
    if (previos.has(m.id)) continue;
    if (!Number.isNaN(limite) && typeof d.timestamp === 'string') {
      const t = Date.parse(d.timestamp);
      if (!Number.isNaN(t) && t < limite) continue;
    }
    ultimos.set(m.id, uso);
  }
  const totales = Object.fromEntries(CAMPOS.map((c) => [c, 0]));
  for (const uso of ultimos.values()) {
    for (const c of CAMPOS) {
      const n = uso[c];
      if (Number.isSafeInteger(n) && n >= 0) totales[c] += n;
    }
  }
  return { ...totales, messages: ultimos.size, ids: [...ultimos.keys()] };
}

/** Lo que se envía a `report_uc_usage`: identificadores y cifras, nada más (AC-04). */
export function informe({ proyecto, uc, sesion, agente, uso }) {
  return {
    project_id: proyecto,
    uc_id: uc,
    session_id: sesion,
    agent_id: agente || '',
    ...Object.fromEntries(CAMPOS.map((c) => [c, uso[c]])),
    messages: uso.messages,
  };
}
