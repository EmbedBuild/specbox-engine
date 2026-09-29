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
	buildEngramInstallPlan,
	buildFreeformProjectSettings,
	stripLegacySpecboxEntry,
	FREEFORM_ROOT_RELATIVE,
	REMOTE_MCP_URL,
} = require(path.join(outDir, 'mcp.js'));

// UC-3901 AC-03 — SpecBox-MCP is written by the `specbox` CLI bundled in the
// extension (specbox-cli/, copied at compile time): Claude Code gets an http
// entry whose headers helper sends the token of this device.
async function specboxEntry() {
	const { configureClaudeCode, helperCommand } = await import('../specbox-cli/lib/claude.mjs');
	const calls = [];
	const run = (cmd, args) => {
		calls.push(args);
		return { status: 0, stdout: '', stderr: '', error: null };
	};
	const helper = helperCommand('/home/me/.specbox/bin/mcp-headers.mjs', '/usr/bin/node');
	configureClaudeCode({ mcpUrl: REMOTE_MCP_URL, helperCmd: helper, run, readFile: () => '{}' });
	const add = calls.find((a) => a[1] === 'add-json');
	return JSON.parse(add[3]);
}

test('AC-01: SpecBox MCP config points at the free hosted endpoint over http, with the headers helper', async () => {
	assert.equal(REMOTE_MCP_URL, 'https://mcp-specbox-engine.jpsdeveloper.com/mcp');
	assert.deepEqual(await specboxEntry(), {
		type: 'http',
		url: REMOTE_MCP_URL,
		headersHelper: '"/usr/bin/node" "/home/me/.specbox/bin/mcp-headers.mjs"',
	});
});

test('AC-02: remote config carries no local runtime (no python, uv, server.server)', async () => {
	const serialized = JSON.stringify(await specboxEntry()).toLowerCase();
	assert.ok(!serialized.includes('python'));
	assert.ok(!serialized.includes('"uv'));
	assert.ok(!serialized.includes('server.server'));
});

test('UC-3901 AC-03: the dead entries of older versions are removed from settings.local.json, nothing else', () => {
	const launcher = {
		mcpServers: {
			'SpecBox-MCP': {
				command: 'node',
				args: ['/Users/me/.vscode/extensions/embedbuild.specbox-engine-6.12.0/bin/mcp-launcher.mjs', '{}'],
				env: { SPECBOX_NATIVE_MCP_TOKEN: '${secretStorage:specbox.mcpToken}' },
			},
			engram: { command: 'engram', args: ['mcp'] },
		},
		specbox: { backend_type: 'freeform' },
	};
	const cleaned = stripLegacySpecboxEntry(launcher);
	assert.equal(cleaned.changed, true);
	assert.deepEqual(cleaned.settings, { mcpServers: { engram: { command: 'engram', args: ['mcp'] } }, specbox: { backend_type: 'freeform' } });

	const bridge = stripLegacySpecboxEntry({ mcpServers: { 'SpecBox-MCP': { command: 'npx', args: ['mcp-remote', REMOTE_MCP_URL] } } });
	assert.equal(bridge.changed, true);
	assert.deepEqual(bridge.settings, {});

	const custom = { mcpServers: { 'SpecBox-MCP': { command: 'my-own-wrapper', args: ['x'] } } };
	assert.deepEqual(stripLegacySpecboxEntry(custom), { changed: false, settings: custom });
	assert.equal(stripLegacySpecboxEntry({}).changed, false);
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

test('UC-662 AC-06: FreeForm reuses the SAME hosted MCP endpoint (no local mode)', async () => {
	const entry = await specboxEntry();
	assert.equal(entry.url, REMOTE_MCP_URL);
	assert.equal(buildFreeformProjectSettings('/abs/proj').env.SPECBOX_ENGINE_MCP_URL, entry.url);
	assert.ok(!JSON.stringify(entry).toLowerCase().includes('python'));
});

// UC-3801 AC-05 — FreeForm on the hosted MCP works in content-passing mode.
// The server never receives a directory: the settings the extension writes
// export SPECBOX_ENGINE_MCP_URL so hooks and skills pass the local items.json
// as `items_content` and write back what the tools return.

test('UC-3801 AC-05: FreeForm settings export SPECBOX_ENGINE_MCP_URL so the client passes content, not paths', () => {
	const s = buildFreeformProjectSettings('/abs/proj');
	assert.equal(s.env.SPECBOX_ENGINE_MCP_URL, REMOTE_MCP_URL);
});

test('UC-3801 AC-05: the hosted MCP server config never carries a tracking directory', async () => {
	const json = JSON.stringify(await specboxEntry());
	assert.ok(!json.includes('root_path'));
	assert.ok(!json.includes('doc/tracking'));
});

test('UC-3801 AC-05: FreeForm settings keep the absolute root for CLIENT-side hooks only (not for the server)', () => {
	const s = buildFreeformProjectSettings('/abs/proj');
	assert.equal(s.specbox.freeform_root_absolute, `/abs/proj/${FREEFORM_ROOT_RELATIVE}`);
	assert.ok(!('root_path' in s.specbox));
});
