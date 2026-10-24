/**
 * lib/heartbeat.mjs — el latido de la sesión (US-99 · UC-9901), sin efectos.
 *
 * Calcula qué decir al board (UC, fase, si espera) a partir del evento del hook y de lo que hay
 * en el repo, y decide si toca enviarlo: al empezar y al cerrar siempre; si cambió la UC, la fase
 * o la espera, en el acto; si no, como mucho cada dos minutos (AC-01). Solo campos enumerados o de
 * forma fija: nunca texto de la conversación ni de las specs.
 */

/** Cada cuánto, como mucho, se repite un latido sin cambios. */
export const INTERVALO_MS = 2 * 60 * 1000;

/** Las fases que acepta el board (CHECK de la migración 0031). */
export const FASES = ['idle', 'discovery', 'prd', 'plan', 'design', 'implement', 'tests', 'review', 'release'];

const UC = /^UC-[0-9]{1,6}[a-z]?$/;
const SESION = /^[A-Za-z0-9-]{8,64}$/;

/** La UC activa: la del marcador si es reciente, si no la de la rama `feature/UC-1234-…`. */
export function ucActiva({ marcador, rama } = {}) {
  const delMarcador = (marcador?.uc_id || '').trim();
  if (UC.test(delMarcador)) return delMarcador;
  const m = /(?:^|\/)uc-([0-9]{1,6}[a-z]?)(?:[-_/]|$)/i.exec(rama || '');
  return m ? `UC-${m[1].replace(/[a-z]$/i, (letra) => letra.toLowerCase())}` : null;
}

/** Ids de fase de pipeline_state.json (/implement) → fase del board. */
const DE_PIPELINE = {
  init: 'plan',
  db_infra: 'implement',
  stitch_designs: 'design',
  design_to_code: 'design',
  feature_code: 'implement',
  appscript: 'implement',
  n8n: 'implement',
  integration: 'implement',
  tests: 'tests',
  qa: 'tests',
  acceptance: 'tests',
  pr: 'review',
  merge: 'review',
};

/** Palabras del nombre de un checkpoint → fase (el primero que encaje). */
const PALABRAS = [
  [/discovery/i, 'discovery'],
  [/\bprd\b/i, 'prd'],
  [/\bplan\b/i, 'plan'],
  [/dise[ñn]o|design|lienzo|canvas/i, 'design'],
  [/\bpruebas?\b|\btests?\b|\bqa\b|acceptance|aceptaci/i, 'tests'],
  [/revisi[oó]n|review|\bpr\b|merge|fusi/i, 'review'],
  [/release|publica/i, 'release'],
];

/**
 * La fase: la de pipeline_state.json si la hay; si no, la del último checkpoint reciente (menos de
 * dos horas); si no, `implement` con UC activa e `idle` sin ella.
 */
export function faseActual({ pipeline, checkpoint, checkpointEdadS, uc } = {}) {
  const deP = DE_PIPELINE[pipeline?.current_phase];
  if (deP) return deP;
  if (checkpoint && (checkpointEdadS ?? Infinity) < 2 * 3600) {
    const nombre = String(checkpoint.phase_name || '');
    for (const [re, fase] of PALABRAS) if (re.test(nombre)) return fase;
    return 'implement';
  }
  return uc ? 'implement' : 'idle';
}

/**
 * Qué espera la sesión según el evento: una notificación de permiso → `permission`; la de
 * inactividad («esperando tu respuesta») → `decision`; la persona escribe o una tool termina →
 * `none`; el resto conserva lo que había.
 */
export function esperaTras(evento, entrada = {}, anterior = 'none') {
  if (evento === 'Notification') {
    const tipo = String(entrada.notification_type || '');
    const texto = String(entrada.message || '');
    if (tipo === 'permission_prompt' || /permission|permiso/i.test(texto)) return 'permission';
    if (tipo === 'idle_prompt' || /waiting for your input|esperando/i.test(texto)) return 'decision';
    return anterior;
  }
  if (evento === 'UserPromptSubmit' || evento === 'PostToolUse') return 'none';
  if (evento === 'SessionStart' || evento === 'SessionEnd') return 'none';
  return anterior;
}

/** El latido que se enviaría, o null si no hay sesión o proyecto native que decir. */
export function latido({ evento, entrada = {}, proyecto, marcador, rama, pipeline, checkpoint, checkpointEdadS, anterior }) {
  const sesion = String(entrada.session_id || '');
  if (!SESION.test(sesion) || !proyecto) return null;
  const uc = ucActiva({ marcador, rama });
  return {
    project_id: proyecto,
    session_id: sesion,
    uc_id: uc,
    phase: faseActual({ pipeline, checkpoint, checkpointEdadS, uc }),
    waiting: esperaTras(evento, entrada, anterior?.session_id === sesion ? anterior.waiting : 'none'),
    ended: evento === 'SessionEnd',
  };
}

/** ¿Toca enviarlo? Al empezar y al cerrar, siempre; si cambió algo, ya; si no, cada dos minutos. */
export function tocaEnviar(nuevo, anterior, ahora) {
  if (!nuevo) return false;
  if (nuevo.ended) return true;
  if (!anterior || anterior.session_id !== nuevo.session_id) return true;
  for (const k of ['uc_id', 'phase', 'waiting']) if (anterior[k] !== nuevo[k]) return true;
  return ahora - (anterior.sent_at || 0) >= INTERVALO_MS;
}
