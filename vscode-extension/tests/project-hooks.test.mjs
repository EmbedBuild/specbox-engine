// UC-11201 — what "SpecBox: Update project hooks" shows before and after updating.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { describeStatus, modifiedHooks, summarizeUpdate } from '../out/project-hooks.js';

const t = (message, ...args) => message.replace(/\{(\d+)\}/g, (_, i) => String(args[Number(i)]));

const STATUS = {
	ok: true,
	version: '6.29.2',
	installed_version: '6.28.0',
	hooks: [
		{ path: 'pre-commit-lint.mjs', state: 'modified' },
		{ path: 'spec-guard.mjs', state: 'updatable' },
		{ path: 'freeform-fragment.mjs', state: 'missing' },
		{ path: 'quality-first-guard.mjs', state: 'current' },
	],
	settings_missing: [{ event: 'PreToolUse', matcher: 'mcp__SpecBox-MCP__.*', command: 'node .claude/hooks/freeform-fragment.mjs' }],
	differs: true,
};

test('AC-01: the list before updating names every hook that differs, and the settings to add', () => {
	assert.deepEqual(describeStatus(STATUS, t), [
		'pre-commit-lint.mjs — changed locally: left as is',
		'spec-guard.mjs — will be updated',
		'freeform-fragment.mjs — missing: will be installed',
		'.claude/settings.json: 1 hook registrations will be added',
	]);
});

test('AC-02: only the hooks changed locally are offered for replacement', () => {
	assert.deepEqual(modifiedHooks(STATUS), ['pre-commit-lint.mjs']);
});

test('the summary says what was written and where the new version of a kept hook is', () => {
	const text = summarizeUpdate(
		{ ok: true, version: '6.29.2', written: ['spec-guard.mjs', 'freeform-fragment.mjs'], kept: [{ path: 'pre-commit-lint.mjs', new: '.claude/hooks/pre-commit-lint.mjs.new' }], retired: [], settings_added: 1, settings_backup: '.claude/settings.json.bak' },
		t,
	);
	assert.equal(
		text,
		'Project hooks updated to SpecBox 6.29.2: 2 written. Kept your version of pre-commit-lint.mjs; the new one is next to it as .new. 1 hook registrations added to .claude/settings.json.',
	);
});
