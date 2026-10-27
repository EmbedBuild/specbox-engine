/**
 * lib/freeform-path.mjs — Resolve FreeForm root paths client-side.
 *
 * The MCP server may be remote (an http entry or an mcp-remote bridge in the
 * Claude Code config, or env SPECBOX_ENGINE_MCP_URL set), in which case it has
 * no access to the client's files and the board travels as items_content. With
 * a local server, this helper builds an absolute path from the git toplevel of
 * the calling client, so set_auth_token always receives a path the MCP can
 * write to deterministically.
 */

import { isAbsolute, join } from 'path';
import { execSync } from 'child_process';
import { readFileSync } from 'fs';
import { homedir } from 'os';

/** The server name the hooks match on (`mcp__SpecBox-MCP__…`). */
export const SPECBOX_SERVER = 'SpecBox-MCP';

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

function readJson(path) {
  try {
    return JSON.parse(readFileSync(path, 'utf-8'));
  } catch {
    return null;
  }
}

function gitToplevel(cwd) {
  try {
    return execSync('git rev-parse --show-toplevel', {
      cwd,
      encoding: 'utf-8',
      stdio: ['ignore', 'pipe', 'ignore'],
    }).trim();
  } catch {
    return null;
  }
}

/**
 * The SpecBox-MCP entry Claude Code uses for this project, with its precedence:
 * local scope (~/.claude.json → projects[<root>]), then project scope (<root>/.mcp.json),
 * then user scope (~/.claude.json). null when none declares it.
 */
export function specboxServerEntry({ cwd = process.cwd(), home = homedir() } = {}) {
  const root = gitToplevel(cwd) || cwd;
  const claude = readJson(join(home, '.claude.json')) || {};
  const candidates = [
    claude.projects?.[root]?.mcpServers,
    readJson(join(root, '.mcp.json'))?.mcpServers,
    claude.mcpServers,
  ];
  for (const servers of candidates) {
    if (servers?.[SPECBOX_SERVER]) return servers[SPECBOX_SERVER];
  }
  return null;
}

/** An MCP entry that reaches a server over the network: http/sse, or a bridge such as mcp-remote. */
export function isRemoteEntry(entry) {
  if (!entry || typeof entry !== 'object') return false;
  if (['http', 'sse', 'streamable-http'].includes(entry.type) || entry.url) return true;
  const args = Array.isArray(entry.args) ? entry.args.map(String) : [];
  return args.includes('mcp-remote') || args.some((a) => /^https?:\/\//.test(a));
}

/**
 * Whether the current Claude Code session is talking to a remote MCP server.
 * Hooks and skills use this to decide whether set_auth_token may carry a
 * FreeForm directory at all (a remote server has no access to it).
 *
 * UC-11101: SPECBOX_ENGINE_MCP_URL is only written by the VSCode extension, so
 * a project onboarded any other way also looks at how Claude Code reaches the
 * SpecBox-MCP server.
 */
export function isRemoteMcp({ env = process.env, cwd = process.cwd(), home = homedir() } = {}) {
  if ((env.SPECBOX_ENGINE_MCP_URL || '').trim()) return true;
  return isRemoteEntry(specboxServerEntry({ cwd, home }));
}
