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
