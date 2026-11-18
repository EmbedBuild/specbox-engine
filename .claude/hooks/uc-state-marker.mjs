#!/usr/bin/env node
/**
 * uc-state-marker.mjs — PostToolUse de las tools de SpecBox: el estado de la UC queda en el proyecto (UC-12216).
 *
 * Con el MCP remoto, `start_uc` no puede escribir .quality/active_uc.json en el disco del proyecto:
 * lo devuelve como `active_uc_marker` y este hook lo escribe. `complete_uc` y `release_uc` lo borran
 * si es de esa UC. Con el MCP local el servidor ya lo escribe; repetirlo deja el mismo fichero.
 *
 * UC-12206: también deja lo que mira uc-lifecycle-guard al hacer push: ac_marked.json tras
 * mark_ac_batch (criterios cumplidos y no cumplidos) y uc_moved_to_review.json tras move_uc a
 * revisión; el marcador guarda los criterios de la UC para saber cuáles faltan.
 *
 * Nunca bloquea ni escribe al agente: si no puede, se calla.
 */

import { execFileSync } from 'node:child_process';
import { parseToolName } from './lib/freeform-fragment.mjs';
import { acIdsFrom, clearMarker, isError, markerFrom, recordMarkedAcs, recordMove, writeMarker } from './lib/uc-state.mjs';
import { readHookInput } from './lib/utils.mjs';

const { event, toolName, toolInput, cwd, payload } = readHookInput();
const parsed = parseToolName(toolName);
if (event !== 'PostToolUse' || !parsed) process.exit(0);

const root = (() => {
  try {
    return (
      execFileSync('git', ['-C', cwd, 'rev-parse', '--show-toplevel'], {
        encoding: 'utf-8',
        stdio: ['ignore', 'pipe', 'ignore'],
      }).trim() || cwd
    );
  } catch {
    return cwd;
  }
})();

const response = payload.tool_response;
try {
  if (parsed.tool === 'start_uc') {
    const marker = markerFrom(response);
    if (marker) {
      const acIds = acIdsFrom(response);
      writeMarker(root, acIds.length ? { ...marker, ac_ids: acIds } : marker);
      recordMove(root, marker.uc_id, 'in_progress'); // la UC vuelve a estar en curso
    }
  } else if (parsed.tool === 'mark_ac_batch') {
    if (!isError(response) && toolInput.uc_id) recordMarkedAcs(root, toolInput.uc_id, response);
  } else if (parsed.tool === 'move_uc') {
    if (!isError(response) && toolInput.uc_id) recordMove(root, toolInput.uc_id, toolInput.target);
  } else if (parsed.tool === 'complete_uc' || parsed.tool === 'release_uc') {
    if (!isError(response)) clearMarker(root, toolInput.uc_id);
  }
} catch {
  // el marcador es una ayuda para los hooks: nunca la razón de que falle una tool
}
process.exit(0);
