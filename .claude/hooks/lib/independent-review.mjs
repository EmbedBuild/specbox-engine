/**
 * lib/independent-review.mjs — si la revisión deja fusionar una UC (UC-12402).
 *
 * La misma regla que `independent_review_result` de server/review.py (una prueba compara las dos):
 * - una UC devuelta después de su último visto bueno no se fusiona;
 * - la aceptación de una persona (el panel) basta en cualquier nivel de autopilot;
 * - en «agresivo», y en FreeForm (sin panel), basta el último veredicto «aceptada» de un contexto
 *   independiente del que implementó;
 * - fuera de «agresivo», en native, hace falta la persona.
 */

export const AGGRESSIVE = 'agresivo';
const VERDICTS = new Set(['accepted', 'returned']);

function latest(verdicts) {
  const valid = (Array.isArray(verdicts) ? verdicts : []).filter((v) => v && VERDICTS.has(v.verdict));
  if (!valid.length) return null;
  return valid.reduce((a, b) => (String(b.at ?? '') >= String(a.at ?? '') ? b : a));
}

/** `{ ok, reason_code?, reason? }` con los mismos códigos y textos que el servidor. */
export function independentReview({ humanAcceptance = null, verdicts = [], level = '', backendType = '' } = {}) {
  const last = latest(verdicts);
  if (last && last.verdict === 'returned') {
    return { ok: false, reason_code: 'returned', reason: `La UC fue devuelta: ${last.reason || 'sin motivo'}.` };
  }
  if (humanAcceptance) return { ok: true };
  const agentOk = !!last && last.verdict === 'accepted' && !!last.independent;
  if ((level === AGGRESSIVE || backendType === 'freeform') && agentOk) return { ok: true };
  if (level !== AGGRESSIVE && backendType !== 'freeform') {
    return {
      ok: false,
      reason_code: 'no_person_acceptance',
      reason: 'Falta que una persona acepte la UC en el panel (fuera del autopilot «agresivo»).',
    };
  }
  return {
    ok: false,
    reason_code: 'no_independent_verdict',
    reason: 'Falta el veredicto «aceptada» de un evaluador en un contexto distinto del que implementó.',
  };
}

export const INDEPENDENT_HOW_TO =
  'En autopilot «agresivo», lanza un evaluador aislado (subagente AG-09b) que revise los criterios y sus ' +
  'recibos y registre su veredicto con record_review_verdict. En los demás niveles, una persona acepta la ' +
  'UC en revisión desde el panel.';
