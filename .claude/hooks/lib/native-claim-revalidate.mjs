/**
 * native-claim-revalidate.mjs — pure decision logic for spec-guard's native
 * claim revalidation (UC-304, AC-21 / AC-22).
 *
 * spec-guard.mjs treats `.quality/active_uc.json` as a CACHE of the remote
 * claim. The policy:
 *
 *   - Offline (no MCP URL, or the revalidation call failed/timed out) → trust
 *     the cache and ALLOW. The cached claim is the dev's last-known-good state
 *     [AC-21].
 *   - Online and the MCP says the claim is still the dev's → ALLOW.
 *   - Online and the MCP says the claim is gone or now belongs to someone else
 *     → BLOCK with a message naming the conflict [AC-22].
 *
 * This module is pure (no I/O) so it is unit-testable. The hook performs the
 * actual network probe and feeds the result here.
 */

/**
 * @param {object|null} claim   The cached claim: { ucId, developerId }.
 * @param {object} revalidation The probe result:
 *   { reachable: boolean, claim?: { developer_id }|null }
 *   - reachable=false → could not reach the MCP (offline / error / timeout).
 *   - reachable=true, claim=null → the UC has no active claim anymore.
 *   - reachable=true, claim={developer_id} → the current remote owner.
 * @returns {{ allow: boolean, reason: string, conflict?: object }}
 */
export function decideNativeClaim(claim, revalidation) {
  // No native claim cached → this policy does not apply; let the caller's
  // normal freshness logic decide.
  if (!claim) {
    return { allow: true, reason: 'no-native-claim' };
  }

  // Offline / unreachable → trust the cache [AC-21].
  if (!revalidation || revalidation.reachable !== true) {
    return { allow: true, reason: 'offline-cache-trusted' };
  }

  const remote = revalidation.claim;

  // Claim vanished remotely (released or expired) → block [AC-22].
  if (!remote || !remote.developer_id) {
    return {
      allow: false,
      reason: 'claim-released',
      conflict: { expected: claim.developerId, actual: null },
    };
  }

  // Claim now belongs to someone else → block [AC-22].
  if (remote.developer_id !== claim.developerId) {
    return {
      allow: false,
      reason: 'claim-taken-over',
      conflict: { expected: claim.developerId, actual: remote.developer_id },
    };
  }

  // Still the dev's claim → allow.
  return { allow: true, reason: 'claim-confirmed' };
}
