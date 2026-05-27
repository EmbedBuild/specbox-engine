// UC-VSCODE-WHOAMI — cloud-api.ts tests, zero-deps via node:test.
// Spins a local HTTPS-like HTTP server on 127.0.0.1 and points the SUT at it
// via the specbox.signInBaseUrl override.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import Module from 'node:module';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.resolve(__dirname, '..', 'out');
const require = createRequire(import.meta.url);

// cloud-api.ts switches to plain http.request when the URL is http:// — the
// tests point signInBaseUrl at http://127.0.0.1:<port>/vscode/issue-token so
// the SUT bypasses TLS automatically.
let configOverride = {};
const vscodeStub = {
	l10n: { t: (s) => s },
	workspace: {
		getConfiguration: () => ({ get: (key) => configOverride[key] }),
	},
};

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function (req, ...rest) {
	if (req === 'vscode') { return 'vscode-stub'; }
	return originalResolve.call(this, req, ...rest);
};
require.cache['vscode-stub'] = { id: 'vscode-stub', filename: 'vscode-stub', loaded: true, exports: vscodeStub };

const { fetchWhoami, _resetCacheForTests } = require(path.join(outDir, 'cloud-api.js'));

async function withServer(handler, fn) {
	const server = http.createServer(handler);
	await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
	const port = server.address().port;
	configOverride = { 'specbox.signInBaseUrl': `http://127.0.0.1:${port}/vscode/issue-token` };
	_resetCacheForTests();
	try {
		await fn(port);
	} finally {
		configOverride = {};
		await new Promise((resolve) => server.close(resolve));
	}
}

test('happy path: 200 JSON with handle returns parsed response', async () => {
	let receivedAuth = null;
	await withServer((req, res) => {
		receivedAuth = req.headers['authorization'];
		assert.equal(req.url, '/api/whoami');
		res.writeHead(200, { 'Content-Type': 'application/json' });
		res.end(JSON.stringify({ handle: 'jesusperezdeveloper', developer_id: 'dev-uuid', github_user_id: 12345 }));
	}, async () => {
		const r = await fetchWhoami('spbx_token_alpha');
		assert.ok(r);
		assert.equal(r.handle, 'jesusperezdeveloper');
		assert.equal(r.developer_id, 'dev-uuid');
		assert.equal(r.github_user_id, 12345);
		assert.equal(receivedAuth, 'Bearer spbx_token_alpha');
	});
});

test('SPA fallback (text/html) returns null without throwing', async () => {
	await withServer((req, res) => {
		res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
		res.end('<!doctype html><html></html>');
	}, async () => {
		const r = await fetchWhoami('spbx_anything');
		assert.equal(r, null);
	});
});

test('401 returns null (caller keeps signed-in flag but no handle)', async () => {
	await withServer((req, res) => {
		res.writeHead(401, { 'Content-Type': 'application/json' });
		res.end(JSON.stringify({ code: 'UNAUTHENTICATED', message: 'Invalid token' }));
	}, async () => {
		const r = await fetchWhoami('spbx_revoked');
		assert.equal(r, null);
	});
});

test('5xx returns null', async () => {
	await withServer((req, res) => {
		res.writeHead(503, { 'Content-Type': 'application/json' });
		res.end(JSON.stringify({ error: 'unavailable' }));
	}, async () => {
		const r = await fetchWhoami('spbx_t');
		assert.equal(r, null);
	});
});

test('JSON missing handle returns null', async () => {
	await withServer((req, res) => {
		res.writeHead(200, { 'Content-Type': 'application/json' });
		res.end(JSON.stringify({ developer_id: 'd', github_user_id: 1 }));
	}, async () => {
		const r = await fetchWhoami('spbx_t');
		assert.equal(r, null);
	});
});

test('malformed JSON returns null', async () => {
	await withServer((req, res) => {
		res.writeHead(200, { 'Content-Type': 'application/json' });
		res.end('not json at all');
	}, async () => {
		const r = await fetchWhoami('spbx_t');
		assert.equal(r, null);
	});
});

test('caches successful response across calls within TTL', async () => {
	let hits = 0;
	await withServer((req, res) => {
		hits++;
		res.writeHead(200, { 'Content-Type': 'application/json' });
		res.end(JSON.stringify({ handle: 'cached_handle', developer_id: 'd' }));
	}, async () => {
		const a = await fetchWhoami('spbx_cache');
		const b = await fetchWhoami('spbx_cache');
		const c = await fetchWhoami('spbx_cache');
		assert.equal(hits, 1);
		assert.equal(a.handle, 'cached_handle');
		assert.equal(b.handle, 'cached_handle');
		assert.equal(c.handle, 'cached_handle');
	});
});

test('different tokens are cached independently', async () => {
	let hits = 0;
	await withServer((req, res) => {
		hits++;
		res.writeHead(200, { 'Content-Type': 'application/json' });
		const handle = req.headers['authorization']?.includes('spbx_a') ? 'user_a' : 'user_b';
		res.end(JSON.stringify({ handle, developer_id: 'd' }));
	}, async () => {
		const a = await fetchWhoami('spbx_a');
		const b = await fetchWhoami('spbx_b');
		assert.equal(hits, 2);
		assert.equal(a.handle, 'user_a');
		assert.equal(b.handle, 'user_b');
	});
});

test('failures are NOT cached (next call retries)', async () => {
	let hits = 0;
	await withServer((req, res) => {
		hits++;
		if (hits === 1) {
			res.writeHead(200, { 'Content-Type': 'text/html' });
			res.end('<html></html>');
		} else {
			res.writeHead(200, { 'Content-Type': 'application/json' });
			res.end(JSON.stringify({ handle: 'retry_winner', developer_id: 'd' }));
		}
	}, async () => {
		const a = await fetchWhoami('spbx_retry');
		const b = await fetchWhoami('spbx_retry');
		assert.equal(hits, 2);
		assert.equal(a, null);
		assert.equal(b.handle, 'retry_winner');
	});
});
