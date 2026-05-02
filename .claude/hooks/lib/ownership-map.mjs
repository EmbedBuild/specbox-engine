// lib/ownership-map.mjs — parse file-ownership.md → {agent → glob[]} (v5.32.0).
//
// The single source of truth for ownership lives in
// .claude/skills/implement/file-ownership.md as a Markdown table.
// This parser reads that table without forcing a YAML/JSON copy that
// would drift. If the table is malformed, returns an empty map and
// lets the caller fail-open (degradation graceful — never block on
// a parser bug).

import { existsSync, readFileSync } from 'node:fs';

const DEFAULT_OWNERSHIP_PATH = '.claude/skills/implement/file-ownership.md';
const AGENT_ID_RE = /\b(AG-\d{2}[a-z]?)\b/;

/**
 * Parse a Markdown table cell that contains a comma-separated list of
 * globs. Returns the trimmed glob array.
 * @param {string} cell
 * @returns {string[]}
 */
export function parseOwnershipCell(cell) {
  if (!cell) return [];
  return cell
    .split(',')
    .map((g) => g.trim())
    .filter((g) => g.length > 0);
}

/**
 * Parse file-ownership.md and return a map { "AG-01": ["lib/features/**", ...] }.
 * @param {string} [path]
 * @returns {Record<string, string[]>}
 */
export function parseOwnershipMap(path = DEFAULT_OWNERSHIP_PATH) {
  if (!existsSync(path)) return {};
  let body;
  try {
    body = readFileSync(path, 'utf-8');
  } catch {
    return {};
  }

  const map = {};
  const lines = body.split('\n');
  for (const line of lines) {
    if (!line.includes('|')) continue;
    if (line.includes('---')) continue; // separator row
    const cells = line
      .split('|')
      .map((c) => c.trim())
      .filter((_, i, arr) => i > 0 && i < arr.length - 1); // strip leading/trailing empties
    if (cells.length < 2) continue;
    const agentMatch = cells[0].match(AGENT_ID_RE);
    if (!agentMatch) continue;
    map[agentMatch[1]] = parseOwnershipCell(cells[cells.length - 1]);
  }
  return map;
}

// Convert one of our supported glob patterns to a RegExp.
//
// Supported tokens:
//   /<DBLSTAR>/  → matches any number of path segments (incl. zero)
//   <DBLSTAR>    → matches any number of path segments
//   *            → matches any chars except '/'
//   ?            → matches any single char except '/'
//
// (DBLSTAR = literally two asterisks — written this way in the comment
//  to avoid closing JSDoc parsing inside the source.)
//
// Also normalises a leading "./".
export function globToRegExp(pattern) {
  const cleaned = pattern.replace(/^\.\//, '');
  // Token-by-token transformation: walk the string and emit regex
  // pieces. This avoids the trap where a later replacement of "*"
  // accidentally rewrites a "*" that came from an earlier escape.
  let out = '';
  let i = 0;
  while (i < cleaned.length) {
    const c = cleaned[i];
    // /**/ → match any number of segments (including zero) — handle
    // before the bare "**" rule.
    if (cleaned.startsWith('/**/', i)) {
      out += '(?:/.+)?/'; // "/" or "/anything/"
      i += 4;
      continue;
    }
    // trailing /**
    if (cleaned.startsWith('/**', i) && i + 3 === cleaned.length) {
      out += '(?:/.*)?';
      i += 3;
      continue;
    }
    // leading **/
    if (i === 0 && cleaned.startsWith('**/', i)) {
      out += '(?:.*/)?';
      i += 3;
      continue;
    }
    // bare ** anywhere else
    if (cleaned.startsWith('**', i)) {
      out += '.*';
      i += 2;
      continue;
    }
    // single *
    if (c === '*') {
      out += '[^/]*';
      i += 1;
      continue;
    }
    if (c === '?') {
      out += '[^/]';
      i += 1;
      continue;
    }
    // regex meta → escape
    if ('.+^${}()|[]\\'.includes(c)) {
      out += '\\' + c;
      i += 1;
      continue;
    }
    out += c;
    i += 1;
  }
  return new RegExp(`^${out}$`);
}

/**
 * Reject suspicious paths that try to escape the repo (`..`, absolute
 * paths). Hooks should call this BEFORE matching against ownership
 * to fail fast on attempted directory traversal.
 * @param {string} path
 * @returns {boolean}
 */
export function isSuspiciousPath(path) {
  if (typeof path !== 'string' || path.length === 0) return true;
  if (path.includes('..')) return true;
  if (path.startsWith('/')) return true; // absolute path
  return false;
}

/**
 * Check whether a relative repo path is allowed for a given agent.
 *
 * Rules:
 *   - Suspicious paths return false (caller should reject).
 *   - Unknown agent → returns null (caller should fail-open with warning).
 *   - Empty ownership → returns null (same: probably a parsing problem).
 *   - Otherwise: true if any glob matches, false otherwise.
 *
 * @param {string} repoRelativePath
 * @param {string} agent
 * @param {Record<string, string[]>} map
 * @returns {boolean | null}
 */
export function pathAllowedForAgent(repoRelativePath, agent, map) {
  if (isSuspiciousPath(repoRelativePath)) return false;
  const globs = map?.[agent];
  if (!globs || globs.length === 0) return null;
  return globs.some((g) => globToRegExp(g).test(repoRelativePath));
}
