// UC-9604 (US-96) — el diagnóstico separa engine y skills y cuenta solo las de SpecBox.
//
// AC-01 · Con el engine encontrado y skills de SpecBox ausentes, la fila Engine muestra la versión y la
//         fila Skills queda pendiente; el panel no dice «Engine: Not installed».
// AC-02 · El contador cuenta solo las 26 de SpecBox (0/26, 26/26): las skills propias no entran.
// AC-03 · El panel lateral y el informe nombran las skills que faltan y la acción que las repone.
// AC-04 · «SpecBox: Health Check» vuelve a leer del disco la lista de skills del panel lateral, con las
//         mismas cifras que el informe y sin pulsar «Refrescar».
//
// Origen: el usuario veía «Engine: Not installed» y «Skills 28/54» cuando tenía el engine y 0 de 26
// skills de SpecBox (28 eran suyas).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import Module from 'node:module';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import fs from 'node:fs';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(import.meta.url);

class TreeItem {
	constructor(label, collapsibleState) { this.label = label; this.collapsibleState = collapsibleState; }
}
class EventEmitter {
	constructor() { this.fired = 0; this.event = () => {}; }
	fire() { this.fired += 1; }
}
const vscodeStub = {
	l10n: { t: (s, ...args) => (args.length ? s.replace(/\{(\d+)\}/g, (_, i) => args[i]) : s) },
	env: { language: 'en' },
	window: { activeColorTheme: undefined, createStatusBarItem: () => ({ show() {}, dispose() {} }) },
	workspace: { getConfiguration: () => ({ get: () => undefined }), workspaceFolders: [] },
	TreeItem,
	EventEmitter,
	ThemeIcon: class { constructor(id) { this.id = id; } },
	MarkdownString: class { constructor(v = '') { this.value = v; } appendMarkdown(s) { this.value += s; } },
	TreeItemCollapsibleState: { None: 0, Collapsed: 1, Expanded: 2 },
	StatusBarAlignment: { Left: 1 },
	ViewColumn: { One: 1 },
};
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function (req, ...rest) {
	if (req === 'vscode') { return 'vscode-stub'; }
	return originalResolve.call(this, req, ...rest);
};
require.cache['vscode-stub'] = { id: 'vscode-stub', filename: 'vscode-stub', loaded: true, exports: vscodeStub };

const { healthRows, renderHealthReport } = require(path.join(root, 'out', 'health.js'));
const { StatusTreeProvider } = require(path.join(root, 'out', 'views', 'status-tree.js'));
const { StatusBarManager } = require(path.join(root, 'out', 'statusbar.js'));
const { KNOWN_SKILLS } = require(path.join(root, 'out', 'constants.js'));

const OWN = Array.from({ length: 28 }, (_, i) => `mia-${i}`);
const BASE = {
	engineInstalled: true, engineVersion: '6.25.0', enginePath: 'C:\\Users\\BSA\\.specbox\\specbox-engine',
	node: { ok: true, version: 'v22.1.0' }, claudeCode: { ok: true, version: '2.1.0' },
	engram: { ok: true, version: '1.9.0' }, skills: { installed: [...OWN, ...KNOWN_SKILLS], missing: [] },
	hooks: { ok: true, count: 28, broken: [] }, settings: { ok: true },
	mcpSpecbox: { configured: true }, mcpEngram: { configured: true }, gga: { ok: true, version: '1.0.0' },
};
/** Lo que veía el usuario: el engine encontrado, sus 28 skills y ninguna de las 26 de SpecBox. */
const AFFECTED = { ...BASE, engineInstalled: false, skills: { installed: OWN, missing: [...KNOWN_SKILLS] } };

const row = (r, name) => healthRows(r).find((x) => x.component === name);
const fixedHealth = (r) => ({ calls: 0, async run() { this.calls += 1; return r; } });
const labels = (items) => items.map((i) => i.label);

test('AC-01 · engine encontrado sin skills: Engine con su versión y Skills pendiente', () => {
	assert.deepEqual(row(AFFECTED, 'Engine'), { component: 'Engine', state: 'done', detail: 'v6.25.0' });
	assert.equal(row(AFFECTED, 'Skills').state, 'pending');
	const noEngine = { ...AFFECTED, enginePath: null, engineVersion: null };
	assert.deepEqual(row(noEngine, 'Engine'), { component: 'Engine', state: 'pending', detail: 'Not installed' });
});

test('AC-01 · el panel lateral y la barra de estado no dicen «Not installed» con el engine encontrado', async () => {
	const items = await new StatusTreeProvider(fixedHealth(AFFECTED)).getChildren();
	assert.ok(labels(items).includes('Engine: v6.25.0'));
	assert.ok(!labels(items).some((l) => /Not installed/.test(l) && l.startsWith('Engine')));

	const bar = new StatusBarManager();
	bar.update(AFFECTED);
	assert.doesNotMatch(bar.item.text, /not installed/);
	assert.equal(bar.item.text, '$(alert) SpecBox v6.25.0 · 1 pending');
	assert.match(bar.item.tooltip.value, /\[ \] 26 SpecBox skills missing/);

	bar.update({ ...AFFECTED, enginePath: null, engineVersion: null });
	assert.equal(bar.item.text, '$(warning) SpecBox · not installed', 'sin engine sí lo dice');
});

test('AC-02 · el contador cuenta solo las 26 de SpecBox', async () => {
	assert.equal(row(AFFECTED, 'Skills').detail, '0/26', 'antes salía 28/54');
	assert.equal(row(BASE, 'Skills').detail, '26/26', 'las 28 propias no suben la cifra');
	const two = { ...BASE, skills: { installed: OWN, missing: KNOWN_SKILLS.slice(2) } };
	assert.equal(row(two, 'Skills').detail, '2/26');
	const items = await new StatusTreeProvider(fixedHealth(AFFECTED)).getChildren();
	assert.ok(labels(items).includes('Skills: 0/26'));
});

test('AC-03 · el informe nombra las skills que faltan y la acción que las repone', () => {
	const r = { ...BASE, skills: { installed: OWN, missing: ['plan', 'prd'] } };
	const html = renderHealthReport(r, 'light');
	assert.match(html, /Missing skills:.*plan, prd/s);
	assert.match(html, /Run &quot;SpecBox: Install Engine&quot; to restore them\./);
});

test('AC-03 · en el panel lateral, Skills se despliega con las que faltan y la acción', async () => {
	const r = { ...BASE, skills: { installed: OWN, missing: ['plan', 'prd'] } };
	const tree = new StatusTreeProvider(fixedHealth(r));
	const skills = (await tree.getChildren()).find((i) => String(i.label).startsWith('Skills'));
	assert.equal(skills.collapsibleState, 1, 'plegada pero desplegable');
	const children = await tree.getChildren(skills);
	assert.deepEqual(labels(children).slice(0, 2), ['plan', 'prd']);
	const action = children[2];
	assert.equal(action.label, 'Run "SpecBox: Install Engine" to restore them');
	assert.equal(action.command.command, 'specbox.install');

	const complete = (await new StatusTreeProvider(fixedHealth(BASE)).getChildren()).find((i) => String(i.label).startsWith('Skills'));
	assert.equal(complete.collapsibleState, 0, 'sin skills que falten no se despliega');
});

test('AC-04 · el panel lateral enseña el mismo resultado que el informe del Health Check', async () => {
	const health = fixedHealth(BASE);
	const tree = new StatusTreeProvider(health);
	tree.show(AFFECTED);
	const items = await tree.getChildren();
	assert.ok(labels(items).includes('Skills: 0/26'), 'las cifras del informe, no las de otra comprobación');
	assert.equal(health.calls, 0, 'no vuelve a comprobar por su cuenta');
});

test('AC-04 · «SpecBox: Health Check» vuelve a leer las skills del disco y pasa su resultado al panel', () => {
	const src = fs.readFileSync(path.join(root, 'src', 'extension.ts'), 'utf-8');
	const start = src.indexOf("registerCommand('specbox.healthCheck'");
	const handler = src.slice(start, src.indexOf('registerCommand(', start + 10));
	assert.match(handler, /skillsTree\.refresh\(\)/);
	assert.match(handler, /statusTree\.show\(result\)/);
	assert.match(handler, /health\.showReport\(result\)/);
});
