// UC-9601 (US-96) — reinstalar en Windows no borra el contenido al que apuntan los accesos de las skills.
//
// AC-01 · Instalar dos veces deja intactos los ficheros de las skills de la copia del engine.
// AC-02 · Instalar e inicializar un proyecto (las dos ejecutan la instalación) deja las 26 skills.
// AC-03 · Un acceso que ya apunta a su carpeta se deja; si apunta a otra, se quita solo el acceso.
// AC-04 · Con el sistema de ficheros simulado, la prueba falla si se borra en recursivo un enlace.
//
// Origen (2026-10-22, un usuario en Windows): symlinkOrCopy hacía fs.rmSync(dest, {recursive: true})
// sobre el junction que ya existía en ~/.claude/skills/<skill>; en Windows ese borrado atraviesa el
// junction y vacía la carpeta de la skill en ~/.specbox/specbox-engine. En macOS y Linux rm no sigue
// enlaces. Las pruebas con disco real usan junctions en Windows (CI extension-windows.yml) y enlaces
// simbólicos en macOS y Linux.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import Module from 'node:module';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(import.meta.url);

// Un home de pruebas: las constantes (~/.claude/skills) se calculan al cargar el módulo.
const home = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'skills-home-')));
process.env.HOME = home;
process.env.USERPROFILE = home;

const vscodeStub = {
	l10n: { t: (s, ...args) => (args.length ? s.replace(/\{(\d+)\}/g, (_, i) => args[i]) : s) },
	env: { language: 'en' },
	window: {},
	workspace: { getConfiguration: () => ({ get: () => undefined }), workspaceFolders: [] },
};
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function (req, ...rest) {
	if (req === 'vscode') { return 'vscode-stub'; }
	return originalResolve.call(this, req, ...rest);
};
require.cache['vscode-stub'] = { id: 'vscode-stub', filename: 'vscode-stub', loaded: true, exports: vscodeStub };

const { symlinkOrCopy } = require(path.join(root, 'out', 'util.js'));
const { InstallManager } = require(path.join(root, 'out', 'install.js'));
const { HealthChecker } = require(path.join(root, 'out', 'health.js'));
const { KNOWN_SKILLS, CLAUDE_SKILLS_DIR } = require(path.join(root, 'out', 'constants.js'));

// --- Sistema de ficheros simulado con la semántica de Windows ---------------------------------

/**
 * Un árbol en memoria con ficheros, carpetas y enlaces. Como en Windows, un borrado recursivo sobre un
 * enlace vacía la carpeta a la que apunta; además lo anota en `recursiveOnLink` para que la prueba falle.
 */
function simulatedFs() {
	const nodes = new Map(); // ruta → { kind: 'dir' | 'file' | 'link', target? }
	const recursiveOnLink = [];
	const norm = (p) => path.resolve(p);
	const enoent = (p) => Object.assign(new Error(`ENOENT: ${p}`), { code: 'ENOENT' });
	const below = (dir) => [...nodes.keys()].filter((k) => k.startsWith(dir + path.sep));
	const mkdirp = (dir) => {
		const parts = [];
		for (let d = norm(dir); !nodes.has(d) && d !== path.dirname(d); d = path.dirname(d)) { parts.unshift(d); }
		for (const d of parts) { nodes.set(d, { kind: 'dir' }); }
	};
	const stats = (node) => ({
		isSymbolicLink: () => node.kind === 'link',
		isDirectory: () => node.kind === 'dir',
		isFile: () => node.kind === 'file',
	});
	const api = {
		recursiveOnLink,
		nodes,
		file(p) { mkdirp(path.dirname(p)); nodes.set(norm(p), { kind: 'file' }); },
		filesUnder(dir) { return below(norm(dir)).filter((k) => nodes.get(k).kind === 'file'); },
		lstatSync(p) { const n = nodes.get(norm(p)); if (!n) { throw enoent(p); } return stats(n); },
		readlinkSync(p) { const n = nodes.get(norm(p)); if (n?.kind !== 'link') { throw enoent(p); } return n.target; },
		mkdirSync(p) { mkdirp(p); },
		unlinkSync(p) {
			const n = nodes.get(norm(p));
			if (!n) { throw enoent(p); }
			if (n.kind === 'dir') { throw Object.assign(new Error('EPERM'), { code: 'EPERM' }); }
			nodes.delete(norm(p));
		},
		rmdirSync(p) {
			const n = nodes.get(norm(p));
			if (!n) { throw enoent(p); }
			if (n.kind === 'dir' && below(norm(p)).length > 0) { throw Object.assign(new Error('ENOTEMPTY'), { code: 'ENOTEMPTY' }); }
			nodes.delete(norm(p));
		},
		rmSync(p, opts = {}) {
			const key = norm(p);
			const n = nodes.get(key);
			if (!n) { if (opts.force) { return; } throw enoent(p); }
			if (n.kind === 'link' && opts.recursive) {
				recursiveOnLink.push(key);
				// Lo que hace Windows: atraviesa el junction y borra lo que hay detrás.
				for (const k of below(norm(n.target))) { nodes.delete(k); }
			}
			if (n.kind === 'dir') { for (const k of below(key)) { nodes.delete(k); } }
			nodes.delete(key);
		},
		symlinkSync(target, p) { mkdirp(path.dirname(p)); nodes.set(norm(p), { kind: 'link', target }); },
		cpSync() { throw new Error('cpSync no se usa en estas pruebas'); },
		copyFileSync() { throw new Error('copyFileSync no se usa en estas pruebas'); },
	};
	return api;
}

const ENGINE = path.resolve('/sim/home/.specbox/specbox-engine/.claude/skills');
const SKILLS = path.resolve('/sim/home/.claude/skills');

function engineWithPlan(sim) {
	sim.file(path.join(ENGINE, 'plan', 'SKILL.md'));
	sim.file(path.join(ENGINE, 'plan', 'references', 'stitch.md'));
	sim.file(path.join(ENGINE, 'plan', 'LICENSE.txt'));
}

test('AC-04 · el sistema simulado detecta el fallo: el borrado recursivo de antes vacía la carpeta del engine', () => {
	// Comprueba que la prueba de AC-04 sabe fallar: el algoritmo anterior (rmSync recursivo sobre el
	// acceso existente) queda anotado y se lleva los ficheros de la skill, como le pasó al usuario.
	const sim = simulatedFs();
	engineWithPlan(sim);
	const src = path.join(ENGINE, 'plan');
	const dest = path.join(SKILLS, 'plan');
	sim.symlinkSync(src, dest, 'junction');
	sim.rmSync(dest, { recursive: true, force: true });
	assert.deepEqual(sim.recursiveOnLink, [dest]);
	assert.deepEqual(sim.filesUnder(src), []);
});

test('AC-04 · reinstalar sobre un acceso que ya existe nunca lo borra en recursivo y conserva los ficheros', () => {
	const sim = simulatedFs();
	engineWithPlan(sim);
	const src = path.join(ENGINE, 'plan');
	const dest = path.join(SKILLS, 'plan');
	assert.equal(symlinkOrCopy(src, dest, 'dir', sim), 'linked', 'la primera instalación crea el acceso');
	assert.equal(symlinkOrCopy(src, dest, 'dir', sim), 'kept', 'la segunda lo deja como está');
	assert.equal(symlinkOrCopy(src, dest, 'dir', sim), 'kept');
	assert.deepEqual(sim.recursiveOnLink, [], 'ningún borrado recursivo sobre un enlace');
	assert.equal(sim.filesUnder(src).length, 3, 'la skill del engine conserva sus tres ficheros');
});

test('AC-03 · un acceso que apunta a otra carpeta se quita sin tocarla y se crea el bueno', () => {
	const sim = simulatedFs();
	engineWithPlan(sim);
	const other = path.resolve('/sim/home/mis-skills/plan');
	sim.file(path.join(other, 'SKILL.md'));
	sim.file(path.join(other, 'notas.md'));
	const src = path.join(ENGINE, 'plan');
	const dest = path.join(SKILLS, 'plan');
	sim.symlinkSync(other, dest, 'junction');

	assert.equal(symlinkOrCopy(src, dest, 'dir', sim), 'linked');
	assert.deepEqual(sim.recursiveOnLink, []);
	assert.equal(sim.readlinkSync(dest), src, 'el acceso apunta ahora a la skill del engine');
	assert.equal(sim.filesUnder(other).length, 2, 'la otra carpeta conserva todos sus ficheros');
	assert.equal(sim.filesUnder(src).length, 3);
});

test('AC-03 · el mismo destino escrito de otra forma cuenta como el mismo (relativo, separador final)', () => {
	const sim = simulatedFs();
	engineWithPlan(sim);
	const src = path.join(ENGINE, 'plan');
	const dest = path.join(SKILLS, 'plan');
	sim.symlinkSync(path.relative(SKILLS, src) + path.sep, dest, 'junction');
	assert.equal(symlinkOrCopy(src, dest, 'dir', sim), 'kept');
	assert.deepEqual(sim.recursiveOnLink, []);
});

test('una copia real de una instalación anterior sí se sustituye por el acceso', () => {
	// Sin enlaces (Windows sin junctions), la extensión copiaba la skill: esa carpeta es suya y se
	// puede borrar entera.
	const sim = simulatedFs();
	engineWithPlan(sim);
	const src = path.join(ENGINE, 'plan');
	const dest = path.join(SKILLS, 'plan');
	sim.file(path.join(dest, 'SKILL.md'));
	sim.file(path.join(dest, 'viejo.md'));

	assert.equal(symlinkOrCopy(src, dest, 'dir', sim), 'linked');
	assert.equal(sim.lstatSync(dest).isSymbolicLink(), true);
	assert.deepEqual(sim.recursiveOnLink, []);
	assert.equal(sim.filesUnder(src).length, 3);
});

test('un enlace de fichero (comandos) que ya apunta a su origen se deja; si no, se quita solo el enlace', () => {
	const sim = simulatedFs();
	const src = path.resolve('/sim/home/.specbox/specbox-engine/commands/prd.md');
	const other = path.resolve('/sim/home/otro/prd.md');
	const dest = path.resolve('/sim/home/.claude/commands/prd.md');
	sim.file(src);
	sim.file(other);
	sim.symlinkSync(src, dest, 'file');
	assert.equal(symlinkOrCopy(src, dest, 'file', sim), 'kept');
	sim.rmSync(dest);
	sim.symlinkSync(other, dest, 'file');
	assert.equal(symlinkOrCopy(src, dest, 'file', sim), 'linked');
	assert.equal(sim.nodes.get(other).kind, 'file', 'el fichero al que apuntaba sigue ahí');
});

// --- Disco real: junctions en Windows, enlaces simbólicos en macOS y Linux ---------------------

const git = (cwd, ...args) => execFileSync('git', args, { cwd, encoding: 'utf-8' });

/** Una copia del engine versionada en git con las 26 skills de SpecBox, cada una con subcarpetas. */
function engineRepo() {
	const dir = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'skills-engine-')));
	fs.writeFileSync(path.join(dir, 'ENGINE_VERSION.yaml'), 'version: 6.25.0\n');
	for (const name of KNOWN_SKILLS) {
		const skill = path.join(dir, '.claude', 'skills', name);
		fs.mkdirSync(path.join(skill, 'references'), { recursive: true });
		fs.writeFileSync(path.join(skill, 'SKILL.md'), `---\nname: ${name}\n---\n`);
		fs.writeFileSync(path.join(skill, 'references', 'guia.md'), `# ${name}\n`);
	}
	git(dir, 'init', '-q');
	git(dir, 'add', '-A');
	git(dir, '-c', 'user.email=pruebas@specbox.build', '-c', 'user.name=Pruebas', 'commit', '-q', '-m', 'engine');
	return dir;
}

function cleanSkillsDir() {
	// Quitar los accesos sin seguirlos (rmSync recursivo sobre CLAUDE_SKILLS_DIR podría atravesarlos).
	if (!fs.existsSync(CLAUDE_SKILLS_DIR)) { return; }
	for (const name of fs.readdirSync(CLAUDE_SKILLS_DIR)) {
		const p = path.join(CLAUDE_SKILLS_DIR, name);
		if (fs.lstatSync(p).isSymbolicLink()) {
			try { fs.unlinkSync(p); } catch { fs.rmdirSync(p); }
		} else {
			fs.rmSync(p, { recursive: true, force: true });
		}
	}
}

const installer = new InstallManager({});
const install = (enginePath) => installer.installSkills(enginePath);

test('AC-01 · instalar dos veces seguidas deja la copia del engine sin ningún fichero borrado', () => {
	const engine = engineRepo();
	cleanSkillsDir();
	install(engine); // «SpecBox: Instalar Engine»
	install(engine); // otra vez
	assert.equal(git(engine, 'status', '--porcelain'), '', 'git status sin cambios en la copia del engine');
	for (const name of KNOWN_SKILLS) {
		assert.ok(fs.existsSync(path.join(engine, '.claude', 'skills', name, 'references', 'guia.md')), name);
	}
});

test('AC-02 · instalar e inicializar un proyecto deja las 26 skills de SpecBox en el diagnóstico', () => {
	const engine = engineRepo();
	cleanSkillsDir();
	install(engine); // «SpecBox: Instalar Engine»
	install(engine); // «SpecBox: Inicializar Proyecto» vuelve a ejecutar la instalación
	const skills = new HealthChecker().checkSkills();
	assert.deepEqual(skills.missing, [], 'ninguna skill de SpecBox falta');
	for (const name of KNOWN_SKILLS) { assert.ok(skills.installed.includes(name), name); }
	assert.equal(git(engine, 'status', '--porcelain'), '');
});

test('AC-03 · con disco real, el acceso que apunta a otra carpeta se sustituye y esa carpeta queda entera', () => {
	const engine = engineRepo();
	cleanSkillsDir();
	const other = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'skills-otra-')));
	fs.writeFileSync(path.join(other, 'SKILL.md'), '---\nname: plan\n---\n');
	fs.writeFileSync(path.join(other, 'notas.md'), 'mías\n');
	fs.mkdirSync(CLAUDE_SKILLS_DIR, { recursive: true });
	fs.symlinkSync(other, path.join(CLAUDE_SKILLS_DIR, 'plan'), 'junction');

	install(engine);
	assert.deepEqual(fs.readdirSync(other).sort(), ['SKILL.md', 'notas.md']);
	assert.equal(
		path.resolve(fs.realpathSync(path.join(CLAUDE_SKILLS_DIR, 'plan'))),
		path.resolve(path.join(engine, '.claude', 'skills', 'plan')),
	);
	assert.equal(git(engine, 'status', '--porcelain'), '');
});
