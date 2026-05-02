/**
 * lib/token-counter.mjs — zero-deps token estimator (v5.32.0).
 *
 * The chars/4 heuristic is a well-known approximation for Anthropic
 * tokenisation that holds within ~8% for typical mixed text+code.
 * We use it because:
 *   1. Counting is on the hot path (PreToolUse Task hook) — must be
 *      synchronous and fast.
 *   2. Calling Anthropic's count_tokens API would add latency and
 *      cost per Task spawn.
 *   3. The guard's purpose is to flag "this prompt is way too big",
 *      which doesn't need single-token precision.
 *
 * If telemetry shows the heuristic underestimates dangerously, we
 * can swap it for a tiktoken-style counter in a follow-up patch
 * without changing the call sites.
 */

const CHARS_PER_TOKEN = 4;

/**
 * Estimate tokens in a single string. Returns at least 1 for any
 * non-empty input.
 * @param {string} text
 * @returns {number}
 */
export function estimateTokens(text) {
  if (!text) return 0;
  return Math.max(1, Math.ceil(text.length / CHARS_PER_TOKEN));
}

/**
 * Estimate tokens for a structured prompt payload.
 *
 * Accepts the shape that PreToolUse(Task) hooks observe:
 *   { tool_input: { description, prompt, ... } }
 * Or, equivalently, raw fields: { prompt, description, system }.
 *
 * Files arrays are included if present (some Task harnesses pass
 * files explicitly), counted by their content.
 *
 * @param {object} payload
 * @returns {{ total: number, breakdown: Record<string, number> }}
 */
export function estimatePromptTokens(payload) {
  const breakdown = {};
  let total = 0;

  // PreToolUse harness shape: payload.tool_input.{description, prompt, ...}
  const fields = payload?.tool_input ?? payload ?? {};

  if (typeof fields.description === 'string') {
    const t = estimateTokens(fields.description);
    breakdown.description = t;
    total += t;
  }
  if (typeof fields.prompt === 'string') {
    const t = estimateTokens(fields.prompt);
    breakdown.prompt = t;
    total += t;
  }
  if (typeof fields.system === 'string') {
    const t = estimateTokens(fields.system);
    breakdown.system = t;
    total += t;
  }
  if (Array.isArray(fields.files)) {
    let filesTotal = 0;
    for (const f of fields.files) {
      if (typeof f?.content === 'string') {
        filesTotal += estimateTokens(f.content);
      }
    }
    if (filesTotal > 0) {
      breakdown.files = filesTotal;
      total += filesTotal;
    }
  }

  return { total, breakdown };
}
