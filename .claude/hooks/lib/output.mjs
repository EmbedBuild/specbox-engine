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
