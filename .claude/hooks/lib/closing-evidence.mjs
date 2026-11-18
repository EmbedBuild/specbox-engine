/**
 * lib/closing-evidence.mjs — qué criterios de una UC no están demostrados (UC-12401).
 *
 * La misma regla que `closing_evidence_result` de server/coordination/enforcement.py (una prueba
 * compara las dos): un criterio está demostrado si está hecho y tiene al menos un recibo con
 * `passed: true`. Cuentan todos los criterios; una UC sin criterios no tiene nada demostrado. Un
 * criterio cuya evidencia no se conoce (`evidence: null`) cuenta solo por «hecho».
 */

export const CLOSING_REASONS = {
  not_done: 'sin marcar',
  no_evidence: 'sin evidencia',
  failing_evidence: 'con evidencia que falla',
};

/** `{ total, missing: [{ ac_id, reason }], ok }` de los criterios `[{ ac_id, done, evidence }]`. */
export function closingEvidence(acs) {
  const list = Array.isArray(acs) ? acs : [];
  const missing = [];
  if (list.length === 0) missing.push({ ac_id: null, reason: 'no_criteria' });
  for (const ac of list) {
    const acId = String(ac?.ac_id ?? '?');
    const evidence = ac?.evidence;
    if (!ac?.done) missing.push({ ac_id: acId, reason: 'not_done' });
    else if (evidence === null || evidence === undefined) continue;
    else if (!Array.isArray(evidence) || evidence.length === 0) missing.push({ ac_id: acId, reason: 'no_evidence' });
    else if (!evidence.some((e) => e && typeof e === 'object' && e.passed === true)) {
      missing.push({ ac_id: acId, reason: 'failing_evidence' });
    }
  }
  return { total: list.length, missing, ok: missing.length === 0 };
}

/** El motivo en una frase, como `closing_evidence_reason` del servidor; null si está todo demostrado. */
export function closingReason(result) {
  if (result.ok) return null;
  if (result.missing.some((m) => m.reason === 'no_criteria')) return 'La UC no tiene criterios: no hay nada demostrado.';
  const detail = result.missing.map((m) => `${m.ac_id} (${CLOSING_REASONS[m.reason] ?? m.reason})`).join(', ');
  return `${result.missing.length} de ${result.total} criterios sin demostrar: ${detail}.`;
}

/** True si la UC empezó antes de que la medida pasara a «block» (UC-12401 AC-06). */
export function startedBeforeBlock(startedAt, blockSince) {
  const started = Date.parse(startedAt ?? '');
  const since = Date.parse(blockSince ?? '');
  return Number.isFinite(started) && Number.isFinite(since) && started < since;
}

/** Los criterios de una UC de items.json de FreeForm, con su evidencia (null si no consta). */
export function freeformCriteria(items, ucId) {
  const list = Array.isArray(items) ? items : [];
  const uc = list.find((i) => Array.isArray(i?.labels) && i.labels.includes('UC') && i?.meta?.uc_id === ucId);
  if (!uc) return null;
  return list
    .filter((i) => i?.parent_id === uc.id && Array.isArray(i?.labels) && i.labels.includes('AC'))
    .map((i) => {
      const meta = i.meta && typeof i.meta === 'object' ? i.meta : {};
      const known = Array.isArray(meta.evidence) || (meta.verdict && typeof meta.verdict === 'object');
      return {
        ac_id: meta.ac_id || (/^\[(AC-[^\]]+)\]/.exec(String(i.name || ''))?.[1] ?? '?'),
        done: i.state === 'done',
        evidence: known ? (Array.isArray(meta.evidence) ? meta.evidence : []) : null,
      };
    });
}
