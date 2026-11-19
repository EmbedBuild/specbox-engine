/**
 * lib/server-version.mjs — la versión del servidor MCP, para no mandarle parámetros que no conoce.
 *
 * Un hook nuevo puede hablar con un servidor anterior (uno propio, o el alojado en los minutos entre
 * la etiqueta y el despliegue), y un parámetro que el servidor no declara hace fallar la tool. El hook
 * pregunta antes con `serverAtLeast`: lee `/health` (`{status, version}`) con un tope de 2 s y guarda
 * la respuesta 10 minutos en `.quality/logs/mcp_server_version.json` (también un fallo, como versión
 * nula, para no esperar 2 s en cada llamada). Sin respuesta, la versión es nula y no se cumple ningún
 * mínimo. La URL sale de `SPECBOX_MCP_URL`, como en el resto de hooks.
 */

import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { URL_POR_DEFECTO } from './heartbeat-send.mjs';

export const CACHE_FILE = join('.quality', 'logs', 'mcp_server_version.json');
const TTL_MS = 10 * 60 * 1000;
const TIMEOUT_MS = 2000;

/** La URL de /health del servidor MCP (`…/mcp` → `…/health`). */
export function healthUrl(mcpUrl) {
  const url = String(mcpUrl || URL_POR_DEFECTO);
  if (/\/mcp\/?$/.test(url)) return url.replace(/\/mcp\/?$/, '/health');
  try {
    return new URL('/health', url).toString();
  } catch {
    return '';
  }
}

/** ¿`version` (x.y.z) es `min` o posterior? Una versión ilegible no cumple. */
export function atLeast(version, min) {
  const parse = (v) => {
    const m = /^(\d+)\.(\d+)\.(\d+)/.exec(String(v || ''));
    return m ? m.slice(1).map(Number) : null;
  };
  const a = parse(version);
  const b = parse(min);
  if (!a || !b) return false;
  for (let i = 0; i < 3; i += 1) if (a[i] !== b[i]) return a[i] > b[i];
  return true;
}

/** La versión del servidor (o null), de la caché si es reciente. */
export async function serverVersion({ root, env = process.env, fetchImpl = fetch, now = Date.now() } = {}) {
  const url = healthUrl(env.SPECBOX_MCP_URL);
  const path = join(root, CACHE_FILE);
  try {
    const cached = JSON.parse(readFileSync(path, 'utf-8'));
    if (cached?.url === url && typeof cached.at === 'number' && now - cached.at >= 0 && now - cached.at < TTL_MS) {
      return typeof cached.version === 'string' ? cached.version : null;
    }
  } catch {
    // sin caché: se pregunta
  }
  let version = null;
  if (url) {
    const control = new AbortController();
    const timer = setTimeout(() => control.abort(), TIMEOUT_MS);
    try {
      const res = await fetchImpl(url, { signal: control.signal });
      const body = res.ok ? await res.json() : null;
      if (typeof body?.version === 'string') version = body.version;
    } catch {
      // sin respuesta: versión nula
    } finally {
      clearTimeout(timer);
    }
  }
  try {
    mkdirSync(join(root, '.quality', 'logs'), { recursive: true });
    writeFileSync(path, JSON.stringify({ url, version, at: now }), 'utf-8');
  } catch {
    // la caché es una ayuda
  }
  return version;
}

/** ¿El servidor es `min` o posterior? */
export async function serverAtLeast(min, opts) {
  return atLeast(await serverVersion(opts), min);
}
