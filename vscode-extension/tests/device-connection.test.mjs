// UC-3901 AC-03 / UC-3904 — the extension keeps this computer connected with
// the bundled `specbox` CLI: device sign-in URL, credential from whoami, the
// real CLI bridge, startup adoption / renewal and the status bar identity.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import Module from 'node:module';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.resolve(__dirname, '..', 'out');
const require = createRequire(import.meta.url);

let configOverride = {};
const vscodeStub = {
	l10n: { t: (s, ...args) => s.replace(/\{(\d+)\}/g, (_, i) => String(args[Number(i)])) },
	workspace: { getConfiguration: () => ({ get: (key) => configOverride[key] }) },
	window: {},
	env: { language: 'es' },
	Uri: { parse: (s) => s },
};
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function (req, ...rest) {
	if (req === 'vscode') { return 'vscode-stub'; }
	return originalResolve.call(this, req, ...rest);
};
require.cache['vscode-stub'] = { id: 'vscode-stub', filename: 'vscode-stub', loaded: true, exports: vscodeStub };

const { buildSignInUrl } = require(path.join(outDir, 'oauth.js'));
const { SpecboxCli, cloudApiBase, credentialFromWhoami, parseCliJson } = require(path.join(outDir, 'specbox-cli.js'));
const { ensureDeviceConnection, syncRenewal } = require(path.join(outDir, 'device-connection.js'));
const { identityTooltipLines } = require(path.join(outDir, 'statusbar.js'));
const { whoamiStatus, _resetCacheForTests } = require(path.join(outDir, 'cloud-api.js'));
const { howToConnectUrl } = require(path.join(outDir, 'constants.js'));

const DEVICE = { device_id: 'a'.repeat(64), host: 'MacBook Pro', client: 'claude-code' };

// ── Sign-in URL and credential ────────────────────────────────────────

test('AC-01: the sign-in URL carries the device so the cloud issues a device token', () => {
	const url = new URL(buildSignInUrl(4321, 'f'.repeat(64), undefined, DEVICE));
	assert.equal(url.searchParams.get('device_id'), DEVICE.device_id);
	assert.equal(url.searchParams.get('host'), 'MacBook Pro');
	assert.equal(url.searchParams.get('client'), 'claude-code');
	assert.equal(url.searchParams.get('return_to'), 'http://127.0.0.1:4321/callback');
	assert.equal(new URL(buildSignInUrl(4321, 'x')).searchParams.get('device_id'), null);
});

test('the credential for the secure store comes from the token and what whoami says about its device', () => {
	const me = {
		handle: 'jesusperezdeveloper',
		developer_id: 'jesus',
		device: { token_id: 't1', device_name: 'Jesús · Mac · Claude Code', client: 'claude-code', client_label: 'Claude Code', expires_at: '2026-12-28T10:00:00.000Z', renew_after: '2026-12-14T10:00:00.000Z' },
	};
	assert.deepEqual(credentialFromWhoami('spbx_x', me, DEVICE, 'https://api.example/api'), {
		token: 'spbx_x',
		token_id: 't1',
		expires_at: '2026-12-28T10:00:00.000Z',
		renew_after: '2026-12-14T10:00:00.000Z',
		device_id: DEVICE.device_id,
		device_name: 'Jesús · Mac · Claude Code',
		client: 'claude-code',
		developer: { developer_id: 'jesus', display_name: 'jesusperezdeveloper', handle: 'jesusperezdeveloper' },
		cloud_api: 'https://api.example/api',
	});
});

test('the CLI talks to the production API unless the E2E override points at a mock cloud', () => {
	assert.equal(cloudApiBase(undefined), 'https://api-cloud.specbox.build/api');
	assert.equal(cloudApiBase('http://127.0.0.1:9999/vscode/issue-token'), 'http://127.0.0.1:9999/api');
	assert.equal(cloudApiBase('not a url'), 'https://api-cloud.specbox.build/api');
	assert.deepEqual(parseCliJson('warning line\n{"ok":true}\n'), { ok: true });
	assert.equal(parseCliJson('no json'), null);
});

// ── The real bundled CLI ──────────────────────────────────────────────

test('the bridge runs the bundled CLI with the system Node and parses its JSON', async () => {
	const cli = new SpecboxCli(path.resolve(__dirname, '..'), {
		cloudApi: 'https://api.invalid/api',
		mcpUrl: 'https://probe.invalid/mcp',
		nodeFinder: async () => process.execPath,
		env: { ...process.env, SPECBOX_HOME: mkdtempSync(path.join(tmpdir(), 'specbox-ext-')) },
	});
	const device = await cli.call('_device');
	assert.match(device.device_id, /^[0-9a-f]{64}$/);
	assert.equal(device.client, 'claude-code');
	const status = await cli.call('_status');
	assert.equal(status.connected, false);
	assert.deepEqual(await cli.call('_nope'), { ok: false, reason: 'unknown_command' });
});

test('without Node the bridge answers null instead of failing', async () => {
	const cli = new SpecboxCli('/nowhere', { cloudApi: 'x', mcpUrl: 'https://x/mcp', nodeFinder: async () => null });
	assert.equal(await cli.call('_status'), null);
});

// ── Startup: adopt, renew, restore ────────────────────────────────────

function fakeCli(answers) {
	const calls = [];
	return {
		calls,
		async call(command, input) {
			calls.push({ command, input });
			const answer = answers[command];
			return typeof answer === 'function' ? answer(input) : answer ?? null;
		},
	};
}

function fakeSecrets(initial) {
	let token = initial;
	return {
		get value() { return token; },
		async getToken() { return token; },
		async storeToken(t) { token = t; },
	};
}

test('UC-3901 AC-03: after an update, the token kept by an older version becomes a device token', async () => {
	let cleaned = 0;
	const cli = fakeCli({
		_status: { connected: false, store: 'keychain', claude_helper: false },
		_adopt: { ok: true, token: 'spbx_dispositivo', claude: { ok: true } },
	});
	const secrets = fakeSecrets('spbx_anterior');
	const report = await ensureDeviceConnection(cli, secrets, () => { cleaned += 1; });
	assert.equal(report.state, 'adopted');
	assert.deepEqual(cli.calls.find((c) => c.command === '_adopt').input, { token: 'spbx_anterior', issued_via: 'vscode' });
	assert.equal(secrets.value, 'spbx_dispositivo');
	assert.equal(cleaned, 1);
});

test('already connected: renews if due, syncs SecretStorage and restores the Claude Code helper', async () => {
	const cli = fakeCli({
		_status: { connected: true, store: 'keychain', claude_helper: false },
		_renew: { connected: true, renewed: true, token: 'spbx_nuevo' },
		_configure: { ok: true, claude: { ok: true } },
	});
	const secrets = fakeSecrets('spbx_viejo');
	const report = await ensureDeviceConnection(cli, secrets);
	assert.equal(report.state, 'connected');
	assert.equal(secrets.value, 'spbx_nuevo');
	assert.ok(cli.calls.some((c) => c.command === '_configure'));
});

test('connected from the terminal (specbox login): the extension picks the same token up', async () => {
	const cli = fakeCli({
		_status: { connected: true, store: 'keychain', claude_helper: true },
		_renew: { connected: true, renewed: false, token: 'spbx_de_la_terminal' },
	});
	const secrets = fakeSecrets(undefined);
	assert.equal((await ensureDeviceConnection(cli, secrets)).state, 'connected');
	assert.equal(secrets.value, 'spbx_de_la_terminal');
	assert.ok(!cli.calls.some((c) => c.command === '_configure'));
});

test('signed out, no Node or a dead token: nothing is invented', async () => {
	assert.equal((await ensureDeviceConnection(fakeCli({ _status: { connected: false } }), fakeSecrets(undefined))).state, 'signed_out');
	assert.equal((await ensureDeviceConnection(fakeCli({}), fakeSecrets('x'))).state, 'no_node');
	const dead = await ensureDeviceConnection(
		fakeCli({ _status: { connected: false }, _adopt: { ok: false, reason: 'invalid_token' } }),
		fakeSecrets('spbx_revocado'),
	);
	assert.deepEqual(dead, { state: 'adopt_failed', reason: 'invalid_token' });
});

test('AC-03: the daily sync stores the renewed token and reports whether it changed', async () => {
	const secrets = fakeSecrets('spbx_a');
	assert.equal(await syncRenewal(fakeCli({ _renew: { connected: true, token: 'spbx_a' } }), secrets), false);
	assert.equal(await syncRenewal(fakeCli({ _renew: { connected: true, token: 'spbx_b' } }), secrets), true);
	assert.equal(secrets.value, 'spbx_b');
	assert.equal(await syncRenewal(fakeCli({ _renew: { connected: false } }), secrets), false);
});

// ── AC-06 / AC-07 ─────────────────────────────────────────────────────

test('AC-06: the status bar shows the person, the device, the expiry and that it renews itself', () => {
	const lines = identityTooltipLines(
		{ handle: 'jesus', deviceName: 'Jesús · Mac · Claude Code', expiresAt: '2026-12-28T10:00:00.000Z', renews: true },
		'es',
	);
	assert.equal(lines[0], 'Connected as @jesus');
	assert.equal(lines[1], 'Device: Jesús · Mac · Claude Code');
	assert.match(lines[2], /^Token expires on .*2026 — it renews itself$/);
	assert.match(identityTooltipLines({ handle: 'x', renews: false }, 'es')[1], /without expiry/);
	assert.equal(howToConnectUrl('es'), 'https://cloud.specbox.build/como-se-conecta');
	assert.equal(howToConnectUrl('en-US'), 'https://cloud.specbox.build/how-to-connect');
});

test('AC-07: whoami tells an ended connection (401) apart from an unreachable cloud', async () => {
	const server = http.createServer((req, res) => {
		const auth = req.headers.authorization ?? '';
		if (auth.endsWith('revocado')) {
			res.writeHead(401, { 'content-type': 'application/json' });
			res.end('{"code":"invalid_token"}');
		} else if (auth.endsWith('caido')) {
			res.writeHead(502, { 'content-type': 'application/json' });
			res.end('{}');
		} else {
			res.writeHead(200, { 'content-type': 'application/json' });
			res.end(JSON.stringify({ handle: 'jesus', developer_id: 'jesus', device: { token_id: 't', device_name: 'Mac', client: 'claude-code', client_label: 'Claude Code', expires_at: null, renew_after: null } }));
		}
	});
	await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
	configOverride = { 'specbox.signInBaseUrl': `http://127.0.0.1:${server.address().port}/vscode/issue-token` };
	_resetCacheForTests();
	try {
		assert.deepEqual(await whoamiStatus('spbx_revocado'), { status: 'unauthorized' });
		assert.deepEqual(await whoamiStatus('spbx_caido'), { status: 'unavailable' });
		const ok = await whoamiStatus('spbx_bueno');
		assert.equal(ok.status, 'ok');
		assert.equal(ok.me.device.device_name, 'Mac');
	} finally {
		configOverride = {};
		await new Promise((resolve) => server.close(resolve));
	}
});
