import * as path from 'path';
import * as os from 'os';

export const CLAUDE_DIR = path.join(os.homedir(), '.claude');
export const CLAUDE_SKILLS_DIR = path.join(CLAUDE_DIR, 'skills');
export const CLAUDE_HOOKS_DIR = path.join(CLAUDE_DIR, 'hooks');
export const CLAUDE_HOOKS_LIB_DIR = path.join(CLAUDE_HOOKS_DIR, 'lib');
export const CLAUDE_COMMANDS_DIR = path.join(CLAUDE_DIR, 'commands');
export const CLAUDE_SETTINGS = path.join(CLAUDE_DIR, 'settings.json');
export const CLAUDE_SETTINGS_LOCAL = path.join(CLAUDE_DIR, 'settings.local.json');

export const CORE_SKILLS = [
	'prd', 'plan', 'implement', 'adapt-ui', 'optimize-agents',
	'quality-gate', 'explore', 'feedback', 'check-designs',
	'visual-setup', 'acceptance-check', 'quickstart', 'remote',
	'release', 'compliance'
];

export const REQUIRED_NODE_VERSION = 18;
export const REQUIRED_PYTHON_VERSION = '3.12';
