import * as vscode from 'vscode';
import { SkillInfo } from './skill-loader';
import { SKILL_DEFAULTS, SkillDefaults } from './skill-defaults';

export interface SkillCardContent {
	name: string;
	whatItDoes: string;
	whenToUse: string[];
	command: string;
	example: string;
	source: 'skill-md' | 'defaults' | 'placeholder';
}

// The card's own words go through l10n.t when the card is built. The skill content
// (SKILL_DEFAULTS, the SKILL.md description) is the skill's documentation and stays
// as written.
function placeholderContent(): SkillDefaults {
	return {
		whatItDoes: vscode.l10n.t('(no description available)'),
		whenToUse: [vscode.l10n.t('(consult the SKILL.md or run /compliance to verify the skill is correctly installed)')],
		command: '/<skill>',
		example: vscode.l10n.t('(no example available)'),
	};
}

export function buildSkillCardContent(skill: SkillInfo): SkillCardContent {
	const defaults = SKILL_DEFAULTS[skill.name];
	if (defaults) {
		return { name: skill.name, ...defaults, source: 'defaults' };
	}

	// No static defaults — fall through to a placeholder. We could try to parse
	// the SKILL.md frontmatter more aggressively, but the description field
	// today is a single sentence not a 4-block structure. Show a graceful
	// placeholder labeled 'placeholder' so users see what's missing.
	const placeholder = placeholderContent();
	if (skill.hasFrontmatter && skill.description) {
		return {
			name: skill.name,
			whatItDoes: skill.description,
			whenToUse: placeholder.whenToUse,
			command: `/${skill.name}`,
			example: placeholder.example,
			source: 'skill-md',
		};
	}
	return { name: skill.name, ...placeholder, source: 'placeholder' };
}

function sourceLabel(source: SkillCardContent['source']): string {
	switch (source) {
		case 'skill-md': return vscode.l10n.t('Source: SKILL.md frontmatter');
		case 'defaults': return vscode.l10n.t('Source: extension defaults');
		case 'placeholder': return vscode.l10n.t('Source: placeholder (no SKILL.md description, no static default)');
	}
}

export function buildSkillCardItems(content: SkillCardContent): vscode.QuickPickItem[] {
	const copyButton: vscode.QuickInputButton = {
		iconPath: new vscode.ThemeIcon('copy'),
		tooltip: vscode.l10n.t('Copy command to clipboard'),
	};

	return [
		{
			label: `$(info) ${vscode.l10n.t('What it does')}`,
			detail: content.whatItDoes,
			alwaysShow: true,
		},
		{
			label: `$(question) ${vscode.l10n.t('When to use it')}`,
			detail: content.whenToUse.map(line => `• ${line}`).join('\n'),
			alwaysShow: true,
		},
		{
			label: `$(terminal) ${vscode.l10n.t('Command')}`,
			detail: content.command,
			buttons: [copyButton],
			alwaysShow: true,
		},
		{
			label: `$(beaker) ${vscode.l10n.t('Example')}`,
			detail: content.example,
			alwaysShow: true,
		},
		{
			label: '',
			kind: vscode.QuickPickItemKind.Separator,
		},
		{
			label: `$(file) ${sourceLabel(content.source)}`,
			alwaysShow: true,
		},
	];
}

export async function showSkillCard(skill: SkillInfo): Promise<void> {
	const content = buildSkillCardContent(skill);
	const items = buildSkillCardItems(content);

	const quickPick = vscode.window.createQuickPick();
	quickPick.title = vscode.l10n.t('SpecBox skill: /{0}', content.name);
	quickPick.placeholder = vscode.l10n.t('Press Esc to close. Click the copy icon to copy the command.');
	quickPick.items = items;
	quickPick.canSelectMany = false;
	quickPick.matchOnDescription = false;
	quickPick.matchOnDetail = false;

	const disposables: vscode.Disposable[] = [];
	disposables.push(quickPick.onDidTriggerItemButton(async (e) => {
		await vscode.env.clipboard.writeText(content.command);
		vscode.window.setStatusBarMessage(
			vscode.l10n.t('Command copied — paste in the Claude Code chat'),
			3000,
		);
		quickPick.hide();
	}));
	disposables.push(quickPick.onDidHide(() => {
		quickPick.dispose();
		disposables.forEach(d => d.dispose());
	}));

	quickPick.show();
}
