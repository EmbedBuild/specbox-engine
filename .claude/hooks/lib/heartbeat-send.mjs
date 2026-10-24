#!/usr/bin/env node
/**
 * lib/heartbeat-send.mjs — envía un latido al board, en su propio proceso (US-99 · UC-9901).
 *
 * Lo lanza session-heartbeat.mjs sin esperarlo: la sesión nunca espera al board. Usa la misma
 * credencial que Claude Code para el MCP de SpecBox (~/.specbox/bin/mcp-headers.mjs) y un tope de
 * 3 s. Si el board no responde, lo anota en .quality/logs/heartbeat.log, como mucho una vez por
 * minuto, y termina (AC-03). Nunca escribe la credencial ni el latido en el registro.
 *
 * Uso: node heartbeat-send.mjs <raíz del repo> '<latido en JSON>'
 */

import { appendFileSync, mkdirSync, readFileSync, writeFileSync, realpathSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { llamarTool } from './mcp-client.mjs';

export const URL_POR_DEFECTO = 'https://mcp.specbox.build/mcp';
export const REGISTRO = '.quality/logs/heartbeat.log';
const MARCA = '.quality/heartbeat_error.json';

/** Anota un fallo si no se anotó otro en el último minuto. Devuelve si lo anotó. */
export function anotarFallo(raiz, motivo, ahora = Date.now()) {
  const marca = join(raiz, MARCA);
  let ultimo = 0;
  try {
    ultimo = JSON.parse(readFileSync(marca, 'utf8')).at || 0;
  } catch {
    ultimo = 0;
  }
  if (ahora - ultimo < 60_000) return false;
  try {
    mkdirSync(join(raiz, '.quality/logs'), { recursive: true });
    appendFileSync(join(raiz, REGISTRO), `${new Date(ahora).toISOString()} latido no enviado: ${motivo}\n`);
    writeFileSync(marca, JSON.stringify({ at: ahora }));
  } catch {
    return false;
  }
  return true;
}

/** La cabecera Authorization del dispositivo, o {} si este equipo no tiene credencial. */
export async function cabecerasDelDispositivo(env = process.env) {
  const ayudante = join(env.SPECBOX_HOME || join(homedir(), '.specbox'), 'bin', 'mcp-headers.mjs');
  try {
    const modulo = await import(pathToFileURL(ayudante).href);
    return (await modulo.headersFor({ env })) || {};
  } catch {
    return {};
  }
}

/** Manda el latido. Nunca lanza: devuelve true si el board lo aceptó. */
export async function enviarLatido({ raiz, latido, env = process.env, fetchImpl = fetch, cabeceras, ahora = Date.now }) {
  const url = env.SPECBOX_MCP_URL || URL_POR_DEFECTO;
  const h = cabeceras ?? (await cabecerasDelDispositivo({ ...env, CLAUDE_CODE_MCP_SERVER_URL: url }));
  if (!h.Authorization) {
    anotarFallo(raiz, 'este equipo no tiene credencial de SpecBox (specbox login)', ahora());
    return false;
  }
  try {
    const r = await llamarTool({ url, cabeceras: h, nombre: 'report_session_heartbeat', args: latido, fetchImpl });
    if (r?.success === false) {
      anotarFallo(raiz, `el board lo rechazó (${r.code || 'sin código'})`, ahora());
      return false;
    }
    return true;
  } catch (err) {
    anotarFallo(raiz, err?.message || 'fallo', ahora());
    return false;
  }
}

const directo = (() => {
  try {
    return Boolean(process.argv[1]) && import.meta.url === pathToFileURL(realpathSync(process.argv[1])).href;
  } catch {
    return false;
  }
})();
if (directo) {
  let latido = null;
  try {
    latido = JSON.parse(process.argv[3] || 'null');
  } catch {
    latido = null;
  }
  const raiz = process.argv[2] || process.cwd();
  (latido ? enviarLatido({ raiz, latido }) : Promise.resolve(false)).finally(() => process.exit(0));
}
