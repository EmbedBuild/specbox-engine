/**
 * lib/contract-first.mjs — la medida `contract_first` (US-128 · UC-12801) en los hooks.
 *
 * La usan contract-first-guard (antes de escribir en una carpeta de aceptación) y e2e-gate (al hacer
 * commit de pruebas o de evidencia de aceptación). Lee el contrato de la UC activa y dice qué falta,
 * con las reglas de lib/acceptance-contract.mjs (las de la tool check_acceptance_contract).
 */

import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { contractReport } from './acceptance-contract.mjs';

export const MEASURE = 'contract_first';
/** Las carpetas de las pruebas de aceptación de cada stack (la convención de CLAUDE.md). */
export const ACCEPTANCE_PATH = /(^|\/)(tests?\/acceptance|e2e\/acceptance|\.maestro)\//;

/** ¿La medida mira esta UC? No las de /fix (marcadas sin PRD: su prueba va en la carpeta normal). */
export function measuredUc(marker) {
  if (!marker?.uc_id) return false;
  return !(typeof marker.no_prd_reason === 'string' && marker.no_prd_reason.trim());
}

/** La ruta donde se espera el contrato de la UC. */
export function expectedContractPath(marker) {
  return join('.quality', 'evidence', String(marker.feature || marker.uc_id), 'acceptance', 'contract.json');
}

/** El contrato de la UC: el de su feature o, si no, el que diga ser de esa UC. Rutas relativas a `root`. */
export function findContract(root, marker) {
  const base = join('.quality', 'evidence');
  const own = expectedContractPath(marker);
  if (marker.feature && existsSync(join(root, own))) return own;
  let dirs = [];
  try {
    dirs = readdirSync(join(root, base), { withFileTypes: true }).filter((d) => d.isDirectory()).map((d) => d.name);
  } catch {
    return null;
  }
  for (const dir of dirs) {
    const candidate = join(base, dir, 'acceptance', 'contract.json');
    try {
      const data = JSON.parse(readFileSync(join(root, candidate), 'utf-8'));
      if (String(data?.uc_id || '').trim().toUpperCase() === String(marker.uc_id).toUpperCase()) return candidate;
    } catch { /* sin contrato aquí */ }
  }
  return null;
}

/**
 * Qué le falta al contrato de la UC activa, en una frase, o '' si está completo.
 * Con `resultsPaths`, también las pruebas que no citan su pre y su post (AC-02).
 */
export function contractProblem({ root, marker, resultsPaths = [] }) {
  const contractPath = findContract(root, marker);
  if (!contractPath) return { reason: `${marker.uc_id} no tiene contrato (${expectedContractPath(marker)}).`, contractPath: null };
  const contractContent = readFileSync(join(root, contractPath), 'utf-8');
  const criteria = Array.isArray(marker.ac_ids) ? marker.ac_ids : [];
  const report = contractReport({ contractContent, criteriaIds: criteria, ucId: marker.uc_id });
  if (!report.success) return { reason: `el contrato de ${marker.uc_id} no se puede leer: ${report.error}`, contractPath };
  const parts = [];
  if (report.missing.length) parts.push(`criterios sin contrato: ${report.missing.join(', ')}`);
  if (report.incomplete.length) {
    parts.push(`incompletos: ${report.incomplete.map((i) => `${i.ac_id} (sin ${i.missing.join(' ni ')})`).join('; ')}`);
  }
  if (report.invalid.length) parts.push(`${report.invalid.length} entradas que no valen`);
  if (report.uc_mismatch) parts.push(`es de ${report.uc_mismatch.found}, no de ${report.uc_mismatch.expected}`);
  if (parts.length) return { reason: `el contrato de ${marker.uc_id} (${contractPath}) no está completo: ${parts.join('; ')}.`, contractPath };
  for (const resultsPath of resultsPaths) {
    let resultsContent;
    try {
      resultsContent = readFileSync(join(root, resultsPath), 'utf-8');
    } catch {
      continue;
    }
    const withResults = contractReport({ contractContent, criteriaIds: criteria, ucId: marker.uc_id, resultsContent });
    const c = withResults.citations;
    if (!withResults.success || !c) continue;
    const bad = [
      ...c.uncited.map((u) => `«${u.test}» (${u.ac_id}) no cita su ${u.missing.join(' ni su ')}`),
      ...c.unknown.map((u) => `«${u.test}» cita ${u.condition}: ${u.problem}`),
    ];
    if (bad.length) {
      return { reason: `las pruebas de ${resultsPath} no citan el contrato: ${bad.slice(0, 5).join('; ')}${bad.length > 5 ? '…' : ''}.`, contractPath };
    }
  }
  return { reason: '', contractPath };
}

/** Cómo seguir, para el aviso o el bloqueo. */
export function howToFollow(marker, contractPath) {
  return [
    `Escribe ${contractPath || expectedContractPath(marker)} con pre, post y undefined para cada criterio (doc/specs/results-json-spec.md, «Contrato de cada criterio»).`,
    `Compruébalo con check_acceptance_contract(contract_content, uc_criteria, uc_id="${marker.uc_id}") hasta ok: true y genera las pruebas desde él, citando @pre:AC-NN.preN @post:AC-NN.postN (Paso 7.5.0 de /implement).`,
  ];
}
