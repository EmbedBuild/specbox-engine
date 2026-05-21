/**
 * Tests for lib/native-claim-revalidate.mjs (UC-304, AC-21 / AC-22).
 *
 * Pure-logic tests, no I/O — matches the node:assert convention of the other
 * hook tests in this directory.
 */

import assert from 'node:assert/strict';

import { decideNativeClaim } from '../../.claude/hooks/lib/native-claim-revalidate.mjs';

const CLAIM = { ucId: 'UC-301', developerId: 'alice' };

function testNoClaimIsNoOp() {
  const d = decideNativeClaim(null, { reachable: true, claim: null });
  assert.equal(d.allow, true);
  assert.equal(d.reason, 'no-native-claim');
}

function testOfflineTrustsCache() {
  // AC-21: unreachable MCP → trust the cached claim.
  assert.equal(decideNativeClaim(CLAIM, { reachable: false }).allow, true);
  assert.equal(decideNativeClaim(CLAIM, null).allow, true);
  assert.equal(
    decideNativeClaim(CLAIM, { reachable: false }).reason,
    'offline-cache-trusted',
  );
}

function testOnlineClaimConfirmedAllows() {
  const d = decideNativeClaim(CLAIM, {
    reachable: true,
    claim: { developer_id: 'alice' },
  });
  assert.equal(d.allow, true);
  assert.equal(d.reason, 'claim-confirmed');
}

function testOnlineClaimReleasedBlocks() {
  // AC-22: claim gone remotely → block.
  const d = decideNativeClaim(CLAIM, { reachable: true, claim: null });
  assert.equal(d.allow, false);
  assert.equal(d.reason, 'claim-released');
  assert.equal(d.conflict.expected, 'alice');
  assert.equal(d.conflict.actual, null);
}

function testOnlineClaimTakenOverBlocks() {
  // AC-22: claim now belongs to another dev → block, name the conflict.
  const d = decideNativeClaim(CLAIM, {
    reachable: true,
    claim: { developer_id: 'bob' },
  });
  assert.equal(d.allow, false);
  assert.equal(d.reason, 'claim-taken-over');
  assert.equal(d.conflict.expected, 'alice');
  assert.equal(d.conflict.actual, 'bob');
}

const tests = [
  testNoClaimIsNoOp,
  testOfflineTrustsCache,
  testOnlineClaimConfirmedAllows,
  testOnlineClaimReleasedBlocks,
  testOnlineClaimTakenOverBlocks,
];

let failed = 0;
for (const t of tests) {
  try {
    t();
    console.log(`  ok ${t.name}`);
  } catch (err) {
    failed++;
    console.error(`  FAIL ${t.name}: ${err.message}`);
  }
}

if (failed > 0) {
  console.error(`\n${failed} of ${tests.length} tests failed`);
  process.exit(1);
}
console.log(`\n${tests.length} tests passed`);
