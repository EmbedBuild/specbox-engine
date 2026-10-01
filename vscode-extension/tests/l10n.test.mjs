// US-57 / UC-5702 — la extensión habla el idioma de VSCode de principio a fin.
//
// AC-01 · todo texto que pasa por vscode.l10n.t está en bundle.l10n.json y en
//         bundle.l10n.es.json, y los dos bundles tienen exactamente las mismas claves
//         (sin entrada, VSCode enseña la clave: el texto en inglés).
// AC-02 · el linter de cadenas (scripts/lint-extension-strings.mjs) pasa: ningún aviso,
//         diálogo, título de progreso ni paso de progreso con un literal fuera de l10n.t.
// AC-03 · esta prueba corre con `npm test`.
//
// Se lee el código fuente: l10n.t no se puede ejecutar fuera de VSCode, y una clave que
// no es un literal no se puede traducir, así que también se rechaza.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const EXT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const SRC = path.join(EXT, 'src');
const readJson = (rel) => JSON.parse(fs.readFileSync(path.join(EXT, rel), 'utf8'));

function sources(dir, acc = []) {
	for (const name of fs.readdirSync(dir)) {
		const p = path.join(dir, name);
		if (fs.statSync(p).isDirectory()) { sources(p, acc); }
		else if (p.endsWith('.ts') && !p.endsWith('.d.ts')) { acc.push(p); }
	}
	return acc;
}

/**
 * Claves literales de l10n.t (con su fichero) y las llamadas cuya clave no es un literal.
 * Cuenta también el alias `const t = vscode.l10n.t` (health.ts, statusbar.ts).
 */
function l10nCalls() {
	const keys = new Map();
	const dynamic = [];
	for (const file of sources(SRC)) {
		const src = fs.readFileSync(file, 'utf8');
		const rel = path.relative(EXT, file);
		const call = /const\s+t\s*=\s*vscode\.l10n\.t\b/.test(src)
			? /(?:\bl10n\.t|(?<![.\w])t)\(\s*/g
			: /\bl10n\.t\(\s*/g;
		for (const m of src.matchAll(call)) {
			const rest = src.slice(m.index + m[0].length);
			const lit = rest.match(/^(['"`])((?:\\.|(?!\1)[^\\])*)\1/);
			if (!lit || (lit[1] === '`' && lit[2].includes('${'))) {
				dynamic.push(`${rel}: l10n.t(${rest.slice(0, 40)}…`);
				continue;
			}
			const key = lit[2].replace(/\\(.)/g, '$1');
			if (!keys.has(key)) { keys.set(key, rel); }
		}
	}
	return { keys, dynamic };
}

const placeholders = (s) => [...s.matchAll(/\{(\d+)\}/g)].map((m) => m[1]).sort().join(',');

const en = readJson('l10n/bundle.l10n.json');
const es = readJson('l10n/bundle.l10n.es.json');
const { keys, dynamic } = l10nCalls();

test('la lectura del código encuentra las llamadas a l10n.t', () => {
	assert.ok(keys.size >= 80, `solo ${keys.size} claves: ¿cambió la forma de llamar a l10n.t?`);
});

test('AC-01 · ninguna clave de l10n.t se construye en tiempo de ejecución', () => {
	assert.deepEqual(dynamic, []);
});

test('AC-01 · cada texto de l10n.t está en el bundle inglés y en el español', () => {
	const missingEn = [...keys].filter(([k]) => !(k in en)).map(([k, f]) => `${f}: ${k}`);
	const missingEs = [...keys].filter(([k]) => !(k in es)).map(([k, f]) => `${f}: ${k}`);
	assert.deepEqual(missingEn, [], 'faltan en l10n/bundle.l10n.json');
	assert.deepEqual(missingEs, [], 'faltan en l10n/bundle.l10n.es.json');
});

test('AC-01 · los dos bundles tienen exactamente las mismas claves', () => {
	assert.deepEqual(Object.keys(es).sort(), Object.keys(en).sort());
});

test('AC-01 · el inglés es la propia clave y el español traduce sin perder huecos {0}', () => {
	for (const [key, value] of Object.entries(en)) {
		assert.equal(value, key, `en: «${key}»`);
	}
	for (const [key, value] of Object.entries(es)) {
		assert.ok(value.trim(), `es vacío: «${key}»`);
		assert.equal(placeholders(value), placeholders(key), `es cambia los huecos: «${key}» → «${value}»`);
	}
});

test('AC-01 · los textos del manifiesto (package.nls) también tienen las mismas claves', () => {
	const nlsEn = readJson('package.nls.json');
	const nlsEs = readJson('package.nls.es.json');
	assert.deepEqual(Object.keys(nlsEs).sort(), Object.keys(nlsEn).sort());
});

test('AC-02 · el linter de cadenas de la extensión pasa', () => {
	const lint = spawnSync(process.execPath, [path.join(EXT, '..', 'scripts', 'lint-extension-strings.mjs')], {
		encoding: 'utf8',
	});
	assert.equal(lint.status, 0, lint.stderr || lint.stdout);
});
