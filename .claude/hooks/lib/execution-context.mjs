/**
 * lib/execution-context.mjs — read-side helpers for execution_context.json (v5.32.0).
 *
 * Hooks read this file to know which feature/branch/stack the active
 * Task is operating on. Writes happen exclusively from the SKILL.md
 * (Paso 0.4b) which delegates to the Python helper for atomicity —
 * hooks are read-only over this file.
 */

import { existsSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

const EVIDENCE_DIR = '.quality/evidence';
const FILENAME = 'execution_context.json';

/**
 * Resolve the path to execution_context.json for a feature.
 * @param {string} featureSlug
 * @param {string} [projectRoot] absolute path; defaults to process.cwd().
 * @returns {string}
 */
export function contextPath(featureSlug, projectRoot) {
  const root = projectRoot ? resolve(projectRoot) : process.cwd();
  return join(root, EVIDENCE_DIR, featureSlug, FILENAME);
}

/**
 * Read and parse the context file. Returns null if absent or corrupt
 * (hooks must degrade gracefully — a missing file means we're outside
 * a managed /implement run, NOT an error condition).
 * @param {string} featureSlug
 * @param {string} [projectRoot]
 * @returns {object | null}
 */
export function readExecutionContext(featureSlug, projectRoot) {
  const p = contextPath(featureSlug, projectRoot);
  if (!existsSync(p)) return null;
  try {
    return JSON.parse(readFileSync(p, 'utf-8'));
  } catch {
    return null;
  }
}

/**
 * Read the active_agent.json marker (transient, written by SKILL.md
 * just before Task() and removed after the Task returns).
 * @returns {{agent: string, feature_slug: string, phase: string, started_at: string} | null}
 */
export function readActiveAgent() {
  const p = join(process.cwd(), '.quality/active_agent.json');
  if (!existsSync(p)) return null;
  try {
    return JSON.parse(readFileSync(p, 'utf-8'));
  } catch {
    return null;
  }
}

/**
 * Convenience: get the execution context for the currently active
 * agent's feature, or null if no Task is currently active.
 * @returns {object | null}
 */
export function readContextForActiveAgent() {
  const active = readActiveAgent();
  if (!active?.feature_slug) return null;
  return readExecutionContext(active.feature_slug);
}
