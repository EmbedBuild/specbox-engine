// US-89 (UC-8903) — identity-schedule.ts: when the extension asks /api/whoami.
// Pure module (no `vscode`): tested over compiled out/identity-schedule.js with
// a fake clock that moves time and fires timers in order.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const {
	IdentityRefresher,
	IDENTITY_BACKGROUND_EVERY_MS,
	IDENTITY_FOCUS_MIN_GAP_MS,
} = require(path.resolve(__dirname, '..', 'out', 'identity-schedule.js'));

const MIN = 60_000;
const HOUR = 60 * MIN;

class FakeClock {
	constructor() { this.t = 0; this.timers = []; this.seq = 0; }
	now() { return this.t; }
	setTimeout(fn, ms) { const id = ++this.seq; this.timers.push({ id, at: this.t + ms, fn }); return id; }
	clearTimeout(id) { this.timers = this.timers.filter((x) => x.id !== id); }
	advance(ms) {
		const end = this.t + ms;
		for (;;) {
			this.timers.sort((a, b) => a.at - b.at);
			const next = this.timers[0];
			if (!next || next.at > end) { break; }
			this.timers.shift();
			this.t = next.at;
			next.fn();
		}
		this.t = end;
	}
}

function setup() {
	const clock = new FakeClock();
	const asks = [];
	const refresher = new IdentityRefresher(async () => { asks.push(clock.now()); }, clock);
	return { clock, asks, refresher };
}

test('the intervals are 30 minutes in the background and 5 minutes on focus', () => {
	assert.equal(IDENTITY_BACKGROUND_EVERY_MS, 30 * MIN);
	assert.equal(IDENTITY_FOCUS_MIN_GAP_MS, 5 * MIN);
});

test('AC-02: a window left alone asks at most 16 times in 8 hours (it was 480)', async () => {
	const { clock, asks, refresher } = setup();
	await refresher.refreshNow(); // activation
	clock.advance(8 * HOUR);
	const afterActivation = asks.filter((t) => t > 0);
	assert.equal(afterActivation.length, 16);
	assert.deepEqual(afterActivation.slice(0, 3), [30 * MIN, 60 * MIN, 90 * MIN]);
	refresher.dispose();
});

test('AC-01: activation, sign-in and renewal ask right away', async () => {
	const { clock, asks, refresher } = setup();
	await refresher.refreshNow(); // activation
	clock.advance(1000);
	await refresher.refreshNow(); // sign-in
	clock.advance(1000);
	await refresher.refreshNow(); // renewal
	assert.deepEqual(asks, [0, 1000, 2000]);
	refresher.dispose();
});

test('AC-01: focus asks only when 5 minutes went by, and moves the background ask', async () => {
	const { clock, asks, refresher } = setup();
	await refresher.refreshNow();
	clock.advance(4 * MIN);
	refresher.onFocus(); // 4 min: too soon
	assert.deepEqual(asks, [0]);
	clock.advance(1 * MIN);
	refresher.onFocus(); // 5 min: asks
	assert.deepEqual(asks, [0, 5 * MIN]);
	clock.advance(29 * MIN); // 34 min: the old 30-min ask was replaced
	assert.deepEqual(asks, [0, 5 * MIN]);
	clock.advance(1 * MIN); // 35 min = 5 + 30
	assert.deepEqual(asks, [0, 5 * MIN, 35 * MIN]);
	refresher.dispose();
});

test('AC-03: never more than 30 minutes between asks, whatever the focus does', async () => {
	const { clock, asks, refresher } = setup();
	await refresher.refreshNow();
	const focusAt = [3, 7, 40, 41, 50, 95, 180, 181, 300].map((m) => m * MIN);
	let t = 0;
	for (const at of focusAt) {
		clock.advance(at - t);
		t = at;
		refresher.onFocus();
	}
	clock.advance(6 * HOUR - t);
	for (let i = 1; i < asks.length; i++) {
		assert.ok(asks[i] - asks[i - 1] <= 30 * MIN, `gap of ${(asks[i] - asks[i - 1]) / MIN} min`);
		assert.ok(asks[i] - asks[i - 1] >= 5 * MIN, `asks ${(asks[i] - asks[i - 1]) / MIN} min apart`);
	}
	// A token revoked at any moment shows up at the next ask: at most 30 min later.
	const revokedAt = 123 * MIN;
	const next = asks.find((a) => a > revokedAt);
	assert.ok(next !== undefined && next - revokedAt <= 30 * MIN);
	refresher.dispose();
});

test('a failing ask does not stop the background schedule', async () => {
	const clock = new FakeClock();
	const asks = [];
	const refresher = new IdentityRefresher(async () => { asks.push(clock.now()); throw new Error('offline'); }, clock);
	await assert.rejects(refresher.refreshNow());
	clock.advance(HOUR);
	assert.deepEqual(asks, [0, 30 * MIN, 60 * MIN]);
	refresher.dispose();
});

test('after dispose nothing else is asked', async () => {
	const { clock, asks, refresher } = setup();
	await refresher.refreshNow();
	refresher.dispose();
	clock.advance(2 * HOUR);
	refresher.onFocus();
	await refresher.refreshNow();
	assert.deepEqual(asks, [0]);
});
