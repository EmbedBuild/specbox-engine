// US-VSCODE-PREREQ-GATE / UC-706 — evaluatePrerequisites + buildPrereqWarning.
// Pure-function tests over compiled out/prerequisites.js, stubbing `vscode`.

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
	commands: {},
	Uri: { parse: (s) => s },
};
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function (req, ...rest) {
	if (req === 'vscode') { return 'vscode-stub'; }
	return originalResolve.call(this, req, ...rest);
};
require.cache['vscode-stub'] = { id: 'vscode-stub', filename: 'vscode-stub', loaded: true, exports: vscodeStub };

const { evaluatePrerequisites, buildPrereqWarning } = require(path.join(outDir, 'prerequisites.js'));

const allOk = () => ({
	node: { ok: true },
	claudeCode: { ok: true },
	engram: { ok: true },
	mcpSpecbox: { configured: true },
	mcpEngram: { configured: true },
});

test('AC-01: all critical prerequisites present → ready, empty missing', () => {
	const r = evaluatePrerequisites(allOk());
	assert.equal(r.verdict, 'ready');
	assert.deepEqual(r.missing, []);
});

test('AC-01: each missing critical prerequisite → degraded + labelled in missing', () => {
	const cases = [
		['claudeCode', 'Claude Code', (h) => { h.claudeCode.ok = false; }],
		['engram', 'Engram', (h) => { h.engram.ok = false; }],
		['node', 'Node.js', (h) => { h.node.ok = false; }],
		['mcpSpecbox', 'MCP SpecBox server', (h) => { h.mcpSpecbox.configured = false; }],
		['mcpEngram', 'MCP Engram server', (h) => { h.mcpEngram.configured = false; }],
	];
	for (const [, label, mutate] of cases) {
		const h = allOk();
		mutate(h);
		const r = evaluatePrerequisites(h);
		assert.equal(r.verdict, 'degraded', `${label} missing should be degraded`);
		assert.ok(r.missing.includes(label), `missing should include "${label}"`);
	}
});

test('AC-01: multiple missing → all labelled', () => {
	const h = allOk();
	h.claudeCode.ok = false;
	h.mcpEngram.configured = false;
	const r = evaluatePrerequisites(h);
	assert.equal(r.verdict, 'degraded');
	assert.deepEqual(r.missing, ['Claude Code', 'MCP Engram server']);
});

test('AC-02: GGA is not part of the input and never causes degraded', () => {
	// The input type has no gga field at all; an all-ok env is ready regardless.
	const r = evaluatePrerequisites(allOk());
	assert.equal(r.verdict, 'ready');
});

test('AC-03: warning text names the missing items and warns about breakage', () => {
	const msg = buildPrereqWarning(['Claude Code', 'Engram']);
	assert.match(msg, /may not work correctly/i);
	assert.match(msg, /Claude Code/);
	assert.match(msg, /Engram/);
});
