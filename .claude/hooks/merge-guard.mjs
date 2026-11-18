#!/usr/bin/env node
/**
 * merge-guard.mjs — PreToolUse de `gh pr merge`: lo que se fusiona está demostrado (UC-12401).
 *
 * La medida `closing_evidence` de EP-20, antes de fusionar la PR de la UC activa: cada criterio de la
 * UC está hecho y tiene al menos un recibo que pasa (la misma regla que complete_uc, en
 * lib/closing-evidence.mjs). /implement marca los criterios y pasa la UC a revisión antes de fusionar,
 * así que una prueba de aceptación que falla deja su criterio sin recibo que pase y la fusión no sigue.
 *
 * - En «warn» (por defecto) avisa con cada criterio y su motivo, y deja fusionar.
 * - En «block» detiene la fusión y dice cómo seguir.
 * - Una UC anterior a la regla (en el marcador, o empezada antes de que la medida bloqueara) no se
 *   detiene: avisa.
 * - Sin datos (sin UC activa, sin red, un backend sin recibos) no detiene nada.
 *
 * Los criterios salen de doc/tracking/items.json en FreeForm y de `get_uc` con la identidad del
 * dispositivo en native. US-124 añade aquí `independent_review` (UC-12402).
 */

import { execFileSync } from 'node:child_process';
import { isAbsolute, join } from 'node:path';
import { readHookInput, readJsonFile } from './lib/utils.mjs';
import { getProjectConfig } from './lib/config.mjs';
import { blockWith, noteWith } from './lib/output.mjs';
import { leerPolitica, modoDe } from './lib/enforcement-policy.mjs';
import { recordCorrectionIfBlocked, recordEnforcementEvent } from './lib/enforcement-events.mjs';
import { closingEvidence, closingReason, freeformCriteria, startedBeforeBlock } from './lib/closing-evidence.mjs';
import { cabecerasDelDispositivo, URL_POR_DEFECTO } from './lib/heartbeat-send.mjs';
import { llamarTool } from './lib/mcp-client.mjs';

const MEASURE = 'closing_evidence';
const { toolInput, cwd } = readHookInput();
if (!/\bgh\s+pr\s+merge\b/m.test(String(toolInput.command || ''))) process.exit(0);

let root = cwd;
try {
  root = execFileSync('git', ['-C', cwd, 'rev-parse', '--show-toplevel'], {
    encoding: 'utf-8',
    stdio: ['ignore', 'pipe', 'ignore'],
    timeout: 5000,
  }).trim() || cwd;
} catch {
  // fuera de un repositorio: se usa la carpeta actual
}
process.chdir(root);
const config = getProjectConfig();
if (!config.isSpecDriven) process.exit(0);
const marker = readJsonFile('.quality/active_uc.json');
if (!marker?.uc_id) process.exit(0);

const politica = await leerPolitica({
  root,
  backendType: config.backendType,
  boardId: config.boardId,
  trackingDir: config.freeformRoot,
});
const mode = modoDe(politica, MEASURE);
if (mode === 'off') process.exit(0);

/** Los criterios de la UC activa con sus recibos, o null si no se pueden leer. */
async function criterios() {
  if (config.backendType === 'freeform') {
    const dir = config.freeformRoot
      ? (isAbsolute(config.freeformRoot) ? config.freeformRoot : join(root, config.freeformRoot))
      : join(root, 'doc', 'tracking');
    return freeformCriteria(readJsonFile(join(dir, 'items.json')), marker.uc_id);
  }
  if (config.backendType !== 'native' || !config.boardId || process.env.SPECBOX_ENFORCEMENT_POLICY === 'off') return null;
  try {
    const url = process.env.SPECBOX_MCP_URL || URL_POR_DEFECTO;
    const cabeceras = await cabecerasDelDispositivo({ ...process.env, CLAUDE_CODE_MCP_SERVER_URL: url });
    if (!cabeceras.Authorization) return null;
    const uc = await llamarTool({
      url,
      cabeceras,
      nombre: 'get_uc',
      args: { board_id: config.boardId, uc_id: marker.uc_id },
      topeMs: 4000,
    });
    if (!Array.isArray(uc?.acceptance_criteria)) return null;
    return uc.acceptance_criteria.map((ac) => ({ ac_id: ac.id, done: !!ac.done, evidence: Array.isArray(ac.evidence) ? ac.evidence : [] }));
  } catch {
    return null; // sin red o con el tablero caído: no se detiene nada
  }
}

const acs = await criterios();
if (acs === null) process.exit(0);
const result = closingEvidence(acs);
if (result.ok) {
  await recordCorrectionIfBlocked({ root, config, measure: MEASURE, ucId: marker.uc_id, by: 'merge-guard' });
  process.exit(0);
}

const reason = `${marker.uc_id}: ${closingReason(result)}`;
const how = [
  'Marca cada criterio con mark_ac (o mark_ac_batch) y un recibo que pase: una prueba, una captura, un enlace o una nota escrita si se comprobó a mano.',
  'Si una prueba de aceptación falla, corrige el código, vuelve a pasarla y márcala antes de fusionar.',
];
const predates =
  (Array.isArray(marker.predates_rule) && marker.predates_rule.includes(MEASURE)) ||
  startedBeforeBlock(marker.started_at, politica.bloqueaDesde?.[MEASURE]);

if (mode === 'block' && !predates) {
  await recordEnforcementEvent({ root, config, measure: MEASURE, ucId: marker.uc_id, outcome: 'blocked', by: 'merge-guard' });
  blockWith('SPEC GUARD: la UC tiene criterios sin demostrar', [
    `SpecBox detuvo la fusión por la medida ${MEASURE}. Motivo: ${reason}`,
    ...how.map((h) => `Cómo seguir: ${h}`),
  ]);
}
noteWith('PreToolUse', 'SPEC GUARD: la UC tiene criterios sin demostrar (aviso)', [
  predates
    ? `La UC es anterior a la regla ${MEASURE}: la fusión sigue. Motivo: ${reason}`
    : `Medida ${MEASURE} en «warn»: la fusión sigue. Motivo: ${reason}`,
  ...how,
]);
