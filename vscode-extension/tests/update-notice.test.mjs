// UC-9605 (US-96) — el aviso tras actualizar no contradice el panel y nombra el comando real.
//
// AC-01 · El aviso y la fila «MCP SpecBox» del panel usan la misma comprobación: con el MCP de SpecBox
//         configurado en Claude Code, el aviso no dice que falte terminar el onboarding.
// AC-02 · Cuando falta, el aviso nombra el comando exacto en el idioma de VSCode («SpecBox: Inicializar
//         Proyecto» o «SpecBox: Onboard Project») y ofrece un botón que lo ejecuta.
// AC-03 · El aviso solo habla de «este proyecto» cuando comprueba el proyecto abierto; si comprueba la
//         configuración global, lo dice así.
//
// Origen: con el MCP configurado en ~/.claude.json (donde lo deja `specbox login`), el panel decía «MCP
// SpecBox: Configured» y el aviso, que solo leía ~/.claude/settings.local.json, «this project has not
// finished onboarding yet» y «Run the SpecBox setup wizard» (no hay ningún comando con ese nombre).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import Module from 'node:module';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(import.meta.url);

const home = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'notice-home-')));
process.env.HOME = home;
process.env.USERPROFILE = home;

const shown = { info: [], commands: [] };
let answer;
const vscodeStub = {
	l10n: { t: (s, ...args) => (args.length ? s.replace(/\{(\d+)\}/g, (_, i) => args[i]) : s) },
	env: { language: 'en' },
	window: {
		showInformationMessage: (msg, ...buttons) => {
			shown.info.push({ msg, buttons });
			return Promise.resolve(buttons.includes(answer) ? answer : undefined);
		},
		showWarningMessage: () => Promise.resolve(undefined),
		showErrorMessage: () => Promise.resolve(undefined),
		withProgress: (_o, fn) => fn({ report: () => {} }),
	},
	workspace: { getConfiguration: () => ({ get: () => undefined }), workspaceFolders: [] },
	commands: { executeCommand: (c) => { shown.commands.push(c); return Promise.resolve(); } },
	ProgressLocation: { Notification: 15 },
};
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function (req, ...rest) {
	if (req === 'vscode') { return 'vscode-stub'; }
	return originalResolve.call(this, req, ...rest);
};
require.cache['vscode-stub'] = { id: 'vscode-stub', filename: 'vscode-stub', loaded: true, exports: vscodeStub };

const { HealthChecker } = require(path.join(root, 'out', 'health.js'));
const mig = require(path.join(root, 'out', 'migration.js'));
const { ExtensionUpdater } = require(path.join(root, 'out', 'updater.js'));

const en = JSON.parse(fs.readFileSync(path.join(root, 'l10n', 'bundle.l10n.json'), 'utf-8'));
const es = JSON.parse(fs.readFileSync(path.join(root, 'l10n', 'bundle.l10n.es.json'), 'utf-8'));
const nlsEn = JSON.parse(fs.readFileSync(path.join(root, 'package.nls.json'), 'utf-8'));
const nlsEs = JSON.parse(fs.readFileSync(path.join(root, 'package.nls.es.json'), 'utf-8'));

function reset({ claudeJson } = {}) {
	shown.info = []; shown.commands = []; answer = undefined;
	fs.rmSync(path.join(home, '.claude'), { recursive: true, force: true });
	fs.rmSync(path.join(home, '.claude.json'), { force: true });
	if (claudeJson) { fs.writeFileSync(path.join(home, '.claude.json'), JSON.stringify(claudeJson)); }
}

/** Una copia del engine en la misma versión que la extensión: el flujo va directo al aviso. */
function engineDir() {
	const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'notice-engine-'));
	fs.writeFileSync(path.join(dir, 'ENGINE_VERSION.yaml'), 'version: 6.25.0\n');
	return dir;
}
const offline = async () => ({ code: 1, stdout: '', stderr: 'offline' });
const runUpdate = () => new ExtensionUpdater('6.25.0', offline).runUpdateFlow(engineDir());

const HOSTED = { mcpServers: { 'SpecBox-MCP': { type: 'http', url: 'https://mcp.specbox.build/mcp', headersHelper: '~/.specbox/bin/mcp-headers.mjs' } } };

test('AC-01 · con el MCP en ~/.claude.json, el panel dice Configured y el aviso no habla de onboarding', async () => {
	reset({ claudeJson: HOSTED });
	assert.equal(new HealthChecker().checkMcpConfigured('specbox-engine').configured, true, 'fila «MCP SpecBox: Configured»');
	assert.equal(mig.detectClientConfigCase(null, { mcpConfigured: true }), 'hosted_mcp_ok');

	await runUpdate();
	assert.equal(shown.info.length, 1);
	assert.equal(shown.info[0].msg, 'Updated to v6.25.0 — no changes needed for your configuration.');
	assert.deepEqual(shown.info[0].buttons, []);
});

test('AC-01 · sin el MCP en ningún sitio, el panel dice Not configured y el aviso pide terminar', async () => {
	reset();
	assert.equal(new HealthChecker().checkMcpConfigured('specbox-engine').configured, false);
	await runUpdate();
	assert.match(shown.info[0].msg, /the SpecBox MCP server is not configured in Claude Code yet/);
});

test('AC-01 · la detección sigue igual sin la comprobación (los 5 casos de UC-664 no cambian)', () => {
	assert.equal(mig.detectClientConfigCase(null), 'onboarding_incomplete');
	assert.equal(mig.detectClientConfigCase({ specbox: { backend_type: 'freeform' } }, { mcpConfigured: true }), 'freeform_remote_ok');
	assert.equal(mig.detectClientConfigCase({ specbox: { backend_type: 'freeform' } }), 'onboarding_incomplete');
	assert.equal(mig.detectClientConfigCase({ mcpServers: { 'SpecBox-MCP': { command: 'uv', args: ['run'] } } }, { mcpConfigured: true }), 'freeform_local_obsolete');
});

test('AC-02 · el aviso nombra el comando real y su botón lo ejecuta', async () => {
	reset();
	answer = 'SpecBox: Onboard Project';
	await runUpdate();
	const { msg, buttons } = shown.info[0];
	assert.match(msg, /Run "SpecBox: Onboard Project" to finish setting it up\./);
	assert.doesNotMatch(msg, /setup wizard/);
	assert.deepEqual(buttons, ['SpecBox: Onboard Project']);
	assert.deepEqual(shown.commands, ['specbox.onboard']);
});

test('AC-02 · en cada idioma, el nombre es el título del comando que enseña VSCode', () => {
	assert.equal(en['SpecBox: Onboard Project'], nlsEn['command.onboard.title']);
	assert.equal(es['SpecBox: Onboard Project'], nlsEs['command.onboard.title']);
	assert.ok(es['Run "SpecBox: Onboard Project" to finish setting it up.'].includes(`«${nlsEs['command.onboard.title']}»`));
	assert.ok(en['Run "SpecBox: Onboard Project" to finish setting it up.'].includes(`"${nlsEn['command.onboard.title']}"`));
});

test('AC-03 · el aviso dice que comprueba la configuración global y no habla de «este proyecto»', () => {
	const s = mig.buildMigrationSummary(mig.planMigration('onboarding_incomplete', '6.25.0'), { toVersion: '6.25.0', backupPath: null });
	const text = mig.renderSummaryText(s);
	assert.match(text, /global configuration/);
	assert.doesNotMatch(text, /this project/i);
	for (const key of ['SpecBox updated to v{0}.', s.migrated, s.action]) {
		assert.ok(key in en, key);
		assert.doesNotMatch(es[key], /este proyecto/i);
	}
	assert.match(es[s.migrated], /configuración global/);
});

test('el caso que migra conserva su botón «Revert»', () => {
	const s = mig.buildMigrationSummary(mig.planMigration('freeform_local_obsolete', '6.25.0'), { toVersion: '6.25.0', backupPath: '/x.bak' });
	assert.equal(s.button, 'revert');
});
