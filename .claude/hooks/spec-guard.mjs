#!/usr/bin/env node
/**
 * spec-guard.mjs — PostToolUse hook for Write/Edit on source files (src/, lib/)
 * BLOCKING: Prevents writing source code without an active UC in the project manager.
 *
 * This hook enforces the SpecBox Engine contract:
 * "No code without traceability. No implementation without an active UC."
 *
 * v5.7.0 — Pipeline Integrity Enforcement
 */

import { execFileSync } from 'node:child_process';
import { readStdin, fileExists, fileAge, git } from './lib/utils.mjs';
import { getProjectConfig, getActiveUC, getActiveUCReservation, getStaleUC } from './lib/config.mjs';
import { decideNativeReservation } from './lib/native-reservation-revalidate.mjs';

/**
 * Best-effort revalidation of a native reservation against the MCP. Returns
 * { reachable, reservation } for decideNativeReservation. Never throws — any
 * failure (no URL, network error, timeout, bad JSON) yields reachable:false
 * so the cache is trusted [AC-21]. Online conflicts are surfaced for AC-22.
 *
 * Endpoint: GET /api/native/reservation-status?uc_id=...
 * Expected response: { uc_id, reservation: { developer_id } | null }
 *
 * Wire-protocol compat (v5.35-v5.36): if the MCP returns the legacy shape
 * { uc_id, claim: {…} | null } we pass `claim` through too, and the pure
 * decision module accepts both. UC-612 removes the fallback in v5.37.0.
 */
function probeNativeReservation(reservation) {
  const mcpUrl = process.env.SPECBOX_ENGINE_MCP_URL || process.env.DEV_ENGINE_MCP_URL || '';
  if (!mcpUrl) return { reachable: false };
  try {
    const url = `${mcpUrl.replace(/\/$/, '')}/api/native/reservation-status`;
    const out = execFileSync(
      'curl',
      [
        '-fsS', '--max-time', '3',
        '-L', // follow redirects so a server still serving the legacy URL
              // with a 301 to /reservation-status works transparently
        '-G', url,
        '--data-urlencode', `uc_id=${reservation.ucId}`,
      ],
      { encoding: 'utf8', timeout: 4000, stdio: ['ignore', 'pipe', 'ignore'] },
    );
    const data = JSON.parse(out);
    return {
      reachable: true,
      reservation: data.reservation ?? null,
      // Forward the legacy `claim` field too so the pure decision module
      // can fall back if the server has not yet upgraded.
      claim: data.claim ?? undefined,
    };
  } catch {
    return { reachable: false };
  }
}

const input = readStdin();

// Extract file path
let filePath = '';
try {
  const parsed = JSON.parse(input);
  filePath = parsed.file_path || '';
} catch {
  const match = input.match(/"file_path"\s*:\s*"([^"]*)"/);
  filePath = match ? match[1] : '';
}

if (!filePath) {
  process.exit(0);
}

// Only guard source code files (src/, lib/), not tests, docs, config, etc.
if (!/(^|\/)(?:src|lib)\//.test(filePath)) {
  process.exit(0);
}

// Skip test files, config files, generated files
if (/(test\/|tests\/|\.test\.|\.spec\.|_test\.dart|\.g\.dart|\.freezed\.dart|\.config\.|\.json$|\.yaml$|\.md$)/.test(filePath)) {
  process.exit(0);
}

// --- Check if project is spec-driven ---
const { boardId, backendType, isSpecDriven } = getProjectConfig();

// If no board and no backend configured → not spec-driven, allow
if (!isSpecDriven) {
  process.exit(0);
}

// --- Spec-driven project: verify branch discipline ---
const currentBranch = git('branch --show-current');

if (currentBranch === 'main' || currentBranch === 'master') {
  console.log('');
  console.log('============================================================');
  console.log(`  SPEC GUARD: Writing source code on ${currentBranch} blocked`);
  console.log('============================================================');
  console.log(`  File: ${filePath}`);
  console.log(`  Branch: ${currentBranch}`);
  console.log('');
  console.log('  Spec-driven projects require ALL code on feature branches.');
  console.log('  Create a branch first: git checkout -b feature/{name} main');
  console.log('============================================================');
  console.log('');
  process.exit(1);
}

// --- Spec-driven project: verify active UC ---
const activeUC = getActiveUC();
if (activeUC) {
  // Native reservation revalidation (UC-304, renamed in UC-613): the marker is
  // a cache of the remote reservation. Offline → trust it [AC-21]. Online →
  // revalidate; block if the reservation was released or taken over by another
  // dev [AC-22].
  const reservation = getActiveUCReservation();
  if (reservation) {
    const decision = decideNativeReservation(reservation, probeNativeReservation(reservation));
    if (!decision.allow) {
      const actual = decision.conflict?.actual;
      console.log('');
      console.log('============================================================');
      console.log('  ⛔ SPEC GUARD: Native UC reservation no longer yours');
      console.log('============================================================');
      console.log(`  File: ${filePath}`);
      console.log(`  UC: ${reservation.ucId}`);
      if (decision.reason === 'reservation-released') {
        console.log(`  The reservation was released remotely (you were ${reservation.developerId}).`);
        console.log('  Re-run start_uc to re-reserve before writing code.');
      } else {
        console.log(`  The reservation is now held by '${actual}' (you are '${reservation.developerId}').`);
        console.log('  Another developer took over this UC. Coordinate or pick another UC.');
      }
      console.log('============================================================');
      console.log('');
      process.exit(1);
    }
  }
  // Active UC exists and is fresh (and reservation still valid / offline) → allow
  process.exit(0);
}

// Check if stale
const staleUC = getStaleUC();
if (staleUC) {
  console.log('');
  console.log('============================================================');
  console.log('  ⛔ SPEC GUARD: Active UC marker is stale (>24h)');
  console.log('============================================================');
  console.log(`  File: ${filePath}`);
  console.log('  The active UC marker at .quality/active_uc.json is older than 24 hours.');
  console.log('  This likely means the previous implementation session ended');
  console.log('  without completing the UC.');
  console.log('');
  console.log('  To proceed:');
  console.log('    1. Run start_uc(board_id, uc_id) to activate a UC');
  console.log('    2. Or use /implement to start the pipeline properly');
  console.log('============================================================');
  console.log('');
  process.exit(1);
}

// No active UC marker → BLOCK
console.log('');
console.log('============================================================');
console.log('  ⛔ SPEC GUARD: No active UC — implementation blocked');
console.log('============================================================');
console.log(`  File: ${filePath}`);
console.log(`  Board: ${boardId}`);
console.log('');
console.log('  This project uses spec-driven development (Trello/Plane).');
console.log('  You MUST have an active UC before writing source code.');
console.log('');
console.log('  The SpecBox Engine contract is non-negotiable:');
console.log('  No code without traceability. No implementation without pipeline.');
console.log('');
console.log('  To proceed:');
console.log('    1. find_next_uc(board_id) → identify the next UC');
console.log('    2. start_uc(board_id, uc_id) → move to In Progress');
console.log('    3. Then implement the code');
console.log('    4. mark_ac_batch(...) → check acceptance criteria');
console.log('    5. complete_uc(board_id, uc_id) → move to Done');
console.log('');
console.log('  If /implement skill is unavailable, execute these steps');
console.log('  MANUALLY. The pipeline is the contract, not the skill.');
console.log('============================================================');
console.log('');
process.exit(1);
