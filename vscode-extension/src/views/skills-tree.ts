import * as vscode from 'vscode';
import { CORE_SKILLS } from '../constants';
import { InstallManager } from '../install';

const SKILL_DESCRIPTIONS: Record<string, string> = {
	'prd': 'Generate Product Requirements Documents',
	'plan': 'Technical implementation plans + Stitch designs',
	'implement': 'Autopilot end-to-end implementation',
	'adapt-ui': 'Scan project UI components',
	'optimize-agents': 'Audit and optimize agent system',
	'quality-gate': 'Adaptive quality gates with evidence',
	'explore': 'Read-only codebase analysis',
	'feedback': 'Capture developer testing feedback',
	'check-designs': 'Retroactive Stitch design compliance',
	'visual-setup': 'Brand kit + design system setup',
	'acceptance-check': 'Standalone BDD acceptance validation',
	'quickstart': 'Interactive onboarding tutorial',
	'remote': 'Remote project management',
	'release': 'Audit, clean, and release new version',
	'compliance': 'SpecBox compliance audit + auto-fix',
};

export class SkillsTreeProvider implements vscode.TreeDataProvider<SkillItem> {
	private _onDidChangeTreeData = new vscode.EventEmitter<SkillItem | undefined>();
	readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

	constructor(private installer: InstallManager) {}

	refresh(): void {
		this._onDidChangeTreeData.fire(undefined);
	}

	getTreeItem(element: SkillItem): vscode.TreeItem {
		return element;
	}

	async getChildren(): Promise<SkillItem[]> {
		const installed = new Set(this.installer.getInstalledSkills());
		return CORE_SKILLS.map(name => new SkillItem(
			name,
			installed.has(name),
			SKILL_DESCRIPTIONS[name] ?? ''
		));
	}
}

class SkillItem extends vscode.TreeItem {
	constructor(name: string, installed: boolean, description: string) {
		super(`/${name}`, vscode.TreeItemCollapsibleState.None);
		this.description = description;
		this.iconPath = new vscode.ThemeIcon(installed ? 'check' : 'circle-slash');
		this.tooltip = installed
			? `/${name} — installed and ready`
			: `/${name} — not installed. Run "SpecBox: Install Engine" to install.`;
	}
}
