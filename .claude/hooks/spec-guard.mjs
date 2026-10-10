#!/usr/bin/env node
/**
 * spec-guard.mjs — PostToolUse hook for Write/Edit on source files (src/, lib/)
 *
 * After the write (PostToolUse cannot undo it), in a spec-driven project:
 *   - code on main/master, or under a native reservation that is no longer yours → exit 2: the
 *     agent gets the reason and has to move the work (US-93/UC-9302; it exited 1, unseen);
 *   - code with no active UC (or a stale marker) → a note to the agent (additionalContext).
 *
 * This hook enforces the SpecBox Engine contract:
 * "No code without traceability. No implementation without an active UC."
 *
 * v5.7.0 — Pipeline Integrity Enforcement
 */

import { execFileSync } from 'node:child_process';
import { readStdin, fileExists, fileAge, git } from './lib/utils.mjs';
import { blockWith, noteWith } from './lib/output.mjs';
import { dirname, isAbsolute } from 'node:path';
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
  // Claude Code sends the tool's arguments in tool_input; the top level is the old test format.
  filePath = (parsed.tool_input ?? parsed).file_path || '';
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

// The repo the file lives in (a write to another worktree is checked against that worktree).
if (isAbsolute(filePath)) {
  try {
    const top = execFileSync('git', ['-C', dirname(filePath), 'rev-parse', '--show-toplevel'], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim();
    if (top) process.chdir(top);
  } catch { /* not in a git repo: keep the session's directory */ }
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
  blockWith(`SPEC GUARD: código escrito en ${currentBranch}`, [
    `Fichero: ${filePath}`,
    'Es un proyecto spec-driven: el código va en una rama de la UC, nunca en main ni en master.',
    'La escritura ya está hecha. Antes de seguir: git checkout -b feature/{uc}-{nombre} (los cambios se van contigo).',
  ]);
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
      blockWith('SPEC GUARD: la reserva de la UC ya no es tuya', [
        `Fichero: ${filePath}`,
        `UC: ${reservation.ucId}`,
        decision.reason === 'reservation-released'
          ? `La reserva se liberó en remoto (eras ${reservation.developerId}). Vuelve a llamar a start_uc antes de seguir escribiendo.`
          : `Ahora la tiene '${actual}' (tú eres '${reservation.developerId}'). Coordínate con esa persona o elige otra UC.`,
      ]);
    }
  }
  // Active UC exists and is fresh (and reservation still valid / offline) → allow
  process.exit(0);
}

// No active UC (or a stale marker) → a note: the agent should start the UC.
const staleUC = getStaleUC();
noteWith('PostToolUse', staleUC ? 'SPEC GUARD: la UC activa lleva más de 24 h sin tocarse' : 'SPEC GUARD: código sin UC activa', [
  `Fichero: ${filePath} · board ${boardId}`,
  staleUC
    ? 'El marcador .quality/active_uc.json tiene más de 24 h: la sesión anterior terminó sin cerrar la UC.'
    : 'En un proyecto spec-driven todo código va asociado a una UC.',
  'Recorrido: find_next_uc → start_uc → implementar → mark_ac_batch → complete_uc (o /implement).',
]);
