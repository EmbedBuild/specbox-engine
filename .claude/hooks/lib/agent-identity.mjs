/**
 * lib/agent-identity.mjs — el contexto de Claude Code que llama a una tool (US-124 · UC-12402).
 *
 * Claude Code da a cada hook `session_id` y, dentro de un subagente, `agent_id` y `agent_type`. Esos
 * valores los pone Claude Code, no el modelo: con ellos el tablero sabe quién implementó una UC
 * (`start_uc`), si quien la revisa es otro contexto (`record_review_verdict`) y si quien aprueba los
 * criterios es la sesión principal y no un subagente (`approve_criteria`, UC-12502). Los ponen en la
 * llamada el hook agent-identity o, en FreeForm con el MCP remoto, freeform-fragment (un solo hook
 * cambia cada llamada). Lo que mande el modelo en esos campos se sustituye.
 */

/** Las tools que reciben la identidad del contexto. */
export const IDENTITY_TOOLS = new Set(['start_uc', 'record_review_verdict', 'approve_criteria']);

const ID_RE = /^[A-Za-z0-9_.:@/-]{1,128}$/;

/** `{ client_session_id, client_agent_id?, client_agent_type? }` de la entrada del hook ({} si no hay). */
export function identityFields(payload) {
  const out = {};
  const pairs = [
    ['client_session_id', payload?.session_id],
    ['client_agent_id', payload?.agent_id],
    ['client_agent_type', payload?.agent_type],
  ];
  for (const [key, value] of pairs) {
    if (typeof value === 'string' && ID_RE.test(value.trim())) out[key] = value.trim();
  }
  return out;
}

/** La entrada de la tool con la identidad del contexto encima (sin los campos que mandó el modelo). */
export function withIdentity(toolInput, payload) {
  const { client_session_id: _s, client_agent_id: _a, client_agent_type: _t, ...rest } = toolInput || {};
  return { ...rest, ...identityFields(payload) };
}
