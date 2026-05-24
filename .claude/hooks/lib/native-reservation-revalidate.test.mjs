#!/usr/bin/env node
/**
 * native-reservation-revalidate.test.mjs — UC-613 AC-05 (Node side).
 * Run: node .claude/hooks/lib/native-reservation-revalidate.test.mjs
 *
 * Uses Node's built-in test runner (node:test) — zero external deps.
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { decideNativeReservation } from './native-reservation-revalidate.mjs';

// ── No cached reservation → policy does not apply ────────────────────

test('decideNativeReservation: no cached reservation → allow with no-native-reservation', () => {
  const decision = decideNativeReservation(null, { reachable: true });
  assert.equal(decision.allow, true);
  assert.equal(decision.reason, 'no-native-reservation');
});

// ── Offline cache trust ─────────────────────────────────────────────

test('decideNativeReservation: offline (reachable=false) trusts the cache', () => {
  const reservation = { ucId: 'UC-301', developerId: 'alice' };
  const decision = decideNativeReservation(reservation, { reachable: false });
  assert.equal(decision.allow, true);
  assert.equal(decision.reason, 'offline-cache-trusted');
});

test('decideNativeReservation: missing revalidation object trusts the cache', () => {
  const reservation = { ucId: 'UC-301', developerId: 'alice' };
  const decision = decideNativeReservation(reservation, undefined);
  assert.equal(decision.allow, true);
  assert.equal(decision.reason, 'offline-cache-trusted');
});

// ── Online: new wire shape (reservation field) ─────────────────────

test('decideNativeReservation: online + reservation still ours → allow', () => {
  const reservation = { ucId: 'UC-301', developerId: 'alice' };
  const decision = decideNativeReservation(reservation, {
    reachable: true,
    reservation: { developer_id: 'alice' },
  });
  assert.equal(decision.allow, true);
  assert.equal(decision.reason, 'reservation-confirmed');
});

test('decideNativeReservation: online + reservation released → block', () => {
  const reservation = { ucId: 'UC-301', developerId: 'alice' };
  const decision = decideNativeReservation(reservation, {
    reachable: true,
    reservation: null,
  });
  assert.equal(decision.allow, false);
  assert.equal(decision.reason, 'reservation-released');
  assert.deepEqual(decision.conflict, { expected: 'alice', actual: null });
});

test('decideNativeReservation: online + reservation taken over → block', () => {
  const reservation = { ucId: 'UC-301', developerId: 'alice' };
  const decision = decideNativeReservation(reservation, {
    reachable: true,
    reservation: { developer_id: 'bob' },
  });
  assert.equal(decision.allow, false);
  assert.equal(decision.reason, 'reservation-taken-over');
  assert.deepEqual(decision.conflict, { expected: 'alice', actual: 'bob' });
});

// ── Legacy wire shape (claim field) — compat for v5.35-v5.36 ───────

test('decideNativeReservation: legacy claim field is honoured when reservation is absent', () => {
  const reservation = { ucId: 'UC-301', developerId: 'alice' };
  // Server still emitting the v5.34.x shape { reachable, claim: {...} }.
  const decision = decideNativeReservation(reservation, {
    reachable: true,
    claim: { developer_id: 'alice' },
  });
  assert.equal(decision.allow, true);
  assert.equal(decision.reason, 'reservation-confirmed');
});

test('decideNativeReservation: legacy claim=null → treated as released', () => {
  const reservation = { ucId: 'UC-301', developerId: 'alice' };
  const decision = decideNativeReservation(reservation, {
    reachable: true,
    claim: null,
  });
  assert.equal(decision.allow, false);
  assert.equal(decision.reason, 'reservation-released');
});

test('decideNativeReservation: new reservation field wins over legacy claim field', () => {
  const reservation = { ucId: 'UC-301', developerId: 'alice' };
  // A mixed server response should prefer the new shape — `reservation:
  // null` here means released, regardless of what `claim` says.
  const decision = decideNativeReservation(reservation, {
    reachable: true,
    reservation: null,
    claim: { developer_id: 'alice' },
  });
  assert.equal(decision.allow, false);
  assert.equal(decision.reason, 'reservation-released');
});
