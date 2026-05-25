/**
 * lib/mcp-client-io.mjs — Client-side filesystem I/O for content-passing MCP tools (v6.0.1).
 *
 * The v6.0.1 "MCP Path Contract" makes the MCP server filesystem-agnostic:
 * every tool that used to read or write client files now receives the
 * content as a string parameter and returns content to be written. The
 * client (skill or hook) is responsible for the actual filesystem I/O,
 * resolved against the local repo so it works identically whether the
 * MCP runs as stdio (local) or HTTP/SSE (remote VPS, claude.ai web, ...).
 *
 * This module exposes three helpers used by skills:
 *
 *   resolveProjectRoot()    → absolute path to the git toplevel of the CWD.
 *   readContentBundle(paths) → { "<relative>": string | null } map.
 *   writeContentBundle(bundle) → writes everything, returns { written, skipped }.
 *
 * All paths in bundles are RELATIVE to the project root so payloads sent to
 * MCP tools are independent of the caller's absolute filesystem layout.
 */

import { execSync } from 'node:child_process';
import {
  existsSync,
  mkdirSync,
  readFileSync,
  writeFileSync,
} from 'node:fs';
import { dirname, isAbsolute, join, resolve } from 'node:path';

/**
 * Locate the git toplevel of the caller's CWD. Used as the canonical
 * "project root" against which all relative bundle paths are resolved.
 *
 * @param {object} [opts]
 * @param {string} [opts.cwd] - Override CWD (default: process.cwd()).
 * @returns {string} Absolute path to the project root.
 * @throws {Error} When the CWD is not inside a git repository.
 */
export function resolveProjectRoot(opts = {}) {
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
      `resolveProjectRoot: ${cwd} is not inside a git repository. `
      + 'mcp-client-io requires a git repo to anchor relative paths.'
    );
  }
  if (!toplevel) {
    throw new Error('resolveProjectRoot: git rev-parse returned empty output');
  }
  return toplevel;
}

/**
 * Read a list of files relative to the project root and return a bundle
 * suitable for passing as `*_content` parameters to MCP tools.
 *
 * - Files that exist → bundle[relpath] = file content (UTF-8 string).
 * - Files that do not exist → bundle[relpath] = null.
 * - Absolute paths are rejected — bundles must be relative to project root.
 *
 * @param {string[]} relativePaths
 * @param {object} [opts]
 * @param {string} [opts.root] - Override project root (default: resolveProjectRoot()).
 * @returns {Record<string, string | null>}
 */
export function readContentBundle(relativePaths, opts = {}) {
  if (!Array.isArray(relativePaths)) {
    throw new TypeError('readContentBundle: paths must be an array');
  }
  const root = opts.root || resolveProjectRoot();
  const bundle = {};
  for (const rel of relativePaths) {
    if (typeof rel !== 'string' || rel.length === 0) {
      throw new TypeError(
        `readContentBundle: each path must be a non-empty string (got ${JSON.stringify(rel)})`
      );
    }
    if (isAbsolute(rel)) {
      throw new Error(
        `readContentBundle: refusing to read absolute path ${JSON.stringify(rel)}. `
        + 'Pass paths relative to the project root.'
      );
    }
    // Prevent path traversal outside root.
    const abs = resolve(root, rel);
    if (!abs.startsWith(root + '/') && abs !== root) {
      throw new Error(
        `readContentBundle: path ${JSON.stringify(rel)} escapes the project root.`
      );
    }
    if (!existsSync(abs)) {
      bundle[rel] = null;
      continue;
    }
    bundle[rel] = readFileSync(abs, { encoding: 'utf-8' });
  }
  return bundle;
}

/**
 * Write a bundle of relative-path → content entries under the project root.
 * Each non-null value is written (creating parent directories as needed).
 * Null/undefined values are skipped (caller can pass a single dict mixing
 * "files I want written" and "files I read but won't touch").
 *
 * @param {Record<string, string | null | undefined>} bundle
 * @param {object} [opts]
 * @param {string} [opts.root] - Override project root.
 * @returns {{ written: string[], skipped: string[] }}
 */
export function writeContentBundle(bundle, opts = {}) {
  if (bundle === null || typeof bundle !== 'object') {
    throw new TypeError('writeContentBundle: bundle must be an object');
  }
  const root = opts.root || resolveProjectRoot();
  const written = [];
  const skipped = [];
  for (const [rel, content] of Object.entries(bundle)) {
    if (typeof rel !== 'string' || rel.length === 0) {
      throw new TypeError(
        `writeContentBundle: each key must be a non-empty string (got ${JSON.stringify(rel)})`
      );
    }
    if (isAbsolute(rel)) {
      throw new Error(
        `writeContentBundle: refusing to write absolute path ${JSON.stringify(rel)}. `
        + 'Bundle keys must be relative to the project root.'
      );
    }
    if (content === null || content === undefined) {
      skipped.push(rel);
      continue;
    }
    if (typeof content !== 'string') {
      throw new TypeError(
        `writeContentBundle: value for ${JSON.stringify(rel)} must be a string or null (got ${typeof content})`
      );
    }
    const abs = resolve(root, rel);
    if (!abs.startsWith(root + '/') && abs !== root) {
      throw new Error(
        `writeContentBundle: path ${JSON.stringify(rel)} escapes the project root.`
      );
    }
    mkdirSync(dirname(abs), { recursive: true });
    writeFileSync(abs, content, { encoding: 'utf-8' });
    written.push(rel);
  }
  return { written, skipped };
}
