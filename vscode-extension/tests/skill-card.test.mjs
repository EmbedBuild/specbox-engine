// UC-703 / AC-10..AC-13 — skill-card pure-function tests.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import Module from 'node:module';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.resolve(__dirname, '..', 'out');
const require = createRequire(import.meta.url);

class FakeThemeIcon {
	constructor(id) { this.id = id; }
}
const QuickPickItemKind = { Separator: -1, Default: 0 };
const vscodeStub = {
	l10n: { t: (s) => s },
	ThemeIcon: FakeThemeIcon,
	QuickPickItemKind,
	window: { createQuickPick: () => ({}) },
	env: { clipboard: { writeText: async () => undefined } },
};
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function (req, ...rest) {
	if (req === 'vscode') { return 'vscode-stub'; }
	return originalResolve.call(this, req, ...rest);
};
require.cache['vscode-stub'] = { id: 'vscode-stub', filename: 'vscode-stub', loaded: true, exports: vscodeStub };

const { buildSkillCardContent, buildSkillCardItems } = require(path.join(outDir, 'views', 'skill-card.js'));

const KNOWN_SKILL_INFO = {
	name: 'prd',
	description: 'Generate Product Requirements Documents...',
	source: 'global',
	skillMdPath: '/fake/path/prd/SKILL.md',
	hasFrontmatter: true,
};

const UNKNOWN_SKILL_INFO = {
	name: 'totally-custom-skill',
	description: 'A custom skill from a third party',
	source: 'local',
	skillMdPath: '/fake/path/custom/SKILL.md',
	hasFrontmatter: true,
};

const NO_DESC_SKILL_INFO = {
	name: 'silent-skill',
	description: '',
	source: 'global',
	skillMdPath: '/fake/path/silent/SKILL.md',
	hasFrontmatter: false,
};

test('AC-11a: known skill returns source="defaults"', () => {
	const content = buildSkillCardContent(KNOWN_SKILL_INFO);
	assert.equal(content.name, 'prd');
	assert.equal(content.source, 'defaults');
	assert.ok(content.whatItDoes.length > 0);
	assert.ok(Array.isArray(content.whenToUse));
	assert.ok(content.command.startsWith('/prd'));
	assert.ok(content.example.length > 0);
});

test('AC-11b: unknown skill with SKILL.md description returns source="skill-md"', () => {
	const content = buildSkillCardContent(UNKNOWN_SKILL_INFO);
	assert.equal(content.source, 'skill-md');
	assert.equal(content.whatItDoes, UNKNOWN_SKILL_INFO.description);
	assert.equal(content.command, '/totally-custom-skill');
});

test('AC-11c: skill with no description and no defaults returns source="placeholder"', () => {
	const content = buildSkillCardContent(NO_DESC_SKILL_INFO);
	assert.equal(content.source, 'placeholder');
	assert.equal(content.whatItDoes, '(no description available)');
	assert.equal(content.command, '/<skill>');
});

test('AC-10: buildSkillCardItems returns 6 items (4 blocks + separator + source)', () => {
	const content = buildSkillCardContent(KNOWN_SKILL_INFO);
	const items = buildSkillCardItems(content);
	assert.equal(items.length, 6);
});

test('AC-12: the "Command" item has exactly one button', () => {
	const content = buildSkillCardContent(KNOWN_SKILL_INFO);
	const items = buildSkillCardItems(content);
	const commandItem = items.find(i => typeof i.label === 'string' && i.label.includes('Command'));
	assert.ok(commandItem, 'No "Command" item found');
	assert.ok(Array.isArray(commandItem.buttons));
	assert.equal(commandItem.buttons.length, 1);
	assert.ok(commandItem.buttons[0].iconPath instanceof FakeThemeIcon);
	assert.equal(commandItem.buttons[0].iconPath.id, 'copy');
});

test('AC-10b: items include a separator', () => {
	const content = buildSkillCardContent(KNOWN_SKILL_INFO);
	const items = buildSkillCardItems(content);
	const sep = items.find(i => i.kind === QuickPickItemKind.Separator);
	assert.ok(sep, 'No separator item');
});

test('AC-11d: last item labels the content source', () => {
	const content = buildSkillCardContent(KNOWN_SKILL_INFO);
	const items = buildSkillCardItems(content);
	const lastLabel = items[items.length - 1].label;
	assert.ok(lastLabel.includes('Source'), `Expected "Source" footer, got: ${lastLabel}`);
});
