// UC-1405 (US-14) — the rebuild never leaves the managed clone with a local change.
//
// AC-01: install-ext.mjs installs the dependencies with `npm ci` (or, if it cannot, without a
//        lock), so the versioned package-lock.json is never rewritten in the clone.
// AC-04: the versioned package-lock.json says the same as package.json (name, version and
//        licence). Its licence said MIT after the change to FSL-1.1-ALv2, and `npm install`
//        corrected it in every clone, which then could not move to the next release tag.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { DEPENDENCY_INSTALL_COMMANDS } from '../install-ext.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const pkg = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8'));
const lock = JSON.parse(fs.readFileSync(path.join(root, 'package-lock.json'), 'utf8'));

test('AC-04: the versioned lock matches package.json', () => {
	const rootPkg = lock.packages[''];
	assert.equal(lock.name, pkg.name);
	assert.equal(lock.version, pkg.version);
	assert.equal(rootPkg.name, pkg.name);
	assert.equal(rootPkg.version, pkg.version);
	assert.equal(rootPkg.license, pkg.license, 'npm install would rewrite the licence and dirty the managed clone');
	assert.deepEqual(rootPkg.devDependencies ?? {}, pkg.devDependencies ?? {});
	assert.deepEqual(rootPkg.dependencies ?? {}, pkg.dependencies ?? {});
});

test('AC-01: the rebuild installs dependencies without rewriting the lock', () => {
	assert.match(DEPENDENCY_INSTALL_COMMANDS[0], /^npm ci\b/);
	for (const cmd of DEPENDENCY_INSTALL_COMMANDS) {
		const writesLock = /^npm install\b/.test(cmd) && !/--package-lock=false|--no-package-lock/.test(cmd);
		assert.ok(!writesLock, `${cmd} would rewrite package-lock.json`);
	}
	const source = fs.readFileSync(path.join(root, 'install-ext.mjs'), 'utf8');
	assert.ok(!/run\('npm install'/.test(source), 'no bare npm install left in the rebuild');
});
