import * as path from 'path';
import * as os from 'os';

export const CLAUDE_DIR = path.join(os.homedir(), '.claude');
export const CLAUDE_SKILLS_DIR = path.join(CLAUDE_DIR, 'skills');
export const CLAUDE_HOOKS_DIR = path.join(CLAUDE_DIR, 'hooks');
export const CLAUDE_HOOKS_LIB_DIR = path.join(CLAUDE_HOOKS_DIR, 'lib');
export const CLAUDE_COMMANDS_DIR = path.join(CLAUDE_DIR, 'commands');
export const CLAUDE_SETTINGS = path.join(CLAUDE_DIR, 'settings.json');
export const CLAUDE_SETTINGS_LOCAL = path.join(CLAUDE_DIR, 'settings.local.json');

// Canonical list of SpecBox engine skills. Used as the categorization source
// of truth (every entry here must be mapped in skill-categories.ts) and as a
// drift detector in tests. The runtime sidebar reads skills from the filesystem
// via skill-loader.ts — this array is NOT the source of truth for what the
// TreeView displays.
export const KNOWN_SKILLS = [
	'acceptance-check', 'adapt-ui', 'app-init', 'app-sync', 'audit',
	'check-designs', 'compliance', 'discovery', 'explore', 'feedback',
	'handoff', 'implement', 'manual-test', 'optimize-agents', 'plan',
	'prd', 'quality-gate', 'queue-review', 'quickstart', 'release',
	'stripe-connect', 'stripe-standard', 'stripe-switch-account',
	'switch-backend', 'visual-setup',
];

export const REQUIRED_NODE_VERSION = 18;
export const REQUIRED_PYTHON_VERSION = '3.12';
