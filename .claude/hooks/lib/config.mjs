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
 * Read the native claim cache from the active UC marker, if present.
 * The marker written by start_uc on a native session carries a `claim` block
 * (uc_id, developer_id, claimed_at, backend) so this hook can treat the file
 * as a cache and revalidate it against the MCP when online [AC-21].
 *
 * Returns { ucId, developerId, claimedAt } or null when there is no native
 * claim cached (FreeForm/Trello/Plane markers have no claim block).
 */
export function getActiveUCClaim() {
  const filePath = '.quality/active_uc.json';
  const data = readJsonFile(filePath);
  if (!data || !data.claim || data.claim.backend !== 'native') return null;
  return {
    ucId: data.claim.uc_id || data.uc_id || '',
    developerId: data.claim.developer_id || '',
    claimedAt: data.claim.claimed_at || '',
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
