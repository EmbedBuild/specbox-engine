/**
 * lib/config.mjs — Project configuration reader for SpecBox Engine hooks
 * Zero external dependencies.
 */

import { readJsonFile, fileAge } from './utils.mjs';

/**
 * Read project configuration from .claude/project-config.json and .claude/settings.local.json.
 * Returns { boardId, backendType, orchestratorRoot, isSpecDriven }.
 *
 * Multi-repo support (v5.20):
 *   If the project declares multirepo.role = "satellite" with an orchestrator path,
 *   orchestratorRoot resolves to that path. Otherwise defaults to '.' (current repo).
 *   Hooks that need cross-repo paths (design-gate, e2e-gate) use orchestratorRoot.
 */
export function getProjectConfig() {
  let boardId = '';
  let backendType = '';
  let orchestratorRoot = '.';

  for (const configFile of ['.claude/project-config.json', '.claude/settings.local.json']) {
    const config = readJsonFile(configFile);
    if (!config) continue;

    if (!boardId) {
      boardId = config.boardId || config.board_id || '';
    }
    if (!backendType) {
      backendType = config.backend_type || '';
    }

    // Multi-repo: resolve orchestrator path for satellite repos
    const mr = config.multirepo;
    if (mr?.enabled && mr?.role === 'satellite' && mr?.orchestrator) {
      orchestratorRoot = mr.orchestrator;
    }
  }

  return {
    boardId,
    backendType,
    orchestratorRoot,
    isSpecDriven: !!(boardId || backendType),
  };
}

/**
 * Read the active UC marker from .quality/active_uc.json.
 * Returns { ucId, feature, timestamp } or null if not found or stale (>24h).
 */
export function getActiveUC() {
  const filePath = '.quality/active_uc.json';
  const data = readJsonFile(filePath);
  if (!data) return null;

  // Check freshness (must be < 24 hours old)
  const age = fileAge(filePath);
  if (age > 86400) return null;

  return {
    ucId: data.uc_id || '',
    feature: data.feature || '',
    timestamp: data.timestamp || '',
    fresh: true,
  };
}

/**
 * Read the native reservation cache from the active UC marker, if present.
 * The marker written by start_uc on a native session carries a `reservation`
 * block (uc_id, developer_id, reserved_at, backend) so this hook can treat
 * the file as a cache and revalidate it against the MCP when online [AC-21].
 *
 * Wire-protocol compat (v5.35-v5.36): if the marker still carries the legacy
 * `claim` key (written by a Python side that has not yet upgraded), it is
 * honoured as a fallback. UC-612 removes the legacy fallback in v5.37.0.
 *
 * Returns { ucId, developerId, reservedAt } or null when there is no native
 * reservation cached (FreeForm/Trello/Plane markers have no reservation
 * block).
 */
export function getActiveUCReservation() {
  const filePath = '.quality/active_uc.json';
  const data = readJsonFile(filePath);
  if (!data) return null;
  // Prefer the new `reservation` field; fall back to legacy `claim` for
  // compat with a Python side that has not yet upgraded. UC-612 removes
  // the fallback in v5.37.0.
  const block = data.reservation !== undefined ? data.reservation : data.claim;
  if (!block || block.backend !== 'native') return null;
  return {
    ucId: block.uc_id || data.uc_id || '',
    developerId: block.developer_id || '',
    // Accept the new key first, fall back to the legacy one.
    reservedAt: block.reserved_at || block.claimed_at || '',
  };
}

/**
 * Check if the active UC marker exists but is stale (>24h).
 * Returns { stale: true, ucId, feature } or null.
 */
export function getStaleUC() {
  const filePath = '.quality/active_uc.json';
  const data = readJsonFile(filePath);
  if (!data) return null;

  const age = fileAge(filePath);
  if (age <= 86400) return null;

  return {
    stale: true,
    ucId: data.uc_id || '',
    feature: data.feature || '',
  };
}
