// US-VSCODE-ZERO-PYTHON / UC-005 — MCP configuration is remote-only and Engram
// installs via Homebrew (never pip). Pure-function tests over the compiled
// out/mcp.js, stubbing `vscode` the same way skill-card.test.mjs does.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import Module from 'node:module';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.resolve(__dirname, '..', 'out');
const require = createRequire(import.meta.url);

const vscodeStub = {
	l10n: { t: (s) => s },
	window: {},
	env: {},
	Uri: { parse: (s) => s },
};
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function (req, ...rest) {
	if (req === 'vscode') { return 'vscode-stub'; }
	return originalResolve.call(this, req, ...rest);
};
require.cache['vscode-stub'] = { id: 'vscode-stub', filename: 'vscode-stub', loaded: true, exports: vscodeStub };

const {
	buildRemoteServerConfig,
	buildEngramInstallPlan,
	buildFreeformProjectSettings,
	FREEFORM_ROOT_RELATIVE,
	REMOTE_MCP_URL,
} = require(path.join(outDir, 'mcp.js'));

test('AC-01: SpecBox MCP config points at the free hosted remote endpoint via npx mcp-remote', () => {
	const cfg = buildRemoteServerConfig();
	assert.equal(cfg.command, 'npx');
	assert.deepEqual(cfg.args, ['mcp-remote', 'https://mcp-specbox-engine.jpsdeveloper.com/mcp']);
	assert.equal(REMOTE_MCP_URL, 'https://mcp-specbox-engine.jpsdeveloper.com/mcp');
});

test('AC-02: remote config carries no local runtime (no python, uv, server.server)', () => {
	const serialized = JSON.stringify(buildRemoteServerConfig()).toLowerCase();
	assert.ok(!serialized.includes('python'));
	assert.ok(!serialized.includes('uv'));
	assert.ok(!serialized.includes('server.server'));
});

test('AC-03: Engram install uses Homebrew when brew is present, not pip/pipx', () => {
	const plan = buildEngramInstallPlan(true);
	assert.equal(plan.method, 'brew');
	assert.equal(plan.command, 'brew install gentleman-programming/tap/engram');
	const cmd = plan.command.toLowerCase();
	assert.ok(!cmd.includes('pip'));
});

test('AC-04: without brew, Engram falls back to a manual binary install (never pip)', () => {
	const plan = buildEngramInstallPlan(false);
	assert.equal(plan.method, 'manual');
	assert.equal(plan.command, null);
	assert.match(plan.manualUrl, /github\.com\/Gentleman-Programming\/engram/);
	assert.ok(!JSON.stringify(plan).toLowerCase().includes('pip'));
});

// UC-662 AC-06 — FreeForm first-class onboarding, no Python.

test('UC-662 AC-06: buildFreeformProjectSettings marks the project freeform with an absolute root', () => {
	const s = buildFreeformProjectSettings('/Users/me/myproject');
	assert.equal(s.specbox.backend_type, 'freeform');
	assert.equal(s.specbox.freeform_root_absolute, `/Users/me/myproject/${FREEFORM_ROOT_RELATIVE}`);
});

test('UC-662 AC-06: FreeForm settings contain NO python/uv/local-mode references', () => {
	const json = JSON.stringify(buildFreeformProjectSettings('/abs/proj')).toLowerCase();
	for (const forbidden of ['python', 'pip', 'venv', 'local', 'localhost', '127.0.0.1', 'server.server']) {
		assert.ok(!json.includes(forbidden), `settings should not mention ${forbidden}: ${json}`);
	}
});

test('UC-662 AC-06: buildFreeformProjectSettings rejects a relative root (v5.29 BLOCKER)', () => {
	assert.throws(() => buildFreeformProjectSettings('relative/proj'), /must be absolute/);
});

test('UC-662 AC-06: FreeForm reuses the SAME hosted MCP endpoint (no local mode)', () => {
	const cfg = buildRemoteServerConfig();
	assert.ok(cfg.args.includes(REMOTE_MCP_URL));
	assert.ok(!JSON.stringify(cfg).toLowerCase().includes('python'));
});
