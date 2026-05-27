import * as vscode from 'vscode';
import * as path from 'path';
import { CLAUDE_SKILLS_DIR } from '../constants';
import { loadSkillsFromFilesystem, SkillInfo } from './skill-loader';

let outputChannel: vscode.OutputChannel | undefined;

function getOutputChannel(): vscode.OutputChannel {
	if (!outputChannel) {
		outputChannel = vscode.window.createOutputChannel('SpecBox');
	}
	return outputChannel;
}

export class SkillsTreeProvider implements vscode.TreeDataProvider<vscode.TreeItem> {
	private _onDidChangeTreeData = new vscode.EventEmitter<vscode.TreeItem | undefined>();
	readonly onDidChangeTreeData = this._onDidChangeTreeData.event;
	private cachedSkills: SkillInfo[] | null = null;

	constructor(private workspaceFolders: string[] = []) {}

	refresh(): void {
		this.cachedSkills = null;
		this._onDidChangeTreeData.fire(undefined);
	}

	getTreeItem(element: vscode.TreeItem): vscode.TreeItem {
		return element;
	}

	getLoadedSkills(): SkillInfo[] {
		if (this.cachedSkills === null) {
			const localPaths = this.workspaceFolders.map(f => path.join(f, '.claude', 'skills'));
			this.cachedSkills = loadSkillsFromFilesystem({
				localPaths,
				globalPaths: [CLAUDE_SKILLS_DIR],
				onError: (err, p) => {
					getOutputChannel().appendLine(`[skills-tree] Failed to read ${p}: ${err instanceof Error ? err.stack ?? err.message : String(err)}`);
				},
			});
		}
		return this.cachedSkills;
	}

	async getChildren(): Promise<vscode.TreeItem[]> {
		const skills = this.getLoadedSkills();
		if (skills.length === 0) {
			return [new EmptyStateItem()];
		}
		return skills.map(s => new SkillItem(s));
	}
}

class SkillItem extends vscode.TreeItem {
	constructor(public readonly skill: SkillInfo) {
		super(`/${skill.name}`, vscode.TreeItemCollapsibleState.None);
		this.description = skill.description || '(no description)';
		this.iconPath = new vscode.ThemeIcon('extensions');
		const tooltip = new vscode.MarkdownString();
		tooltip.appendMarkdown(`**\`/${skill.name}\`** — ${skill.description || '(no description available)'}`);
		this.tooltip = tooltip;
		this.contextValue = 'specboxSkill';
	}
}

class EmptyStateItem extends vscode.TreeItem {
	constructor() {
		super('No skills detected — run /install or check ~/.claude/skills/', vscode.TreeItemCollapsibleState.None);
		this.iconPath = new vscode.ThemeIcon('warning');
		this.contextValue = 'specboxNoSkills';
	}
}
