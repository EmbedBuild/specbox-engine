// UC-7202 (US-72) — «Comprobar salud» avisa si un hook configurado no existe.
//
// AC-01 · Hooks sale en rojo y lista cada hook que el .claude/settings.json del proyecto abierto
//         referencia y no existe en disco; con todos presentes, en verde con su número.
//
// specbox_cloud configuraba 14 hooks sin tener sus ficheros: fallaban en cada uso y el diagnóstico,
// que solo contaba los hooks globales, decía que todo estaba bien.
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

const vscodeStub = {
	l10n: { t: (s, ...args) => (args.length ? s.replace(/\{(\d+)\}/g, (_, i) => args[i]) : s) },
	env: { language: 'en' },
	window: { activeColorTheme: undefined },
	workspace: { getConfiguration: () => ({ get: () => undefined }), workspaceFolders: [] },
	ViewColumn: { One: 1 },
};
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function (req, ...rest) {
	if (req === 'vscode') { return 'vscode-stub'; }
	return originalResolve.call(this, req, ...rest);
};
require.cache['vscode-stub'] = { id: 'vscode-stub', filename: 'vscode-stub', loaded: true, exports: vscodeStub };

const { missingHookScripts, healthRows, renderHealthReport, HealthChecker } = require(path.join(root, 'out', 'health.js'));

/** Un proyecto temporal con los hooks dados en .claude/hooks y el settings.json dado. */
function project(hookFiles, settings) {
	const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'health-hooks-'));
	fs.mkdirSync(path.join(dir, '.claude', 'hooks'), { recursive: true });
	for (const f of hookFiles) { fs.writeFileSync(path.join(dir, '.claude', 'hooks', f), ''); }
	fs.writeFileSync(path.join(dir, '.claude', 'settings.json'), JSON.stringify(settings));
	return dir;
}

const cmd = (command) => ({ type: 'command', command });
const SETTINGS = {
	hooks: {
		PreToolUse: [{ matcher: 'Write', hooks: [cmd('node .claude/hooks/present.mjs'), cmd('node .claude/hooks/gone.mjs')] }],
		PostToolUse: [{ matcher: 'Bash', hooks: [cmd('node "$CLAUDE_PROJECT_DIR"/.claude/hooks/present.mjs'), cmd('npx some-linter --fix')] }],
		Stop: [{ hooks: [cmd('node ~/.claude/hooks/global-only.mjs')] }],
	},
};

const BASE = {
	engineInstalled: true, engineVersion: '6.19.0', enginePath: '/home/ana/.specbox/specbox-engine',
	node: { ok: true, version: 'v22.1.0' }, claudeCode: { ok: true, version: '2.1.0' },
	engram: { ok: true, version: '1.9.0' }, skills: { installed: ['prd'], missing: [] },
	hooks: { ok: true, count: 28, broken: [] }, settings: { ok: true },
	mcpSpecbox: { configured: true }, mcpEngram: { configured: true }, gga: { ok: true, version: '1.0.0' },
};
const hooksRow = (r) => healthRows(r).find((x) => x.component === 'Hooks');

test('missingHookScripts devuelve los scripts que el proyecto no tiene, resueltos como Claude Code', () => {
	const dir = project(['present.mjs'], SETTINGS);
	const home = fs.mkdtempSync(path.join(os.tmpdir(), 'health-home-'));
	try {
		assert.deepEqual(missingHookScripts(SETTINGS, dir, home).sort(), ['.claude/hooks/gone.mjs', '~/.claude/hooks/global-only.mjs']);
		fs.mkdirSync(path.join(home, '.claude', 'hooks'), { recursive: true });
		fs.writeFileSync(path.join(home, '.claude', 'hooks', 'global-only.mjs'), '');
		assert.deepEqual(missingHookScripts(SETTINGS, dir, home), ['.claude/hooks/gone.mjs'], '~ se resuelve contra el home');
		assert.deepEqual(missingHookScripts({}, dir, home), [], 'sin hooks no falta nada');
		assert.deepEqual(missingHookScripts(null, dir, home), []);
	} finally {
		fs.rmSync(dir, { recursive: true, force: true });
		fs.rmSync(home, { recursive: true, force: true });
	}
});

test('AC-01 · con hooks que no existen, Hooks sale pendiente y los nombra uno a uno', () => {
	const broken = [
		{ project: 'specbox_cloud', source: '.claude/settings.json', script: '.claude/hooks/spec-guard.mjs' },
		{ project: 'specbox_cloud', source: '.claude/settings.json', script: '.claude/hooks/quality-first-guard.mjs' },
	];
	const r = { ...BASE, hooks: { ok: false, count: 28, broken } };
	const row = hooksRow(r);
	assert.equal(row.state, 'pending');
	assert.match(row.detail, /^2 configured but missing: /);
	for (const b of broken) { assert.ok(row.detail.includes(`${b.project}/${b.script} (${b.source})`), b.script); }
	const html = renderHealthReport(r);
	assert.match(html, /1 pending/);
	assert.ok(html.includes('specbox_cloud/.claude/hooks/spec-guard.mjs'));
});

test('AC-01 · con todos los hooks presentes, Hooks sale en verde con su número', () => {
	const row = hooksRow(BASE);
	assert.equal(row.state, 'done');
	assert.equal(row.detail, '28 installed');
	// Un resultado anterior a UC-7202 (sin broken) se sigue pintando igual.
	assert.equal(hooksRow({ ...BASE, hooks: { ok: true, count: 30 } }).detail, '30 installed');
});

test('AC-01 · el diagnóstico real lee el settings.json del proyecto abierto', () => {
	const settings = { hooks: { PreToolUse: [{ matcher: 'Write', hooks: [cmd('node .claude/hooks/present.mjs'), cmd('node .claude/hooks/gone.mjs')] }] } };
	const dir = project(['present.mjs'], settings);
	vscodeStub.workspace.workspaceFolders = [{ name: 'demo', uri: { fsPath: dir } }];
	try {
		const hooks = new HealthChecker().checkHooks();
		// Solo lo del proyecto: el settings global de quien corre la prueba también se revisa, pero varía.
		const fromProject = hooks.broken.filter((b) => b.source === '.claude/settings.json');
		assert.deepEqual(fromProject, [{ project: 'demo', source: '.claude/settings.json', script: '.claude/hooks/gone.mjs' }]);
		assert.equal(hooks.ok, false, 'un hook que falta deja Hooks en rojo');
	} finally {
		vscodeStub.workspace.workspaceFolders = [];
		fs.rmSync(dir, { recursive: true, force: true });
	}
});
