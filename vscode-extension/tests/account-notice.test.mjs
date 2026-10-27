// UC-11013 — accountNotice + showAccountNoticeOnce over compiled out/account-notice.js, stubbing `vscode`.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import Module from 'node:module';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.resolve(__dirname, '..', 'out');
const require = createRequire(import.meta.url);

const shown = [];
const executed = [];
let answer;
const vscodeStub = {
	l10n: { t: (s, ...args) => s.replace(/\{(\d+)\}/g, (m, i) => (i in args ? String(args[i]) : m)) },
	window: {
		showWarningMessage: async (text, ...buttons) => { shown.push({ kind: 'warning', text, buttons }); return answer; },
		showErrorMessage: async (text, ...buttons) => { shown.push({ kind: 'error', text, buttons }); return answer; },
	},
	commands: { executeCommand: async (cmd) => { executed.push(cmd); } },
};
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function (req, ...rest) {
	if (req === 'vscode') { return 'vscode-stub'; }
	return originalResolve.call(this, req, ...rest);
};
require.cache['vscode-stub'] = { id: 'vscode-stub', filename: 'vscode-stub', loaded: true, exports: vscodeStub };

const { accountNotice, showAccountNoticeOnce, ACCOUNT_REQUIRED_FROM } = require(path.join(outDir, 'account-notice.js'));

const BEFORE = new Date('2026-10-28T10:00:00Z');
const AFTER = new Date('2026-10-30T00:00:01Z');

function fakeContext() {
	const store = new Map();
	return { globalState: { get: (k) => store.get(k), update: async (k, v) => { store.set(k, v); } } };
}

test('the date is the day the hosted MCP starts rejecting connections without a token', () => {
	assert.equal(ACCOUNT_REQUIRED_FROM, '2026-10-30');
});

test('MCP configured without an account: a warning with the date before the cut, an error from it', () => {
	const before = accountNotice({ mcpConfigured: true, signedIn: false, today: BEFORE });
	assert.equal(before.severity, 'warning');
	assert.match(before.label, /30 October 2026/);
	assert.match(before.text, /FreeForm the board stays in your repository/);

	const after = accountNotice({ mcpConfigured: true, signedIn: false, today: AFTER });
	assert.equal(after.severity, 'error');
	assert.match(after.text, /Since 30 October 2026/);
});

test('nothing to say when signed in or when the MCP is not configured', () => {
	assert.equal(accountNotice({ mcpConfigured: true, signedIn: true, today: BEFORE }), null);
	assert.equal(accountNotice({ mcpConfigured: false, signedIn: false, today: BEFORE }), null);
});

test('the startup reminder shows at most once a day and its button signs in', async () => {
	const context = fakeContext();
	answer = 'Sign in with GitHub';
	shown.length = 0; executed.length = 0;

	assert.equal(await showAccountNoticeOnce(context, { mcpConfigured: true, signedIn: false, today: BEFORE }), true);
	assert.equal(await showAccountNoticeOnce(context, { mcpConfigured: true, signedIn: false, today: BEFORE }), false, 'same day');
	assert.equal(shown.length, 1);
	assert.equal(shown[0].kind, 'warning');
	assert.deepEqual(shown[0].buttons, ['Sign in with GitHub', 'Later']);
	assert.deepEqual(executed, ['specbox.signIn']);

	answer = 'Later';
	assert.equal(await showAccountNoticeOnce(context, { mcpConfigured: true, signedIn: false, today: AFTER }), true, 'next day');
	assert.equal(shown[1].kind, 'error');
	assert.deepEqual(executed, ['specbox.signIn'], '«Later» does nothing');
});

test('no reminder when signed in', async () => {
	assert.equal(await showAccountNoticeOnce(fakeContext(), { mcpConfigured: true, signedIn: true, today: BEFORE }), false);
});
