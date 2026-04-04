/**
 * lib/utils.mjs — Core utilities for SpecBox Engine hooks (cross-platform)
 * Zero external dependencies. Node.js 18+ built-in modules only.
 */

import { readFileSync, existsSync, statSync, mkdirSync, appendFileSync, readdirSync } from 'fs';
import { basename, join, resolve, dirname } from 'path';
import { execSync } from 'child_process';
import { fileURLToPath } from 'url';

/**
 * Read all of stdin synchronously (fd 0).
 * Claude Code passes tool input as JSON via stdin.
 */
export function readStdin() {
  try {
    return readFileSync(0, 'utf-8');
  } catch {
    return '';
  }
}

/**
 * Execute a git command and return trimmed stdout.
 * Returns '' on any error (not a git repo, command fails, etc.)
 */
export function git(cmd) {
  try {
    return execSync(`git ${cmd}`, { encoding: 'utf-8', stdio: ['pipe', 'pipe', 'pipe'] }).trim();
  } catch {
    return '';
  }
}

/**
 * Read and parse a JSON file. Returns null if missing or invalid.
 */
export function readJsonFile(filePath) {
  if (!existsSync(filePath)) return null;
  try {
    return JSON.parse(readFileSync(filePath, 'utf-8'));
  } catch {
    return null;
  }
}

/**
 * Check if a file exists.
 */
export function fileExists(filePath) {
  return existsSync(filePath);
}

/**
 * Get file age in seconds. Returns Infinity if file doesn't exist.
 */
export function fileAge(filePath) {
  if (!existsSync(filePath)) return Infinity;
  try {
    return (Date.now() - statSync(filePath).mtimeMs) / 1000;
  } catch {
    return Infinity;
  }
}

/**
 * Recursively find files matching a name pattern and optional path substring.
 * Cross-platform — no shell commands.
 *
 * @param {string} dir - Root directory to search
 * @param {RegExp|string} namePattern - Regex or string to match filename
 * @param {string} [pathContains] - Optional substring the full path must contain
 * @returns {string[]} Array of matching full paths
 */
export function findFiles(dir, namePattern, pathContains) {
  const results = [];
  if (!existsSync(dir)) return results;

  const regex = typeof namePattern === 'string' ? new RegExp(namePattern) : namePattern;

  function walk(current) {
    let entries;
    try {
      entries = readdirSync(current, { withFileTypes: true });
    } catch {
      return;
    }
    for (const entry of entries) {
      const fullPath = join(current, entry.name);
      if (entry.isDirectory()) {
        walk(fullPath);
      } else if (entry.isFile()) {
        if (regex.test(entry.name)) {
          if (!pathContains || fullPath.includes(pathContains)) {
            results.push(fullPath);
          }
        }
      }
    }
  }

  walk(dir);
  return results;
}

/**
 * Create directory recursively (like mkdir -p).
 */
export function mkdir(dir) {
  mkdirSync(dir, { recursive: true });
}

/**
 * Append a line to a file (for JSONL logging).
 * Creates parent directories if needed.
 */
export function appendLine(filePath, line) {
  const dir = dirname(filePath);
  if (!existsSync(dir)) {
    mkdirSync(dir, { recursive: true });
  }
  appendFileSync(filePath, line + '\n', 'utf-8');
}

/**
 * Get the project name from git root, replacing underscores with hyphens.
 */
export function getProjectName() {
  const root = git('rev-parse --show-toplevel');
  if (!root) return 'unknown';
  return basename(root).replace(/_/g, '-');
}

/**
 * Current UTC timestamp in ISO 8601 format.
 */
export function now() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
}

/**
 * Check if a command exists on the system (cross-platform).
 * Uses 'which' on Unix, 'where' on Windows.
 */
export function commandExists(cmd) {
  try {
    const checker = process.platform === 'win32' ? 'where' : 'which';
    execSync(`${checker} ${cmd}`, { stdio: ['pipe', 'pipe', 'pipe'] });
    return true;
  } catch {
    return false;
  }
}

/**
 * Resolve the engine root directory (two levels up from hooks/).
 */
export function getEngineRoot() {
  const __filename = fileURLToPath(import.meta.url);
  const __dirname = dirname(__filename);
  return resolve(__dirname, '..', '..', '..');
}

/**
 * Resolve the hooks directory.
 */
export function getHooksDir() {
  const __filename = fileURLToPath(import.meta.url);
  const __dirname = dirname(__filename);
  return resolve(__dirname, '..');
}
