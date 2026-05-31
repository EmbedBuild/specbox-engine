/**
 * lib/fs-scan.mjs — Filesystem scanning helpers for the client-side analyzers (UC-663).
 *
 * These replace the `ctx.project_path.rglob("*")` walks that the Python
 * analyzers ran on the MCP host (broken in remote setups). Here they run on
 * the client repo, so the audit reflects the user's real files.
 *
 * No external deps — pure node:fs. Pruned directories match the Python
 * analyzers' skip-lists so file counts stay comparable.
 */

import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative, extname } from 'node:path';

/** Directories never descended into (union of the Python analyzers' skip-lists). */
export const PRUNE_DIRS = new Set([
  'node_modules', '.git', 'build', 'dist', '.venv', 'venv',
  '.dart_tool', '__pycache__', '.next', 'coverage',
]);

export const SOURCE_EXTS = new Set(['.py', '.ts', '.tsx', '.js', '.jsx', '.dart', '.go']);
export const TEST_HINTS = new Set(['test', 'tests', '__tests__', 'spec']);

/**
 * Walk a directory tree yielding absolute file paths, pruning PRUNE_DIRS.
 * Generator so callers can break early (e.g. portability's 500-file cap).
 *
 * @param {string} root
 * @param {object} [opts]
 * @param {Set<string>} [opts.prune] - override PRUNE_DIRS
 * @returns {Generator<string>}
 */
export function* walkFiles(root, opts = {}) {
  const prune = opts.prune || PRUNE_DIRS;
  const stack = [root];
  while (stack.length) {
    const dir = stack.pop();
    let entries;
    try {
      entries = readdirSync(dir, { withFileTypes: true });
    } catch {
      continue;
    }
    for (const e of entries) {
      const abs = join(dir, e.name);
      if (e.isDirectory()) {
        if (prune.has(e.name)) continue;
        stack.push(abs);
      } else if (e.isFile()) {
        yield abs;
      }
    }
  }
}

/** True if any path segment (lowercased) is a test hint. */
export function isTestPath(absPath, root) {
  const rel = relative(root, absPath).toLowerCase();
  return rel.split(/[\\/]/).some((seg) => TEST_HINTS.has(seg));
}

/** Lowercase extension including the dot (''.ext). */
export function ext(absPath) {
  return extname(absPath).toLowerCase();
}

/** Relative path with forward slashes, falling back to abs if outside root. */
export function relPath(absPath, root) {
  const r = relative(root, absPath);
  if (r.startsWith('..')) return absPath;
  return r.split('\\').join('/');
}

/** st_size in bytes, or 0 on error. */
export function sizeOf(absPath) {
  try {
    return statSync(absPath).size;
  } catch {
    return 0;
  }
}

/** Read a file as UTF-8, returning '' on error (mirrors errors="ignore"). */
export function readText(absPath) {
  try {
    return readFileSync(absPath, 'utf-8');
  } catch {
    return '';
  }
}

/** True if a path exists relative to root. */
export function exists(root, ...rel) {
  return existsSync(join(root, ...rel));
}

/** True if any of the given relative names exists under root. */
export function anyExists(root, names) {
  return names.some((n) => existsSync(join(root, n)));
}

/** True if a relative path is a directory. */
export function isDir(root, ...rel) {
  try {
    return statSync(join(root, ...rel)).isDirectory();
  } catch {
    return false;
  }
}
