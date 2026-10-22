// UC-9603 (US-96) — la instalación comprueba las skills que deja antes de decir que ha terminado.
//
// AC-01 · El recuento de skills del aviso final de «Instalar Engine» cuenta las skills cuyo SKILL.md se
//         puede leer a través de su acceso, no los accesos creados.
// AC-02 · Si falta alguna de las 26 skills de SpecBox, el aviso final no dice que la instalación ha
//         terminado bien: nombra las que faltan y ofrece abrir el Health Check.
//
// Antes, runFullInstall contaba los accesos que creaba y su aviso solo miraba Engram y los MCP: podía
// decir «installed: 26 skills» con el Health Check marcando Skills pendiente.
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

const home = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'summary-home-')));
process.env.HOME = home;
process.env.USERPROFILE = home;

const shown = { info: [], warn: [], commands: [] };
let answer; // botón que «pulsa» la persona en el siguiente aviso
let config = {};
const vscodeStub = {
	l10n: { t: (s, ...args) => (args.length ? s.replace(/\{(\d+)\}/g, (_, i) => args[i]) : s) },
	env: { language: 'en' },
	window: {
		showInformationMessage: (msg, ...buttons) => { shown.info.push({ msg, buttons }); return Promise.resolve(undefined); },
		showWarningMessage: (msg, ...buttons) => { shown.warn.push({ msg, buttons }); return Promise.resolve(answer); },
		showErrorMessage: () => Promise.resolve(undefined),
		withProgress: (_opts, fn) => fn({ report: () => {} }),
	},
	workspace: {
		workspaceFolders: [],
		getConfiguration: () => ({ get: (k) => config[k], update: () => Promise.resolve() }),
	},
	commands: { executeCommand: (c) => { shown.commands.push(c); return Promise.resolve(); } },
	ProgressLocation: { Notification: 15 },
	ConfigurationTarget: { Global: 1 },
};
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function (req, ...rest) {
	if (req === 'vscode') { return 'vscode-stub'; }
	return originalResolve.call(this, req, ...rest);
};
require.cache['vscode-stub'] = { id: 'vscode-stub', filename: 'vscode-stub', loaded: true, exports: vscodeStub };

const { InstallManager, buildInstallSummary } = require(path.join(root, 'out', 'install.js'));
const { specboxSkillsState } = require(path.join(root, 'out', 'health.js'));
const { KNOWN_SKILLS, CLAUDE_SKILLS_DIR } = require(path.join(root, 'out', 'constants.js'));

/** Una copia del engine con hooks, settings y las 26 skills; `withoutSkillMd` quedan sin SKILL.md. */
function engine(withoutSkillMd = [], extraWithoutSkillMd = []) {
	const dir = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'summary-engine-')));
	fs.writeFileSync(path.join(dir, 'ENGINE_VERSION.yaml'), 'version: 6.25.0\n');
	fs.mkdirSync(path.join(dir, '.claude', 'hooks'), { recursive: true });
	fs.writeFileSync(path.join(dir, '.claude', 'hooks', 'spec-guard.mjs'), '');
	fs.writeFileSync(path.join(dir, '.claude', 'settings.json'), '{}\n');
	for (const name of KNOWN_SKILLS) {
		const skill = path.join(dir, '.claude', 'skills', name);
		fs.mkdirSync(skill, { recursive: true });
		fs.writeFileSync(path.join(skill, 'README.md'), name);
		if (!withoutSkillMd.includes(name)) { fs.writeFileSync(path.join(skill, 'SKILL.md'), `---\nname: ${name}\n---\n`); }
	}
	for (const name of extraWithoutSkillMd) {
		fs.mkdirSync(path.join(dir, '.claude', 'skills', name), { recursive: true });
		fs.writeFileSync(path.join(dir, '.claude', 'skills', name, 'NOTAS.md'), name);
	}
	return dir;
}

function reset() {
	shown.info = []; shown.warn = []; shown.commands = []; answer = undefined;
	fs.rmSync(path.join(home, '.claude'), { recursive: true, force: true });
}

test('AC-01 · el recuento son las skills cuyo SKILL.md se lee a través de su acceso', async () => {
	reset();
	config = { enginePath: engine(['plan']) };
	await new InstallManager({}).runFullInstall();
	const all = [...shown.info, ...shown.warn].map((x) => x.msg).join('\n');
	assert.match(all, /25 of 26 SpecBox skills|could not install 1 of 26/, 'cuenta 25 legibles, no 26 accesos creados');
	assert.doesNotMatch(all, /26 skills/);
	assert.deepEqual(specboxSkillsState(CLAUDE_SKILLS_DIR).missing, ['plan']);
});

test('AC-01 · 27 accesos creados y uno sin SKILL.md: el aviso dice 26 skills', async () => {
	reset();
	config = { enginePath: engine([], ['borrador']) };
	await new InstallManager({}).runFullInstall();
	const all = [...shown.info, ...shown.warn].map((x) => x.msg);
	assert.equal(all.length, 1);
	assert.match(all[0], /\(26 skills, 1 hooks\)|installed: 26 skills/, 'las legibles');
	assert.doesNotMatch(all[0], /27/, 'no los accesos creados');
	assert.equal(fs.readdirSync(CLAUDE_SKILLS_DIR).length, 27);
});

test('AC-02 · con una skill sin SKILL.md el aviso no dice que ha terminado bien y nombra la que falta', async () => {
	reset();
	config = { enginePath: engine(['plan', 'prd']) };
	answer = 'Open Health Check';
	await new InstallManager({}).runFullInstall();
	assert.equal(shown.info.length, 0, 'ningún aviso de éxito');
	assert.equal(shown.warn.length, 1);
	const { msg, buttons } = shown.warn[0];
	assert.match(msg, /could not install 2 of 26 SpecBox skills: plan, prd\./);
	assert.doesNotMatch(msg, /\binstalled\b/);
	assert.ok(buttons.includes('Open Health Check'));
	assert.deepEqual(shown.commands, ['specbox.healthCheck'], 'el botón abre el Health Check');
});

test('buildInstallSummary · con las 26 legibles y los MCP listos, éxito con 26', () => {
	const s = buildInstallSummary({ engineVersion: '6.25.0', readableSkills: 26, missingSkills: [], hooks: 28, missingPieces: [] });
	assert.equal(s.level, 'info');
	assert.equal(s.text, '[x] SpecBox Engine v6.25.0 installed: 26 skills, 28 hooks, MCP configured.');
	assert.deepEqual(s.actions, []);
});

test('buildInstallSummary · faltan skills y MCP: aviso con los dos botones y sin «installed»', () => {
	const s = buildInstallSummary({ engineVersion: '6.25.0', readableSkills: 24, missingSkills: ['plan', 'prd'], hooks: 28, missingPieces: ['MCP SpecBox server'] });
	assert.equal(s.level, 'warning');
	assert.equal(s.text, 'SpecBox could not install 2 of 26 SpecBox skills: plan, prd. Also missing: MCP SpecBox server.');
	assert.deepEqual(s.actions, ['healthCheck', 'configureMcp']);
});

test('buildInstallSummary · skills completas y falta un MCP: el aviso de siempre con las 26', () => {
	const s = buildInstallSummary({ engineVersion: '6.25.0', readableSkills: 26, missingSkills: [], hooks: 28, missingPieces: ['Engram'] });
	assert.equal(s.level, 'warning');
	assert.equal(s.text, 'SpecBox installed (26 skills, 28 hooks). Missing: Engram. Configure now?');
	assert.deepEqual(s.actions, ['configureMcp']);
});

test('specboxSkillsState · un acceso cuyo SKILL.md no se abre cuenta como ausente', () => {
	const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'summary-skills-'));
	for (const name of KNOWN_SKILLS.slice(0, 3)) {
		fs.mkdirSync(path.join(dir, name));
		fs.writeFileSync(path.join(dir, name, 'SKILL.md'), '');
	}
	fs.mkdirSync(path.join(dir, KNOWN_SKILLS[3], 'SKILL.md'), { recursive: true }); // una carpeta, no un fichero
	const state = specboxSkillsState(dir);
	assert.deepEqual(state.present, KNOWN_SKILLS.slice(0, 3));
	assert.equal(state.missing.length, 23);
	assert.ok(state.missing.includes(KNOWN_SKILLS[3]));
});
