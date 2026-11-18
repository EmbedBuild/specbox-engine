#!/usr/bin/env node
/**
 * lib/uc-usage-send.mjs — envía los tokens nuevos de una UC al board, en su propio proceso
 * (US-124 · UC-12403).
 *
 * Lo lanza uc-usage.mjs sin esperarlo: la sesión nunca espera al board. Usa la credencial del
 * dispositivo (como el latido) y llama a `report_uc_usage`. Solo si el board lo acepta escribe el
 * cursor nuevo: si falla, el siguiente envío lleva también estas cifras. El fallo se anota en
 * .quality/logs/uc-usage.log como mucho una vez por minuto, sin credenciales ni cifras. Al
 * terminar borra la marca de envío en curso.
 *
 * Uso: node uc-usage-send.mjs <raíz> '<informe JSON>' <fichero del cursor> '<cursor JSON>'
 */

import { appendFileSync, mkdirSync, readFileSync, realpathSync, rmSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { cabecerasDelDispositivo, URL_POR_DEFECTO } from './heartbeat-send.mjs';
import { llamarTool } from './mcp-client.mjs';

export const REGISTRO = '.quality/logs/uc-usage.log';
const MARCA = '.quality/uc_usage_error.json';

function anotarFallo(raiz, motivo, ahora = Date.now()) {
  const marca = join(raiz, MARCA);
  let ultimo = 0;
  try {
    ultimo = JSON.parse(readFileSync(marca, 'utf8')).at || 0;
  } catch {
    ultimo = 0;
  }
  if (ahora - ultimo < 60_000) return;
  try {
    mkdirSync(join(raiz, '.quality/logs'), { recursive: true });
    appendFileSync(join(raiz, REGISTRO), `${new Date(ahora).toISOString()} tokens de la UC no enviados: ${motivo}\n`);
    writeFileSync(marca, JSON.stringify({ at: ahora }));
  } catch {
    // solo lectura: no pasa nada
  }
}

/** Manda el informe y, si el board lo acepta, guarda el cursor. Nunca lanza. */
export async function enviarUso({ raiz, informe, cursorRuta, cursor, env = process.env, fetchImpl = fetch, cabeceras }) {
  try {
    const url = env.SPECBOX_MCP_URL || URL_POR_DEFECTO;
    const h = cabeceras ?? (await cabecerasDelDispositivo({ ...env, CLAUDE_CODE_MCP_SERVER_URL: url }));
    if (!h.Authorization) {
      anotarFallo(raiz, 'este equipo no tiene credencial de SpecBox (specbox login)');
      return false;
    }
    const r = await llamarTool({ url, cabeceras: h, nombre: 'report_uc_usage', args: informe, fetchImpl });
    if (r?.success === false) {
      anotarFallo(raiz, `el board lo rechazó (${r.code || 'sin código'})`);
      // Un rechazo por los datos no se arregla reenviando: el cursor avanza.
      if (r.code === 'INVALID_USAGE' || r.code === 'UC_NOT_FOUND') writeFileSync(cursorRuta, JSON.stringify(cursor));
      return false;
    }
    writeFileSync(cursorRuta, JSON.stringify(cursor));
    return true;
  } catch (err) {
    anotarFallo(raiz, err?.message || 'fallo');
    return false;
  } finally {
    rmSync(`${cursorRuta}.pending`, { force: true });
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
  let informe = null;
  let cursor = null;
  try {
    informe = JSON.parse(process.argv[3] || 'null');
    cursor = JSON.parse(process.argv[5] || 'null');
  } catch {
    informe = null;
  }
  const raiz = process.argv[2] || process.cwd();
  const cursorRuta = process.argv[4];
  (informe && cursor && cursorRuta ? enviarUso({ raiz, informe, cursorRuta, cursor }) : Promise.resolve(false)).finally(
    () => process.exit(0),
  );
}
