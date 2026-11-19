#!/usr/bin/env node
/**
 * contract-first-guard.mjs — PreToolUse de Write/Edit: el contrato antes de las pruebas (UC-12801).
 *
 * La medida `contract_first` de EP-20. Antes de escribir en una carpeta de pruebas de aceptación
 * (`tests/acceptance/`, `test/acceptance/`, `e2e/acceptance/`, `.maestro/`) con una UC activa,
 * comprueba que la UC tiene su contrato completo: `.quality/evidence/<feature>/acceptance/contract.json`
 * con pre, post y undefined para cada criterio del marcador (las mismas reglas que la tool
 * check_acceptance_contract, lib/contract-first.mjs). Si falta: en «warn» (por defecto) avisa y deja
 * escribir; en «block» detiene la escritura (exit 2) y dice qué falta y cómo seguir; el bloqueo y su
 * corrección van al tablero. Ignora las UC de /fix (marcadas sin PRD: su prueba va en la carpeta
 * normal); en «block», una UC anterior a la regla solo recibe la nota. Sin tablero, sin UC activa o
 * con la medida en «off», no hace nada. e2e-gate aplica la misma medida al hacer commit.
 */

import { execFileSync } from 'node:child_process';
import { existsSync, realpathSync } from 'node:fs';
import { basename, dirname, isAbsolute, join, relative, resolve } from 'node:path';
import { readHookInput, readJsonFile } from './lib/utils.mjs';
import { getProjectConfig } from './lib/config.mjs';
import { blockWith, noteWith } from './lib/output.mjs';
import { leerPolitica, modoDe } from './lib/enforcement-policy.mjs';
import { recordCorrectionIfBlocked, recordEnforcementEvent } from './lib/enforcement-events.mjs';
import { ACCEPTANCE_PATH, MEASURE, contractProblem, howToFollow, measuredUc } from './lib/contract-first.mjs';

const { toolInput, cwd } = readHookInput();
const target = String(toolInput.file_path || '');
if (!target) process.exit(0);

const root = (() => {
  try {
    return execFileSync('git', ['-C', cwd, 'rev-parse', '--show-toplevel'], {
      encoding: 'utf-8', stdio: ['ignore', 'pipe', 'ignore'], timeout: 5000,
    }).trim() || cwd;
  } catch {
    return cwd;
  }
})();
/** La ruta real (enlaces resueltos) de algo que puede no existir aún: /var y /private/var en macOS. */
function real(path) {
  let cur = path;
  const rest = [];
  while (!existsSync(cur)) {
    rest.unshift(basename(cur));
    const up = dirname(cur);
    if (up === cur) return path;
    cur = up;
  }
  try {
    return join(realpathSync(cur), ...rest);
  } catch {
    return path;
  }
}
const rel = relative(real(root), real(isAbsolute(target) ? target : resolve(cwd, target))).split('\\').join('/');
if (rel.startsWith('..') || !ACCEPTANCE_PATH.test(rel)) process.exit(0);

process.chdir(root);
const config = getProjectConfig();
if (!config.isSpecDriven) process.exit(0);
const marker = readJsonFile('.quality/active_uc.json');
if (!measuredUc(marker)) process.exit(0);

const politica = await leerPolitica({ root, backendType: config.backendType, boardId: config.boardId, trackingDir: config.freeformRoot });
const mode = modoDe(politica, MEASURE);
if (mode === 'off') process.exit(0);

const { reason, contractPath } = contractProblem({ root, marker });
if (!reason) {
  await recordCorrectionIfBlocked({ root, config, measure: MEASURE, ucId: marker.uc_id, by: 'contract-first-guard' });
  process.exit(0);
}

const how = howToFollow(marker, contractPath);
const predates = Array.isArray(marker.predates_rule) && marker.predates_rule.includes(MEASURE);
if (mode === 'block' && !predates) {
  await recordEnforcementEvent({ root, config, measure: MEASURE, ucId: marker.uc_id, outcome: 'blocked', by: 'contract-first-guard' });
  blockWith('CONTRACT FIRST: las pruebas de aceptación van después del contrato', [
    `SpecBox detuvo la escritura de ${rel} por la medida ${MEASURE}. Motivo: ${reason}`,
    ...how.map((h) => `Cómo seguir: ${h}`),
  ]);
}
noteWith('PreToolUse', 'CONTRACT FIRST: las pruebas de aceptación van después del contrato (aviso)', [
  predates
    ? `Medida ${MEASURE} en «block», pero ${marker.uc_id} es anterior a la regla: la escritura sigue. Motivo: ${reason}`
    : `Medida ${MEASURE} en «warn»: la escritura sigue. Motivo: ${reason}`,
  ...how,
]);
