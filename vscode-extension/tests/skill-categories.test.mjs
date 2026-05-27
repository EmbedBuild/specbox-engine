// UC-702 / AC-05, AC-07, AC-09 — skill-categories pure-function tests.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import Module from 'node:module';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.resolve(__dirname, '..', 'out');
const require = createRequire(import.meta.url);

const vscodeStub = { l10n: { t: (s) => s } };
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function (req, ...rest) {
	if (req === 'vscode') { return 'vscode-stub'; }
	return originalResolve.call(this, req, ...rest);
};
require.cache['vscode-stub'] = { id: 'vscode-stub', filename: 'vscode-stub', loaded: true, exports: vscodeStub };

const { getCategoryFor, CATEGORY_ORDER, CATEGORY_LABELS, CATEGORY_ICONS } = require(path.join(outDir, 'views', 'skill-categories.js'));
const { KNOWN_SKILLS } = require(path.join(outDir, 'constants.js'));

const CANONICAL_SKILLS = {
	pipeline: ['prd', 'plan', 'implement', 'feedback'],
	quality: ['audit', 'compliance', 'quality-gate', 'acceptance-check'],
	visual: ['visual-setup', 'adapt-ui', 'check-designs'],
	tracking: ['switch-backend', 'app-init', 'app-sync', 'queue-review'],
	stripe: ['stripe-connect', 'stripe-standard', 'stripe-switch-account'],
	lifecycle: ['release', 'handoff', 'discovery', 'quickstart', 'manual-test', 'optimize-agents', 'explore'],
};

test('AC-05: CATEGORY_ORDER is the 7 canonical categories in the fixed order', () => {
	assert.deepEqual([...CATEGORY_ORDER], [
		'pipeline', 'quality', 'visual', 'tracking', 'stripe', 'lifecycle', 'other',
	]);
});

test('AC-06: every category has a label and a ThemeIcon name', () => {
	for (const cat of CATEGORY_ORDER) {
		assert.ok(CATEGORY_LABELS[cat], `Missing label for ${cat}`);
		assert.ok(CATEGORY_ICONS[cat], `Missing icon for ${cat}`);
	}
	// Specific icon assignments per PRD AC-02
	assert.equal(CATEGORY_ICONS.pipeline, 'rocket');
	assert.equal(CATEGORY_ICONS.quality, 'shield');
	assert.equal(CATEGORY_ICONS.visual, 'paintcan');
	assert.equal(CATEGORY_ICONS.tracking, 'list-tree');
	assert.equal(CATEGORY_ICONS.stripe, 'credit-card');
	assert.equal(CATEGORY_ICONS.lifecycle, 'tools');
	assert.equal(CATEGORY_ICONS.other, 'question');
});

test('AC-07: unknown skills fall back to "other"', () => {
	assert.equal(getCategoryFor('totally-unknown-skill'), 'other');
	assert.equal(getCategoryFor('foo'), 'other');
	assert.equal(getCategoryFor(''), 'other');
});

test('AC-09: each canonical skill maps to its expected category', () => {
	for (const [category, skills] of Object.entries(CANONICAL_SKILLS)) {
		for (const skill of skills) {
			assert.equal(
				getCategoryFor(skill), category,
				`Expected ${skill} → ${category}, got ${getCategoryFor(skill)}`,
			);
		}
	}
});

test('drift detector: every KNOWN_SKILL maps to a non-"other" category', () => {
	const drifted = KNOWN_SKILLS.filter(s => getCategoryFor(s) === 'other');
	assert.deepEqual(drifted, [],
		`Skills in KNOWN_SKILLS but not in SKILL_TO_CATEGORY mapping: ${drifted.join(', ')}`);
});
