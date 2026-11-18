#!/usr/bin/env node
/**
 * uc-usage.mjs — el coste real de la UC activa en tokens (US-124 · UC-12403).
 * NO BLOQUEA y es silencioso: nunca escribe nada para el agente ni sale con error.
 *
 * Eventos: Stop (al terminar cada turno de la sesión), SubagentStop (al terminar cada subagente) y
 * PreToolUse de complete_uc (lo último antes de cerrar, que después ya no hay UC activa). Lee de la
 * transcripción lo nuevo desde su cursor (`.quality/uc_usage/`), suma `message.usage` contando cada
 * respuesta una vez y solo desde que empezó la UC, y lo manda a la UC activa con `report_uc_usage`
 * en un proceso aparte que no se espera (lib/uc-usage-send.mjs). Solo cifras, nunca texto (AC-04).
 * Solo en proyectos con board native; si el formato de la transcripción no se reconoce, no manda
 * nada y la UC queda «estimado».
 *
 * SPECBOX_UC_USAGE=off lo apaga. SPECBOX_UC_USAGE_DRY_RUN=<fichero> escribe el informe en ese
 * fichero (y avanza el cursor) en vez de enviarlo (pruebas).
 */

import { spawn } from 'node:child_process';
import { appendFileSync, existsSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { getProjectConfig } from './lib/config.mjs';
import { MAX_IDS, informe, leerDesde, rutaCursor, sumarUso, transcriptDe } from './lib/uc-usage.mjs';
import { fileAge, mkdir, readHookInput, readJsonFile } from './lib/utils.mjs';

const DIR = '.quality/uc_usage';
/** Un envío en curso más reciente que esto hace esperar al siguiente evento (sin contar doble). */
const EN_CURSO_MS = 10_000;
const IGNORADOS = ['uc_usage/', 'uc_usage_error.json', 'logs/uc-usage.log'];

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

try {
  if (process.env.SPECBOX_UC_USAGE === 'off') process.exit(0);
  const { event, toolInput, payload } = readHookInput();
  const { boardId, backendType } = getProjectConfig();
  if (backendType !== 'native' || !boardId) process.exit(0);

  const marcador = fileAge('.quality/active_uc.json') < 86400 ? readJsonFile('.quality/active_uc.json') : null;
  const uc = marcador?.uc_id;
  // Antes de complete_uc, solo si cierra la UC activa.
  if (!uc || (event === 'PreToolUse' && toolInput.uc_id && toolInput.uc_id !== uc)) process.exit(0);
  const sesion = typeof payload.session_id === 'string' ? payload.session_id : '';
  const t = transcriptDe(payload);
  if (!sesion || !t || !existsSync(t.ruta)) process.exit(0);

  mkdir(DIR);
  asegurarIgnorados();
  const cursorRuta = rutaCursor(DIR, t.ruta);
  if (fileAge(`${cursorRuta}.pending`) * 1000 < EN_CURSO_MS) process.exit(0);
  const cursor = readJsonFile(cursorRuta) || {};
  const previo = cursor.ruta === t.ruta ? cursor : {};
  const { lineas, offset } = leerDesde(t.ruta, previo.offset ?? 0);
  const uso = sumarUso(lineas, previo.ids || [], { principal: t.principal, desde: marcador.started_at || null });
  const nuevo = { ruta: t.ruta, offset, ids: [...(previo.ids || []), ...uso.ids].slice(-MAX_IDS) };

  if (uso.messages === 0) {
    // Nada nuevo, o un formato que no se reconoce: se avanza sin enviar.
    writeFileSync(cursorRuta, JSON.stringify(nuevo));
    process.exit(0);
  }
  const datos = informe({ proyecto: boardId, uc, sesion, agente: t.agente, uso });
  if (process.env.SPECBOX_UC_USAGE_DRY_RUN) {
    appendFileSync(process.env.SPECBOX_UC_USAGE_DRY_RUN, `${JSON.stringify(datos)}\n`);
    writeFileSync(cursorRuta, JSON.stringify(nuevo));
  } else {
    writeFileSync(`${cursorRuta}.pending`, String(Date.now()));
    const enviar = join(dirname(fileURLToPath(import.meta.url)), 'lib', 'uc-usage-send.mjs');
    const hijo = spawn(
      process.execPath,
      [enviar, process.cwd(), JSON.stringify(datos), cursorRuta, JSON.stringify(nuevo)],
      { detached: true, stdio: 'ignore' },
    );
    hijo.unref();
  }
} catch {
  // El coste nunca molesta a la sesión.
}
process.exit(0);
