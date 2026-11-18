/**
 * lib/enforcement-events.mjs — los bloqueos de las medidas que aplican los hooks quedan en el tablero (UC-12213).
 *
 * native: `record_enforcement_event` con la identidad del dispositivo (2,5 s); FreeForm: una línea en
 * doc/tracking/enforcement_events.jsonl. Un `passed` tras un `blocked` de la misma medida y UC cuenta
 * como corregido. Nunca lanza.
 */

import { appendFileSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, isAbsolute, join } from 'node:path';
import { cabecerasDelDispositivo, URL_POR_DEFECTO } from './heartbeat-send.mjs';
import { llamarTool } from './mcp-client.mjs';

const STATE = join('.quality', 'enforcement_blocked.json');

function readState(root) {
  try {
    return JSON.parse(readFileSync(join(root, STATE), 'utf-8')) || {};
  } catch {
    return {};
  }
}

function writeState(root, state) {
  try {
    mkdirSync(dirname(join(root, STATE)), { recursive: true });
    writeFileSync(join(root, STATE), JSON.stringify(state));
  } catch { /* sin estado, la corrección no se registra */ }
}

/** Registra `blocked` o `passed` de `measure` en `ucId`. `config` = getProjectConfig(). */
export async function recordEnforcementEvent({ root = process.cwd(), config, measure, ucId, outcome, by, env = process.env }) {
  if (!ucId || !config) return false;
  const state = readState(root);
  if (outcome === 'blocked') state[measure] = ucId;
  else delete state[measure];
  writeState(root, state);
  const at = new Date().toISOString();
  if (config.backendType === 'freeform') {
    try {
      const dir = config.freeformRoot && isAbsolute(config.freeformRoot) ? config.freeformRoot : join(root, 'doc', 'tracking');
      mkdirSync(dir, { recursive: true });
      appendFileSync(join(dir, 'enforcement_events.jsonl'), `${JSON.stringify({ measure, uc_id: ucId, outcome, at, by })}\n`);
      return true;
    } catch {
      return false;
    }
  }
  if (config.backendType !== 'native' || !config.boardId || env.SPECBOX_ENFORCEMENT_POLICY === 'off') return false;
  try {
    const url = env.SPECBOX_MCP_URL || URL_POR_DEFECTO;
    const cabeceras = await cabecerasDelDispositivo({ ...env, CLAUDE_CODE_MCP_SERVER_URL: url });
    if (!cabeceras.Authorization) return false;
    const r = await llamarTool({
      url,
      cabeceras,
      nombre: 'record_enforcement_event',
      args: { measure, uc_id: ucId, outcome, board_id: config.boardId },
      topeMs: 2500,
    });
    return !!r?.success;
  } catch {
    return false;
  }
}

/** Si la última vez `measure` bloqueó `ucId`, ahora pasa: se registra la corrección. */
export async function recordCorrectionIfBlocked(args) {
  const state = readState(args.root || process.cwd());
  if (state[args.measure] && state[args.measure] === args.ucId) {
    return recordEnforcementEvent({ ...args, outcome: 'passed' });
  }
  return false;
}
