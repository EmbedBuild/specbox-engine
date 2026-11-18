/**
 * lib/uc-state.mjs — lo que el estado de una UC deja en el proyecto (UC-12216).
 *
 * Con el MCP remoto el servidor no ve el disco del proyecto: `start_uc` devuelve el marcador de UC
 * activa (`active_uc_marker`) y el hook uc-state-marker lo escribe en .quality/active_uc.json, que
 * leen spec-guard, commit-spec-guard y uc-lifecycle-guard. Funciones puras y una escritura atómica.
 */

import { existsSync, mkdirSync, readFileSync, renameSync, unlinkSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';

export const MARKER_FILE = join('.quality', 'active_uc.json');
const UC_ID = /^UC-\d{1,6}[a-z]?$/;

function parse(text) {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

/** El primer valor de `key` dentro de una respuesta MCP, tenga la forma que tenga. */
export function findValue(response, key, depth = 0) {
  if (depth > 6 || response == null) return undefined;
  if (typeof response === 'string') {
    const text = response.trim();
    return text.startsWith('{') || text.startsWith('[') ? findValue(parse(text), key, depth + 1) : undefined;
  }
  if (Array.isArray(response)) {
    for (const part of response) {
      const found = findValue(part, key, depth + 1);
      if (found !== undefined) return found;
    }
    return undefined;
  }
  if (typeof response === 'object') {
    if (key in response) return response[key];
    for (const value of Object.values(response)) {
      const found = findValue(value, key, depth + 1);
      if (found !== undefined) return found;
    }
  }
  return undefined;
}

/** El objeto de primer nivel de una respuesta MCP: structuredContent, el texto JSON o el propio objeto. */
export function topObject(response, depth = 0) {
  if (depth > 4 || response == null) return null;
  if (typeof response === 'string') {
    const text = response.trim();
    return text.startsWith('{') || text.startsWith('[') ? topObject(parse(text), depth + 1) : null;
  }
  if (Array.isArray(response)) {
    for (const part of response) {
      const found = topObject(part?.type === 'text' ? part.text : part, depth + 1);
      if (found) return found;
    }
    return null;
  }
  if (typeof response === 'object') {
    if (response.structuredContent && typeof response.structuredContent === 'object') return response.structuredContent;
    if (Array.isArray(response.content)) return topObject(response.content, depth + 1);
    if (response.isError === true) return { error: 'isError' };
    return response;
  }
  return null;
}

/** True si la respuesta es un error de la tool (no hay nada que apuntar). Solo mira el primer nivel. */
export function isError(response) {
  const top = topObject(response);
  if (!top) return true; // sin respuesta legible no se toca nada
  const error = top.error;
  return (error !== undefined && error !== null && error !== false && error !== '') || top.success === false;
}

/** El marcador que hay que escribir tras start_uc, o null si la respuesta no trae uno válido. */
export function markerFrom(response) {
  if (isError(response)) return null;
  const marker = topObject(response)?.active_uc_marker;
  if (!marker || typeof marker !== 'object' || !UC_ID.test(String(marker.uc_id || ''))) return null;
  return marker;
}

function writeAtomic(path, content) {
  mkdirSync(dirname(path), { recursive: true });
  const tmp = `${path}.${process.pid}.tmp`;
  writeFileSync(tmp, content, 'utf-8');
  renameSync(tmp, path);
}

/** Escribe el marcador de UC activa en `root`. Devuelve la ruta escrita. */
export function writeMarker(root, marker) {
  const path = join(root, MARKER_FILE);
  writeAtomic(path, `${JSON.stringify(marker, null, 2)}\n`);
  return path;
}

/** Borra el marcador si es de `ucId` (o si no dice de qué UC es). Devuelve true si lo borró. */
export function clearMarker(root, ucId) {
  const path = join(root, MARKER_FILE);
  if (!existsSync(path)) return false;
  const current = parse(readFileSync(path, 'utf-8'));
  if (current?.uc_id && ucId && current.uc_id !== ucId) return false; // es de otra UC: se queda
  unlinkSync(path);
  return true;
}

// ── Lo que mira uc-lifecycle-guard al hacer push (UC-12206) ─────────────

export const AC_MARKED = 'ac_marked.json';
export const MOVED_TO_REVIEW = 'uc_moved_to_review.json';

/** Los id de los criterios de la UC según la respuesta de start_uc (para saber cuáles faltan). */
export function acIdsFrom(response) {
  const acs = topObject(response)?.acceptance_criteria;
  return Array.isArray(acs) ? acs.map((a) => String(a?.id || a?.ac_id || '')).filter(Boolean) : [];
}

/** El marcador de UC activa del proyecto, o null. */
export function readMarker(root) {
  const path = join(root, MARKER_FILE);
  return existsSync(path) ? parse(readFileSync(path, 'utf-8')) : null;
}

/** La carpeta de evidencia de una UC: la `feature` del marcador si es la activa; si no, su id. */
export function evidenceDir(root, ucId) {
  const marker = readMarker(root);
  const feature = marker?.uc_id === ucId && marker.feature ? marker.feature : ucId;
  return join(root, '.quality', 'evidence', String(feature).replace(/[^A-Za-z0-9._-]/g, '_'));
}

/**
 * Suma a ac_marked.json lo que marcó mark_ac_batch: los criterios cumplidos y los no cumplidos.
 * Un criterio que pasa después de haber fallado sale de los no cumplidos.
 */
export function recordMarkedAcs(root, ucId, response, now = new Date().toISOString()) {
  const details = topObject(response)?.details;
  if (!Array.isArray(details)) return null;
  const path = join(evidenceDir(root, ucId), AC_MARKED);
  const before = existsSync(path) ? parse(readFileSync(path, 'utf-8')) || {} : {};
  const passed = new Set(Array.isArray(before.passed) ? before.passed : []);
  const failed = new Set(Array.isArray(before.failed) ? before.failed : []);
  for (const d of details) {
    const id = String(d?.ac_id || '');
    if (!id) continue;
    if (d.passed) {
      passed.add(id);
      failed.delete(id);
    } else {
      failed.add(id);
      passed.delete(id);
    }
  }
  const out = { uc_id: ucId, passed: [...passed].sort(), failed: [...failed].sort(), at: now };
  writeAtomic(path, `${JSON.stringify(out, null, 2)}\n`);
  return out;
}

/** move_uc: a revisión deja uc_moved_to_review.json; a cualquier otro estado lo quita. */
export function recordMove(root, ucId, target, now = new Date().toISOString()) {
  const path = join(evidenceDir(root, ucId), MOVED_TO_REVIEW);
  if (target === 'review') {
    writeAtomic(path, `${JSON.stringify({ uc_id: ucId, at: now }, null, 2)}\n`);
    return true;
  }
  if (existsSync(path)) unlinkSync(path);
  return false;
}
