// UC-4903 — la extensión habla el idioma visual del sistema «Tinta» (D18).
//
// AC-01 · la página de retorno OAuth y el diagnóstico usan los tokens del sistema, oscuros por
//         defecto y con el tema de VSCode; el código no escribe colores.
// AC-02 · la barra de estado y los mensajes dicen el estado con palabra; hecho = [x].
// AC-03 · las páginas solo llevan iconos Lucide con nombre accesible (o decorativos junto a texto).
//
// Corre contra out/ (compilado) con el módulo vscode simulado, como el resto de la suite.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import Module from 'node:module';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import fs from 'node:fs';
import path from 'node:path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, '..');
const outDir = path.join(root, 'out');
const require = createRequire(import.meta.url);

const statusItems = [];
const vscodeStub = {
	l10n: { t: (s, ...args) => (args.length ? s.replace(/\{(\d+)\}/g, (_, i) => args[i]) : s) },
	env: { language: 'es' },
	Uri: { parse: (s) => ({ toString: () => s }) },
	StatusBarAlignment: { Left: 1 },
	MarkdownString: class { constructor(v) { this.value = v; } appendMarkdown(v) { this.value += v; } },
	ViewColumn: { One: 1 },
	window: {
		activeColorTheme: undefined,
		showInformationMessage: async () => undefined,
		createStatusBarItem: () => { const it = { show() {}, dispose() {} }; statusItems.push(it); return it; },
	},
	workspace: { getConfiguration: () => ({ get: () => undefined }), workspaceFolders: [] },
};
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function (req, ...rest) {
	if (req === 'vscode') { return 'vscode-stub'; }
	return originalResolve.call(this, req, ...rest);
};
require.cache['vscode-stub'] = { id: 'vscode-stub', filename: 'vscode-stub', loaded: true, exports: vscodeStub };

const design = require(path.join(outDir, 'design.js'));
const { renderSuccessPage, renderErrorPage } = require(path.join(outDir, 'oauth.js'));
const { renderHealthReport, healthRows } = require(path.join(outDir, 'health.js'));
const { StatusBarManager } = require(path.join(outDir, 'statusbar.js'));

const HEALTH_OK = {
	engineInstalled: true, engineVersion: '6.14.2', enginePath: '/home/ana/.specbox/specbox-engine',
	node: { ok: true, version: 'v22.1.0' }, claudeCode: { ok: true, version: '2.1.0' },
	engram: { ok: true, version: '1.9.0' }, skills: { installed: ['prd', 'plan'], missing: [] },
	hooks: { ok: true, count: 30 }, settings: { ok: true },
	mcpSpecbox: { configured: true }, mcpEngram: { configured: true }, gga: { ok: false, version: null },
};
const HEALTH_ISSUES = { ...HEALTH_OK, engram: { ok: false, version: null }, mcpEngram: { configured: false } };

const HEX = /#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})(?![0-9a-zA-Z_-])/;
const FUNC = /\b(?:rgba?|hsla?|oklch|oklab|lab|lch|hwb)\([^)]*\)/;

/** Cada <svg> de la página: Lucide con nombre o decorativo; la caja marcada, decorativa. */
function iconProblems(html) {
	const out = [];
	for (const m of html.matchAll(/<svg\b[^>]*>/g)) {
		const tag = m[0];
		const isBrand = /class="brand-mark"/.test(tag);
		const isLucide = /class="lucide lucide-[a-z-]+"/.test(tag);
		const hidden = /aria-hidden="true"/.test(tag);
		const named = /role="img"/.test(tag) && /aria-label="[^"]+"/.test(tag);
		if (!isBrand && !isLucide) { out.push(`svg que no es Lucide ni la marca: ${tag.slice(0, 60)}`); }
		if (isBrand && !hidden) { out.push('la marca debe ser decorativa'); }
		if (isLucide && !hidden && !named) { out.push(`icono sin nombre: ${tag.slice(0, 60)}`); }
	}
	return out;
}

test('AC-01 · el código de las páginas y de la barra no escribe colores', () => {
	for (const f of ['src/design.ts', 'src/oauth.ts', 'src/health.ts', 'src/statusbar.ts']) {
		const code = fs.readFileSync(path.join(root, f), 'utf8');
		assert.equal(HEX.exec(code), null, `${f}: color hex escrito`);
		assert.equal(FUNC.exec(code), null, `${f}: color rgb()/hsl() escrito`);
	}
});

test('AC-01 · la página de retorno usa los tokens del sistema y es oscura por defecto', () => {
	vscodeStub.window.activeColorTheme = undefined;
	for (const html of [renderSuccessPage(), renderErrorPage('access_denied', 'Cancelaste el acceso')]) {
		assert.match(html, /<html[^>]*data-theme="dark"/);
		// Las variables del sistema van incrustadas (los dos temas) y la página solo usa var(--…).
		assert.match(html, /--paper-000:/);
		assert.match(html, /\[data-theme="dark"\]/);
		assert.match(html, /IBM\+Plex\+Sans/);
		const pageCss = html.slice(html.lastIndexOf('html { color-scheme'));
		assert.equal(HEX.exec(pageCss.split('</style>')[0]), null, 'la hoja propia de la página no escribe colores');
	}
});

test('AC-01 · la página y el diagnóstico siguen el tema claro de VSCode', () => {
	vscodeStub.window.activeColorTheme = { kind: 1 }; // Light
	assert.match(renderSuccessPage(), /<html[^>]*data-theme="light"/);
	assert.match(renderHealthReport(HEALTH_OK), /<html[^>]*data-theme="light"/);
	vscodeStub.window.activeColorTheme = { kind: 4 }; // HighContrastLight
	assert.match(renderErrorPage('x'), /data-theme="light"/);
	vscodeStub.window.activeColorTheme = { kind: 3 }; // HighContrast → oscuro
	assert.match(renderHealthReport(HEALTH_OK), /data-theme="dark"/);
	vscodeStub.window.activeColorTheme = undefined;
	assert.equal(design.pageTheme(), 'dark');
});

test('AC-03 · las páginas solo llevan iconos Lucide con nombre y la marca decorativa', () => {
	for (const html of [renderSuccessPage(), renderErrorPage('x'), renderHealthReport(HEALTH_OK), renderHealthReport(HEALTH_ISSUES)]) {
		assert.deepEqual(iconProblems(html), []);
		assert.match(html, /class="brand-mark"/);
		assert.match(html, /class="lucide lucide-circle-(?:check|x|alert)"[^>]*role="img"[^>]*aria-label="/);
	}
	// Ni emojis.
	assert.equal(/\p{Extended_Pictographic}/u.test(renderHealthReport(HEALTH_ISSUES)), false);
});

test('AC-02 · el diagnóstico dice el estado con palabra: [x] listo, [ ] pendiente, [ ] opcional', () => {
	const rows = healthRows(HEALTH_ISSUES);
	assert.equal(rows.find((r) => r.component === 'Engram').state, 'pending');
	assert.equal(rows.find((r) => r.component === 'GGA').state, 'optional');
	assert.equal(rows.find((r) => r.component === 'Node.js').state, 'done');
	const html = renderHealthReport(HEALTH_ISSUES);
	assert.match(html, /\[x\] Ready/);
	assert.match(html, /\[ \] Pending/);
	assert.match(html, /\[ \] Optional/);
	assert.match(html, /2 pending/);
	assert.match(renderHealthReport(HEALTH_OK), /\[x\] All systems operational/);
});

test('AC-02 · la barra de estado lleva siempre la palabra; hecho = [x] SpecBox', () => {
	const bar = new StatusBarManager();
	assert.equal(bar.item.text, '$(loading~spin) SpecBox · checking');
	bar.update(HEALTH_OK);
	assert.equal(bar.item.text, '[x] SpecBox v6.14.2 · ready');
	assert.match(bar.item.tooltip.value, /\[x\] SpecBox Engine — all systems operational/);
	bar.update(HEALTH_ISSUES);
	assert.equal(bar.item.text, '$(alert) SpecBox v6.14.2 · 2 pending');
	assert.match(bar.item.tooltip.value, /\[ \] Engram missing/);
	bar.update({ ...HEALTH_OK, engineInstalled: false });
	assert.equal(bar.item.text, '$(warning) SpecBox · not installed');
	// La barra conserva los iconos nativos de VSCode ($(…)); nunca un SVG ni un emoji.
	assert.equal(/<svg|\p{Extended_Pictographic}/u.test(bar.item.text), false);
});

test('AC-02 · los avisos de acciones terminadas empiezan por [x]', () => {
	const sources = ['src/auth.ts', 'src/extension.ts', 'src/install.ts', 'src/mcp.ts', 'src/migration.ts', 'src/prerequisites.ts', 'src/updater.ts', 'src/onboard.ts']
		.map((f) => fs.readFileSync(path.join(root, f), 'utf8')).join('\n');
	for (const done of ['Signed out.', 'SpecBox Engine cloned.', 'All prerequisites are installed. SpecBox is ready.', 'Signed in. Welcome!']) {
		assert.ok(sources.includes(`markDone(vscode.l10n.t('${done}')`), `«${done}» sin [x]`);
	}
	assert.ok(sources.includes('markDone(`MCP configured:'), 'MCP configurado sin [x]');
	assert.equal(design.markDone('Clonado'), '[x] Clonado');
});
