#!/usr/bin/env node
/**
 * merge-guard.mjs — PreToolUse de `gh pr merge`: lo que se fusiona está demostrado y revisado.
 *
 * Dos medidas de EP-20 sobre la UC activa, con los datos del tablero:
 *
 * - `closing_evidence` (UC-12401): cada criterio está hecho y tiene al menos un recibo que pasa (la
 *   regla de complete_uc, en lib/closing-evidence.mjs). /implement marca los criterios y pasa la UC a
 *   revisión antes de fusionar, así que una prueba de aceptación que falla no llega a fusionarse.
 * - `independent_review` (UC-12402): la UC tiene el visto bueno de alguien que no la implementó
 *   (lib/independent-review.mjs). Fuera del autopilot «agresivo» hace falta una persona (el panel); en
 *   «agresivo», o en FreeForm, basta un evaluador en un contexto independiente.
 *
 * En «warn» (por defecto) avisa con lo que falta y deja fusionar; en «block» detiene la fusión y dice
 * cómo seguir. Una UC anterior a la regla (en el marcador, o empezada antes de que la medida
 * bloqueara) no se detiene. Sin datos (sin UC activa, sin red) no detiene nada.
 *
 * Los datos salen de doc/tracking/items.json en FreeForm y de `get_uc` con la identidad del dispositivo
 * en native. El nivel de autopilot, de `specbox.autopilot.level` en .claude/settings.local.json.
 */

import { execFileSync } from 'node:child_process';
import { isAbsolute, join } from 'node:path';
import { readHookInput, readJsonFile } from './lib/utils.mjs';
import { getProjectConfig } from './lib/config.mjs';
import { blockWith, noteWith } from './lib/output.mjs';
import { leerPolitica, modoDe } from './lib/enforcement-policy.mjs';
import { recordCorrectionIfBlocked, recordEnforcementEvent } from './lib/enforcement-events.mjs';
import { closingEvidence, closingReason, freeformCriteria, startedBeforeBlock } from './lib/closing-evidence.mjs';
import { INDEPENDENT_HOW_TO, independentReview } from './lib/independent-review.mjs';
import { cabecerasDelDispositivo, URL_POR_DEFECTO } from './lib/heartbeat-send.mjs';
import { llamarTool } from './lib/mcp-client.mjs';

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
const MEASURES = ['closing_evidence', 'independent_review'].filter((m) => modoDe(politica, m) !== 'off');
if (!MEASURES.length) process.exit(0);
const level = readJsonFile('.claude/settings.local.json')?.specbox?.autopilot?.level || '';

/** `{ acs, humanAcceptance, verdicts }` de la UC activa, o null si no se puede leer. */
async function datosDeLaUc() {
  if (config.backendType === 'freeform') {
    const dir = config.freeformRoot
      ? (isAbsolute(config.freeformRoot) ? config.freeformRoot : join(root, config.freeformRoot))
      : join(root, 'doc', 'tracking');
    const items = readJsonFile(join(dir, 'items.json'));
    const acs = freeformCriteria(items, marker.uc_id);
    if (acs === null) return null;
    const uc = items.find((i) => Array.isArray(i?.labels) && i.labels.includes('UC') && i?.meta?.uc_id === marker.uc_id);
    const verdicts = Array.isArray(uc?.meta?.review_verdicts) ? uc.meta.review_verdicts : [];
    return { acs, humanAcceptance: null, verdicts };
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
    return {
      acs: uc.acceptance_criteria.map((ac) => ({ ac_id: ac.id, done: !!ac.done, evidence: Array.isArray(ac.evidence) ? ac.evidence : [] })),
      humanAcceptance: uc.human_acceptance || null,
      verdicts: Array.isArray(uc.review_verdicts) ? uc.review_verdicts : [],
    };
  } catch {
    return null; // sin red o con el tablero caído: no se detiene nada
  }
}

const datos = await datosDeLaUc();
if (datos === null) process.exit(0);

const evaluar = {
  closing_evidence: () => {
    const r = closingEvidence(datos.acs);
    return r.ok
      ? null
      : {
          motivo: closingReason(r),
          como: [
            'Marca cada criterio con mark_ac (o mark_ac_batch) y un recibo que pase: una prueba, una captura, un enlace o una nota escrita si se comprobó a mano.',
            'Si una prueba de aceptación falla, corrige el código, vuelve a pasarla y márcala antes de fusionar.',
          ],
        };
  },
  independent_review: () => {
    const r = independentReview({
      humanAcceptance: datos.humanAcceptance,
      verdicts: datos.verdicts,
      level,
      backendType: config.backendType,
    });
    return r.ok ? null : { motivo: r.reason, como: [INDEPENDENT_HOW_TO] };
  },
};

const bloqueos = [];
const avisos = [];
for (const measure of MEASURES) {
  const fallo = evaluar[measure]();
  if (!fallo) {
    await recordCorrectionIfBlocked({ root, config, measure, ucId: marker.uc_id, by: 'merge-guard' });
    continue;
  }
  const predates =
    (Array.isArray(marker.predates_rule) && marker.predates_rule.includes(measure)) ||
    startedBeforeBlock(marker.started_at, politica.bloqueaDesde?.[measure]);
  const motivo = `${marker.uc_id}: ${fallo.motivo}`;
  if (modoDe(politica, measure) === 'block' && !predates) {
    await recordEnforcementEvent({ root, config, measure, ucId: marker.uc_id, outcome: 'blocked', by: 'merge-guard' });
    bloqueos.push(`SpecBox detuvo la fusión por la medida ${measure}. Motivo: ${motivo}`, ...fallo.como.map((c) => `Cómo seguir: ${c}`));
  } else {
    avisos.push(
      predates
        ? `La UC es anterior a la regla ${measure}: la fusión sigue. Motivo: ${motivo}`
        : `Medida ${measure} en «warn»: la fusión sigue. Motivo: ${motivo}`,
      ...fallo.como,
    );
  }
}

if (bloqueos.length) blockWith('SPEC GUARD: la UC no está lista para fusionarse', [...bloqueos, ...avisos]);
if (avisos.length) noteWith('PreToolUse', 'SPEC GUARD: la UC no está lista para fusionarse (aviso)', avisos);
