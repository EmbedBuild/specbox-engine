/**
 * lib/output.mjs — Formatted output for SpecBox Engine hooks
 * Matches the exact output format of the original bash hooks.
 */

/**
 * Print a formatted block with ===== borders.
 * Uses stderr for error messages (blocking hooks).
 *
 * @param {string} title - Block title
 * @param {string[]} lines - Lines to print inside the block
 * @param {object} [opts]
 * @param {boolean} [opts.useStderr=false] - Print to stderr instead of stdout
 */
export function printBlock(title, lines, opts = {}) {
  const { useStderr = false } = opts;
  const out = useStderr ? process.stderr : process.stdout;

  out.write('\n');
  out.write('============================================================\n');
  out.write(`  ${title}\n`);
  out.write('============================================================\n');
  for (const line of lines) {
    out.write(`  ${line}\n`);
  }
  out.write('============================================================\n');
  out.write('\n');
}

/**
 * Print a warning message (non-blocking).
 */
export function printWarning(message) {
  process.stdout.write(`\nWARNING: ${message}\n`);
}

/**
 * Print an informational message.
 */
export function printInfo(message) {
  process.stdout.write(`${message}\n`);
}

// ── Canales que llegan al agente (US-93 · UC-9302) ──────────────────────
//
// Comprobado en sesiones reales de Claude Code 2.1.288 (doc/research/hooks-que-no-saltaban/):
//   - exit 2 + stderr: en PreToolUse impide la acción y el agente recibe el motivo; en
//     PostToolUse el agente recibe el motivo (la acción ya ocurrió).
//   - exit 0 + JSON con hookSpecificOutput.additionalContext: nota para el agente, sin impedir nada
//     (PreToolUse y PostToolUse).
//   - exit 1, o exit 0 con texto por stdout o stderr: no llega al agente ni bloquea. No usarlos.

/** Formatea un bloque con título y líneas. */
export function formatBlock(title, lines) {
  const bar = '============================================================';
  return [bar, `  ${title}`, bar, ...lines.map((l) => `  ${l}`), bar].join('\n');
}

/** Impide la acción (PreToolUse) o le dice al agente que corrija (PostToolUse): stderr + exit 2. */
export function blockWith(title, lines) {
  process.stderr.write(`\n${formatBlock(title, lines)}\n`);
  process.exit(2);
}

/** Nota para el agente, sin impedir la acción: additionalContext + exit 0. */
export function noteWith(event, title, lines) {
  const text = [title, ...lines].join('\n');
  process.stdout.write(JSON.stringify({ hookSpecificOutput: { hookEventName: event || 'PostToolUse', additionalContext: text } }));
  process.exit(0);
}
