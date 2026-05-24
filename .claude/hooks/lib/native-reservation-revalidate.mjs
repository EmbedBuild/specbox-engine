/**
 * native-reservation-revalidate.mjs — pure decision logic for spec-guard's
 * native reservation revalidation (UC-304 / AC-21 / AC-22, renamed in
 * UC-613 from native-claim-revalidate.mjs).
 *
 * spec-guard.mjs treats `.quality/active_uc.json` as a CACHE of the remote
 * reservation. The policy:
 *
 *   - Offline (no MCP URL, or the revalidation call failed/timed out) →
 *     trust the cache and ALLOW. The cached reservation is the dev's
 *     last-known-good state [AC-21].
 *   - Online and the MCP says the reservation is still the dev's → ALLOW.
 *   - Online and the MCP says the reservation is gone or now belongs to
 *     someone else → BLOCK with a message naming the conflict [AC-22].
 *
 * This module is pure (no I/O) so it is unit-testable. The hook performs
 * the actual network probe and feeds the result here.
 *
 * Wire-protocol compat (v5.35-v5.36)
 * ----------------------------------
 * The revalidation argument accepts BOTH the new shape
 * `{ reachable, reservation: {…} | null }` and the legacy shape
 * `{ reachable, claim: {…} | null }`. The legacy field is honoured as a
 * fallback so the hook continues to work against an MCP that has not yet
 * upgraded to the renamed endpoint. UC-612 removes the legacy fallback
 * in v5.37.0.
 */

/**
 * @param {object|null} reservation The cached reservation:
 *   { ucId, developerId, reservedAt? }.
 * @param {object} revalidation The probe result:
 *   { reachable: boolean,
 *     reservation?: { developer_id } | null,
 *     claim?: { developer_id } | null }    // legacy fallback (UC-612)
 *   - reachable=false → could not reach the MCP (offline / error / timeout).
 *   - reachable=true, reservation=null → the UC has no active reservation
 *     anymore.
 *   - reachable=true, reservation={developer_id} → the current remote owner.
 * @returns {{ allow: boolean, reason: string, conflict?: object }}
 */
export function decideNativeReservation(reservation, revalidation) {
  // No native reservation cached → this policy does not apply; let the
  // caller's normal freshness logic decide.
  if (!reservation) {
    return { allow: true, reason: 'no-native-reservation' };
  }

  // Offline / unreachable → trust the cache [AC-21].
  if (!revalidation || revalidation.reachable !== true) {
    return { allow: true, reason: 'offline-cache-trusted' };
  }

  // Accept new field `reservation`; fall back to legacy `claim` for
  // compat with an MCP that has not yet upgraded. Removed in v5.37.0
  // by UC-612.
  const remote =
    revalidation.reservation !== undefined ? revalidation.reservation : revalidation.claim;

  // Reservation vanished remotely (released or expired) → block [AC-22].
  if (!remote || !remote.developer_id) {
    return {
      allow: false,
      reason: 'reservation-released',
      conflict: { expected: reservation.developerId, actual: null },
    };
  }

  // Reservation now belongs to someone else → block [AC-22].
  if (remote.developer_id !== reservation.developerId) {
    return {
      allow: false,
      reason: 'reservation-taken-over',
      conflict: { expected: reservation.developerId, actual: remote.developer_id },
    };
  }

  // Still the dev's reservation → allow.
  return { allow: true, reason: 'reservation-confirmed' };
}
