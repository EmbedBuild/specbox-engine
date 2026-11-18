#!/usr/bin/env node
/**
 * prd-sync-guard.mjs — PreToolUse de `gh pr merge`: el PRD cambia en la misma PR que el código (UC-12211).
 *
 * La medida `spec_in_pr` de EP-20. Antes de fusionar la PR de la UC activa comprueba que:
 *   - la PR toca el PRD de su historia (lib/prd-locate.mjs, también en el orquestador si el
 *     proyecto es satélite), o
 *   - su descripción enlaza una PR del orquestador que lo toca, o
 *   - la UC está marcada «sin PRD» con un motivo (update_uc no_prd_reason; va en el marcador).
 * Si no se cumple: en «warn» (por defecto) avisa y deja fusionar; en «block» detiene la fusión y dice
 * el PRD esperado y cómo seguir. Una UC anterior a la regla no se detiene. El modo sale de la
 * política del tablero (lib/enforcement-policy.mjs). Sin `gh` o sin respuesta, no detiene nada.
 */

import { execFileSync } from 'node:child_process';
import { isAbsolute, join, relative, resolve } from 'node:path';
import { readHookInput, readJsonFile } from './lib/utils.mjs';
import { getProjectConfig } from './lib/config.mjs';
import { blockWith, noteWith } from './lib/output.mjs';
import { leerPolitica, modoDe } from './lib/enforcement-policy.mjs';
import { recordCorrectionIfBlocked, recordEnforcementEvent } from './lib/enforcement-events.mjs';
import { locatePrd } from './lib/prd-locate.mjs';

const MEASURE = 'spec_in_pr';
const { toolInput, cwd } = readHookInput();
const command = String(toolInput.command || '');
const merge = /\bgh\s+pr\s+merge\b(.*)$/m.exec(command);
if (!merge) process.exit(0);

const run = (cmd, args, dir) => {
  try {
    return execFileSync(cmd, args, { cwd: dir, encoding: 'utf-8', stdio: ['ignore', 'pipe', 'ignore'], timeout: 8000 }).trim();
  } catch {
    return null;
  }
};

const root = run('git', ['-C', cwd, 'rev-parse', '--show-toplevel'], cwd) || cwd;
process.chdir(root);
const config = getProjectConfig();
if (!config.isSpecDriven) process.exit(0);
const marker = readJsonFile('.quality/active_uc.json');
if (!marker?.uc_id) process.exit(0);
if (Array.isArray(marker.predates_rule) && marker.predates_rule.includes(MEASURE)) process.exit(0);
if (typeof marker.no_prd_reason === 'string' && marker.no_prd_reason.trim()) process.exit(0);

const politica = await leerPolitica({ root, backendType: config.backendType, boardId: config.boardId, trackingDir: config.freeformRoot });
const mode = modoDe(politica, MEASURE);
if (mode === 'off') process.exit(0);

// El PRD esperado: en el orquestador si el proyecto es satélite.
const settings = readJsonFile('.claude/settings.local.json') || {};
const mr = settings.multirepo || readJsonFile('.claude/project-config.json')?.multirepo;
const satellite = mr?.enabled && mr?.role === 'satellite' && mr?.orchestrator;
const canonRoot = satellite ? (isAbsolute(mr.orchestrator) ? mr.orchestrator : resolve(root, mr.orchestrator)) : root;
const prd = locatePrd({ root: canonRoot, feature: marker.feature || '', usId: marker.us_id || '' });

// La PR que se va a fusionar: el argumento de `gh pr merge` (número, URL o rama) y su -R.
const tokens = merge[1].trim().split(/\s+/).filter(Boolean);
let selector = '';
let repoFlag = [];
for (let i = 0; i < tokens.length; i++) {
  if (tokens[i] === '-R' || tokens[i] === '--repo') {
    repoFlag = ['-R', tokens[i + 1] || ''];
    i++;
  } else if (!tokens[i].startsWith('-') && !selector && !/[;&|]/.test(tokens[i])) {
    selector = tokens[i];
  } else if (/[;&|]/.test(tokens[i])) {
    break;
  }
}
const view = (args) => {
  const out = run('gh', ['pr', 'view', ...args, '--json', 'files,body'], root);
  try {
    return out ? JSON.parse(out) : null;
  } catch {
    return null;
  }
};
const pr = view([...(selector ? [selector] : []), ...repoFlag]);
if (!pr) process.exit(0); // sin gh o sin respuesta: no se detiene nada

const touches = (files, rel) => Array.isArray(files) && files.some((f) => (f?.path || f) === rel);
let ok = false;
if (prd) {
  const relToRepo = satellite ? null : prd;
  if (relToRepo && touches(pr.files, relToRepo)) ok = true;
  // Una PR del orquestador enlazada desde la descripción que toca el PRD.
  if (!ok && satellite) {
    const remote = run('git', ['-C', canonRoot, 'remote', 'get-url', 'origin'], canonRoot) || '';
    const slug = /github\.com[:/]([^/]+\/[^/.]+?)(?:\.git)?$/.exec(remote)?.[1];
    const links = slug ? [...String(pr.body || '').matchAll(new RegExp(`github\\.com/${slug.replace('/', '\\/')}/pull/(\\d+)`, 'g'))] : [];
    for (const [, number] of links) {
      const other = view([number, '-R', slug]);
      if (other && touches(other.files, prd)) {
        ok = true;
        break;
      }
    }
  }
}

if (ok) {
  await recordCorrectionIfBlocked({ root, config, measure: MEASURE, ucId: marker.uc_id, by: 'prd-sync-guard' });
  process.exit(0);
}

const where = prd
  ? `${satellite ? `${relative(root, canonRoot) || '.'}/` : ''}${prd}`
  : `un PRD de ${marker.us_id || 'la historia'} (doc/prd/<slug>/prd.md, doc/prd/<feature>.md o doc/prds/)`;
const reason = prd
  ? `la PR de ${marker.uc_id} no cambia el PRD de su historia (${where})${satellite ? ' ni enlaza una PR del orquestador que lo cambie' : ''}.`
  : `no se encontró ${where}.`;
const how = [
  satellite
    ? `Actualiza ${prd || 'el PRD'} en una PR del orquestador y enlázala en la descripción de esta PR.`
    : `Actualiza ${prd || 'el PRD de la historia'} en esta misma PR (por ejemplo, su estado de implementación).`,
  `Si la UC no tiene PRD, márcala: update_uc(board_id, "${marker.uc_id}", no_prd_reason="por qué").`,
];

if (mode === 'block') {
  await recordEnforcementEvent({ root, config, measure: MEASURE, ucId: marker.uc_id, outcome: 'blocked', by: 'prd-sync-guard' });
  blockWith('SPEC GUARD: el PRD no cambia en la misma PR', [
    `SpecBox detuvo la fusión por la medida ${MEASURE}. Motivo: ${reason}`,
    ...how.map((h) => `Cómo seguir: ${h}`),
  ]);
}
noteWith('PreToolUse', 'SPEC GUARD: el PRD no cambia en la misma PR (aviso)', [
  `Medida ${MEASURE} en «warn»: la fusión sigue. Motivo: ${reason}`,
  ...how,
]);
