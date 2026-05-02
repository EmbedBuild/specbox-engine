/**
 * lib/freeform-path.mjs — Resolve FreeForm root paths client-side.
 *
 * The MCP server may be remote (env SPECBOX_ENGINE_MCP_URL set), in which
 * case relative paths are unsafe: the server resolves them against its own
 * CWD, not the client's repo. This helper builds an absolute path from the
 * git toplevel of the calling client, so set_auth_token always receives a
 * path the MCP can write to deterministically.
 */

import { isAbsolute, join } from 'path';
import { execSync } from 'child_process';

/**
 * Resolve a FreeForm root path to an absolute path on the client filesystem.
 *
 * @param {string} relativeOrAbsolute - Path string. If already absolute,
 *   returned unchanged. If relative, joined onto the git toplevel of the CWD.
 * @param {object} [opts]
 * @param {string} [opts.cwd] - Override CWD (default: process.cwd()). Useful
 *   for tests; production callers don't pass this.
 * @returns {string} Absolute path safe to pass to set_auth_token.
 * @throws {Error} If relative and no git repo is detected at CWD.
 */
export function resolveFreeformPath(relativeOrAbsolute, opts = {}) {
  if (typeof relativeOrAbsolute !== 'string' || relativeOrAbsolute.length === 0) {
    throw new Error('resolveFreeformPath: input must be a non-empty string');
  }
  if (isAbsolute(relativeOrAbsolute)) {
    return relativeOrAbsolute;
  }
  const cwd = opts.cwd || process.cwd();
  let toplevel;
  try {
    toplevel = execSync('git rev-parse --show-toplevel', {
      cwd,
      encoding: 'utf-8',
      stdio: ['ignore', 'pipe', 'ignore'],
    }).trim();
  } catch {
    throw new Error(
      `resolveFreeformPath: cannot resolve relative path ${JSON.stringify(relativeOrAbsolute)} `
      + 'because no git repository was found at the CWD. Pass an absolute '
      + 'path or invoke from inside a git repo.'
    );
  }
  return join(toplevel, relativeOrAbsolute);
}

/**
 * Whether the current Claude Code session is talking to a remote MCP server.
 * Hooks and skills use this to decide if relative FreeForm paths must be
 * rejected client-side before reaching set_auth_token.
 */
export function isRemoteMcp() {
  return Boolean((process.env.SPECBOX_ENGINE_MCP_URL || '').trim());
}
