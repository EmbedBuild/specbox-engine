// UC-701 / AC-01..AC-04 — skill-loader pure-function tests, zero-deps via node:test.
// Runs against the compiled output in out/.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import Module from 'node:module';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.resolve(__dirname, '..', 'out');
const require = createRequire(import.meta.url);

// skill-loader.ts does NOT import vscode, but if some other path does we stub it.
const vscodeStub = { l10n: { t: (s) => s } };
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function (req, ...rest) {
	if (req === 'vscode') { return 'vscode-stub'; }
	return originalResolve.call(this, req, ...rest);
};
require.cache['vscode-stub'] = { id: 'vscode-stub', filename: 'vscode-stub', loaded: true, exports: vscodeStub };

const { loadSkillsFromFilesystem, parseSkillFrontmatter } = require(path.join(outDir, 'views', 'skill-loader.js'));

function mkSkill(rootDir, name, frontmatter, body = '') {
	const skillDir = path.join(rootDir, name);
	fs.mkdirSync(skillDir, { recursive: true });
	const fmBlock = frontmatter ? `---\n${frontmatter}\n---\n` : '';
	fs.writeFileSync(path.join(skillDir, 'SKILL.md'), `${fmBlock}${body}`);
}

function tempRoot(label) {
	return fs.mkdtempSync(path.join(os.tmpdir(), `specbox-skill-loader-${label}-`));
}

test('AC-01a: loads skills from a single directory', () => {
	const root = tempRoot('a');
	mkSkill(root, 'foo', 'name: foo\ndescription: Foo does foo things');
	mkSkill(root, 'bar', 'name: bar\ndescription: Bar does bar things');

	const skills = loadSkillsFromFilesystem({ localPaths: [], globalPaths: [root] });
	assert.equal(skills.length, 2);
	const foo = skills.find(s => s.name === 'foo');
	assert.equal(foo.description, 'Foo does foo things');
	assert.equal(foo.source, 'global');
	assert.equal(foo.hasFrontmatter, true);

	fs.rmSync(root, { recursive: true, force: true });
});

test('AC-02: local skills win over global with same name', () => {
	const local = tempRoot('local');
	const global = tempRoot('global');
	mkSkill(local, 'shared', 'name: shared\ndescription: local version');
	mkSkill(global, 'shared', 'name: shared\ndescription: global version');
	mkSkill(global, 'global-only', 'name: global-only\ndescription: only in global');

	const skills = loadSkillsFromFilesystem({ localPaths: [local], globalPaths: [global] });
	assert.equal(skills.length, 2);
	const shared = skills.find(s => s.name === 'shared');
	assert.equal(shared.description, 'local version');
	assert.equal(shared.source, 'local');
	const globalOnly = skills.find(s => s.name === 'global-only');
	assert.equal(globalOnly.source, 'global');

	fs.rmSync(local, { recursive: true, force: true });
	fs.rmSync(global, { recursive: true, force: true });
});

test('AC-03: missing directory does not throw, returns []', () => {
	const skills = loadSkillsFromFilesystem({ localPaths: [], globalPaths: ['/this/path/does/not/exist'] });
	assert.deepEqual(skills, []);
});

test('AC-03b: onError callback is invoked when a directory cannot be read', () => {
	const errors = [];
	loadSkillsFromFilesystem({
		localPaths: [],
		globalPaths: ['/this/path/does/not/exist'],
		onError: (err, p) => errors.push({ err, p }),
	});
	assert.equal(errors.length, 1);
	assert.equal(errors[0].p, '/this/path/does/not/exist');
});

test('malformed frontmatter: skill still appears with hasFrontmatter=false-ish', () => {
	const root = tempRoot('malformed');
	mkSkill(root, 'broken', null, 'no frontmatter at all, just body text');

	const skills = loadSkillsFromFilesystem({ localPaths: [], globalPaths: [root] });
	assert.equal(skills.length, 1);
	assert.equal(skills[0].name, 'broken');
	assert.equal(skills[0].hasFrontmatter, false);
	assert.equal(skills[0].description, '');

	fs.rmSync(root, { recursive: true, force: true });
});

test('parseSkillFrontmatter: extracts name and description', () => {
	const fm = parseSkillFrontmatter('---\nname: foo\ndescription: "quoted desc"\n---\nbody');
	assert.equal(fm.name, 'foo');
	assert.equal(fm.description, 'quoted desc');
});

test('parseSkillFrontmatter: returns empty when no frontmatter', () => {
	const fm = parseSkillFrontmatter('no frontmatter here');
	assert.deepEqual(fm, {});
});

test('sorted output: skills come back alphabetically', () => {
	const root = tempRoot('sort');
	mkSkill(root, 'zebra', 'name: zebra\ndescription: z');
	mkSkill(root, 'alpha', 'name: alpha\ndescription: a');
	mkSkill(root, 'mango', 'name: mango\ndescription: m');

	const skills = loadSkillsFromFilesystem({ localPaths: [], globalPaths: [root] });
	assert.deepEqual(skills.map(s => s.name), ['alpha', 'mango', 'zebra']);

	fs.rmSync(root, { recursive: true, force: true });
});
