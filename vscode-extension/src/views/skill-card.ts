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

const PLACEHOLDER_CONTENT: SkillDefaults = {
	whatItDoes: '(no description available)',
	whenToUse: ['(consult the SKILL.md or run /compliance to verify the skill is correctly installed)'],
	command: '/<skill>',
	example: '(no example available)',
};

export function buildSkillCardContent(skill: SkillInfo): SkillCardContent {
	const defaults = SKILL_DEFAULTS[skill.name];
	if (defaults) {
		return { name: skill.name, ...defaults, source: 'defaults' };
	}

	// No static defaults — fall through to a placeholder. We could try to parse
	// the SKILL.md frontmatter more aggressively, but the description field
	// today is a single sentence not a 4-block structure. Show a graceful
	// placeholder labeled 'placeholder' so users see what's missing.
	if (skill.hasFrontmatter && skill.description) {
		return {
			name: skill.name,
			whatItDoes: skill.description,
			whenToUse: PLACEHOLDER_CONTENT.whenToUse,
			command: `/${skill.name}`,
			example: PLACEHOLDER_CONTENT.example,
			source: 'skill-md',
		};
	}
	return { name: skill.name, ...PLACEHOLDER_CONTENT, source: 'placeholder' };
}

const SOURCE_LABEL: Record<SkillCardContent['source'], string> = {
	'skill-md': 'Source: SKILL.md frontmatter',
	'defaults': 'Source: extension defaults',
	'placeholder': 'Source: placeholder (no SKILL.md description, no static default)',
};

export function buildSkillCardItems(content: SkillCardContent): vscode.QuickPickItem[] {
	const copyButton: vscode.QuickInputButton = {
		iconPath: new vscode.ThemeIcon('copy'),
		tooltip: vscode.l10n.t('Copy command to clipboard'),
	};

	return [
		{
			label: '$(info) What it does',
			detail: content.whatItDoes,
			alwaysShow: true,
		},
		{
			label: '$(question) When to use it',
			detail: content.whenToUse.map(line => `• ${line}`).join('\n'),
			alwaysShow: true,
		},
		{
			label: '$(terminal) Command',
			detail: content.command,
			buttons: [copyButton],
			alwaysShow: true,
		},
		{
			label: '$(beaker) Example',
			detail: content.example,
			alwaysShow: true,
		},
		{
			label: '',
			kind: vscode.QuickPickItemKind.Separator,
		},
		{
			label: `$(file) ${SOURCE_LABEL[content.source]}`,
			alwaysShow: true,
		},
	];
}

export async function showSkillCard(skill: SkillInfo): Promise<void> {
	const content = buildSkillCardContent(skill);
	const items = buildSkillCardItems(content);

	const quickPick = vscode.window.createQuickPick();
	quickPick.title = `SpecBox skill: /${content.name}`;
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
