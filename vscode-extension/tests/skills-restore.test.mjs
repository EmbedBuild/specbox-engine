// UC-9602 (US-96) — la copia gestionada del engine recupera sola las skills borradas.
//
// AC-01 · Al activarse, la extensión repone desde git los ficheros versionados que faltan en la copia
//         gestionada; un fichero modificado se queda como está.
// AC-02 · Tras reponer, un aviso dice cuántas skills ha recuperado.
// AC-03 · Una copia del engine en una ruta elegida por la persona nunca se toca ni avisa.
// AC-04 · Una persona afectada ve 26 de 26 skills de SpecBox sin ejecutar ningún comando.
//
// Las personas en Windows que instalaron e inicializaron un proyecto antes de UC-9601 tienen la copia
// gestionada (~/.specbox/specbox-engine) sin los ficheros de .claude/skills (git status: « D»).
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

const home = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'restore-home-')));
process.env.HOME = home;
process.env.USERPROFILE = home;

const shown = { info: [], warn: [] };
const vscodeStub = {
	l10n: { t: (s, ...args) => (args.length ? s.replace(/\{(\d+)\}/g, (_, i) => args[i]) : s) },
	env: { language: 'en' },
	window: {
		showInformationMessage: (msg) => { shown.info.push(msg); return Promise.resolve(undefined); },
		showWarningMessage: (msg) => { shown.warn.push(msg); return Promise.resolve(undefined); },
	},
	workspace: { getConfiguration: () => ({ get: () => undefined }), workspaceFolders: [] },
};
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function (req, ...rest) {
	if (req === 'vscode') { return 'vscode-stub'; }
	return originalResolve.call(this, req, ...rest);
};
require.cache['vscode-stub'] = { id: 'vscode-stub', filename: 'vscode-stub', loaded: true, exports: vscodeStub };

const { InstallManager, managedEnginePath, restoreManagedEngine } = require(path.join(root, 'out', 'install.js'));
const { HealthChecker } = require(path.join(root, 'out', 'health.js'));
const { KNOWN_SKILLS, CLAUDE_SKILLS_DIR } = require(path.join(root, 'out', 'constants.js'));

const git = (cwd, ...args) => execFileSync('git', args, { cwd, encoding: 'utf-8' });

/** Una copia del engine versionada en git con las 26 skills, en `dir`. */
function engineRepo(dir, { autocrlf } = {}) {
	fs.rmSync(dir, { recursive: true, force: true });
	fs.mkdirSync(dir, { recursive: true });
	if (autocrlf !== undefined) {
		git(dir, 'init', '-q');
		git(dir, 'config', 'core.autocrlf', String(autocrlf));
	}
	fs.writeFileSync(path.join(dir, 'ENGINE_VERSION.yaml'), 'version: 6.25.0\n');
	fs.writeFileSync(path.join(dir, 'README.md'), '# engine\n');
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

/** Lo que dejó el fallo de UC-9601: las carpetas de las skills vacías de la copia del engine. */
function loseSkills(engine, names = KNOWN_SKILLS) {
	for (const name of names) {
		const skill = path.join(engine, '.claude', 'skills', name);
		for (const entry of fs.readdirSync(skill)) { fs.rmSync(path.join(skill, entry), { recursive: true, force: true }); }
	}
}

/** Accesos de ~/.claude/skills a la copia gestionada, como los dejó la instalación. */
function linkSkills(engine) {
	fs.mkdirSync(CLAUDE_SKILLS_DIR, { recursive: true });
	for (const name of KNOWN_SKILLS) {
		const dest = path.join(CLAUDE_SKILLS_DIR, name);
		if (fs.existsSync(dest) || isLink(dest)) { continue; }
		fs.symlinkSync(path.join(engine, '.claude', 'skills', name), dest, 'junction');
	}
}

function isLink(p) { try { return fs.lstatSync(p).isSymbolicLink(); } catch { return false; } }

function reset() { shown.info = []; shown.warn = []; }

test('AC-01 · repone los ficheros borrados de la copia gestionada y deja como está el modificado', async () => {
	const engine = engineRepo(managedEnginePath());
	loseSkills(engine, ['plan', 'prd']);
	fs.writeFileSync(path.join(engine, 'README.md'), '# engine con cambios\n');

	const r = await restoreManagedEngine(engine);
	assert.deepEqual(r.skills, ['plan', 'prd']);
	assert.equal(r.restored.length, 4);
	assert.equal(git(engine, 'status', '--porcelain'), ' M README.md\n', 'solo queda el fichero modificado');
	assert.equal(fs.readFileSync(path.join(engine, 'README.md'), 'utf-8'), '# engine con cambios\n');
});

test('AC-01 · con core.autocrlf (lo normal en Windows) lo repuesto no queda como modificado', async () => {
	// Sin `checkout-index -u` git da por modificados todos los ficheros repuestos y el `git pull
	// --ff-only` del actualizador se negaría a avanzar la copia (lo vio la CI de Windows).
	const engine = engineRepo(managedEnginePath(), { autocrlf: true });
	loseSkills(engine);
	const r = await restoreManagedEngine(engine);
	assert.equal(r.skills.length, 26);
	assert.equal(git(engine, 'status', '--porcelain'), '', 'git status limpio');
});

test('AC-01 · sin nada borrado no hace nada', async () => {
	const engine = engineRepo(managedEnginePath());
	const r = await restoreManagedEngine(engine);
	assert.deepEqual(r, { restored: [], skills: [] });
});

test('AC-02 · tras reponer, el aviso dice cuántas skills ha recuperado', async () => {
	reset();
	const engine = engineRepo(managedEnginePath());
	linkSkills(engine);
	loseSkills(engine);
	const r = await new InstallManager({}).repairManagedEngine();
	assert.equal(r.skills.length, 26);
	assert.equal(shown.info.length, 1);
	assert.match(shown.info[0], /^\[x\] SpecBox recovered 26 skills /);

	reset();
	loseSkills(engine, ['plan']);
	await new InstallManager({}).repairManagedEngine();
	assert.match(shown.info[0], /^\[x\] SpecBox recovered 1 skill /);

	reset();
	await new InstallManager({}).repairManagedEngine();
	assert.deepEqual(shown.info, [], 'sin nada que reponer no avisa');
});

test('AC-03 · una copia del engine en otra ruta se queda con sus ficheros borrados y sin aviso', async () => {
	reset();
	fs.rmSync(managedEnginePath(), { recursive: true, force: true });
	const mine = engineRepo(fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'mi-engine-'))));
	loseSkills(mine, ['plan']);
	const before = git(mine, 'status', '--porcelain');
	assert.match(before, / D \.claude\/skills\/plan\/SKILL\.md/);

	assert.equal((await restoreManagedEngine(mine)).skipped, 'not_managed');
	const r = await new InstallManager({}).repairManagedEngine();
	assert.equal(r.skipped, 'no_clone');
	assert.equal(git(mine, 'status', '--porcelain'), before, 'git status igual que antes');
	assert.deepEqual(shown.info, []);
	assert.deepEqual(shown.warn, []);
});

test('AC-04 · una persona afectada ve 26 de 26 skills de SpecBox tras activarse la extensión', async () => {
	reset();
	const engine = engineRepo(managedEnginePath());
	linkSkills(engine);
	loseSkills(engine);
	const health = new HealthChecker();
	assert.equal(health.checkSkills().missing.length, 26, 'antes: 0 de 26');

	await new InstallManager({}).repairManagedEngine();
	assert.deepEqual(health.checkSkills().missing, [], 'después: 26 de 26');
	assert.equal(git(engine, 'status', '--porcelain'), '');
});

test('AC-04 · la activación repara la copia antes del primer diagnóstico', () => {
	const src = fs.readFileSync(path.join(root, 'src', 'extension.ts'), 'utf-8');
	const startup = src.slice(src.indexOf('async function runStartupTasks'));
	const repair = startup.indexOf('repairManagedEngine()');
	const firstHealth = startup.indexOf('health.run()');
	assert.ok(repair > 0, 'runStartupTasks llama a repairManagedEngine');
	assert.ok(repair < firstHealth, 'antes del primer health.run()');
});

test('la instalación repone la copia gestionada antes de crear los accesos', () => {
	const src = fs.readFileSync(path.join(root, 'src', 'install.ts'), 'utf-8');
	const run = src.slice(src.indexOf('async runFullInstall'), src.indexOf('async resolveEnginePath'));
	assert.ok(run.indexOf('restoreManagedEngine(') > 0, 'runFullInstall repone la copia');
	assert.ok(run.indexOf('restoreManagedEngine(') < run.indexOf('this.installSkills('), 'antes de instalar las skills');
});
