import * as vscode from 'vscode';
import * as path from 'path';
import { CLAUDE_SKILLS_DIR } from '../constants';
import { loadSkillsFromFilesystem, SkillInfo } from './skill-loader';
import {
	SkillCategory, CATEGORY_ORDER, CATEGORY_LABELS, CATEGORY_ICONS, getCategoryFor,
} from './skill-categories';

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
	private cachedByCategory: Map<SkillCategory, SkillInfo[]> | null = null;

	constructor(private workspaceFolders: string[] = []) {}

	refresh(): void {
		this.cachedSkills = null;
		this.cachedByCategory = null;
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

	private getSkillsByCategory(): Map<SkillCategory, SkillInfo[]> {
		if (this.cachedByCategory !== null) { return this.cachedByCategory; }
		const map = new Map<SkillCategory, SkillInfo[]>();
		for (const cat of CATEGORY_ORDER) { map.set(cat, []); }
		for (const skill of this.getLoadedSkills()) {
			const cat = getCategoryFor(skill.name);
			map.get(cat)!.push(skill);
		}
		this.cachedByCategory = map;
		return map;
	}

	async getChildren(element?: vscode.TreeItem): Promise<vscode.TreeItem[]> {
		const skills = this.getLoadedSkills();
		if (skills.length === 0) {
			return element ? [] : [new EmptyStateItem()];
		}

		if (!element) {
			// Root: 7 categorías en orden fijo, siempre visibles (incluso con count 0)
			const byCat = this.getSkillsByCategory();
			return CATEGORY_ORDER.map(cat => new SkillCategoryItem(cat, byCat.get(cat)!.length));
		}

		if (element instanceof SkillCategoryItem) {
			const byCat = this.getSkillsByCategory();
			return byCat.get(element.category)!.map(s => new SkillItem(s));
		}

		// Leaf items have no children
		return [];
	}
}

class SkillCategoryItem extends vscode.TreeItem {
	constructor(public readonly category: SkillCategory, public readonly count: number) {
		super(CATEGORY_LABELS[category], vscode.TreeItemCollapsibleState.Expanded);
		this.description = `(${count})`;
		this.iconPath = new vscode.ThemeIcon(CATEGORY_ICONS[category]);
		this.contextValue = 'specboxSkillCategory';
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
		this.command = {
			command: 'specbox.showSkillCard',
			arguments: [skill],
			title: vscode.l10n.t('Show skill card'),
		};
	}
}

class EmptyStateItem extends vscode.TreeItem {
	constructor() {
		super('No skills detected — run /install or check ~/.claude/skills/', vscode.TreeItemCollapsibleState.None);
		this.iconPath = new vscode.ThemeIcon('warning');
		this.contextValue = 'specboxNoSkills';
	}
}

export { SkillCategoryItem, SkillItem, EmptyStateItem };
