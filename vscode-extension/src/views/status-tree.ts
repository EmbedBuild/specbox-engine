import * as vscode from 'vscode';
import { HealthChecker, HealthResult, specboxSkillsCount } from '../health';
import { SecretsManager } from '../secret-storage';

export interface IdentityState {
	signedIn: boolean;
	handle?: string;
}

export class StatusTreeProvider implements vscode.TreeDataProvider<vscode.TreeItem> {
	private _onDidChangeTreeData = new vscode.EventEmitter<vscode.TreeItem | undefined>();
	readonly onDidChangeTreeData = this._onDidChangeTreeData.event;
	private cachedResult: HealthResult | null = null;
	private cacheTime = 0;
	private identityState: IdentityState = { signedIn: false };
	private static readonly CACHE_TTL_MS = 10_000; // 10s — prevents duplicate checks on rapid UI events

	constructor(private health: HealthChecker, private secrets?: SecretsManager) {}

	updateIdentity(state: IdentityState): void {
		this.identityState = state;
		this._onDidChangeTreeData.fire(undefined);
	}

	refresh(): void {
		this.cachedResult = null;
		this.cacheTime = 0;
		this._onDidChangeTreeData.fire(undefined);
	}

	/** UC-9604 AC-04 — show a result already computed (the Health Check's), so both say the same. */
	show(result: HealthResult): void {
		this.cachedResult = result;
		this.cacheTime = Date.now();
		this._onDidChangeTreeData.fire(undefined);
	}

	getTreeItem(element: vscode.TreeItem): vscode.TreeItem {
		return element;
	}

	async getChildren(element?: vscode.TreeItem): Promise<vscode.TreeItem[]> {
		if (element instanceof SkillsStatusItem) { return element.children; }
		if (element) { return []; }
		const now = Date.now();
		if (!this.cachedResult || (now - this.cacheTime) > StatusTreeProvider.CACHE_TTL_MS) {
			this.cachedResult = await this.health.run();
			this.cacheTime = now;
		}
		const r = this.cachedResult;

		const identityItem = this.identityState.signedIn
			? new IdentityTreeItem(
				vscode.l10n.t('Signed in as @{0}', this.identityState.handle ?? '?'),
				'github-inverted'
			)
			: new IdentityTreeItem(
				vscode.l10n.t('Not signed in (FreeForm mode)'),
				'person'
			);

		return [
			identityItem,
			// UC-9604 — the engine is there when it was found; missing skills go in the Skills row.
			new StatusItem(
				`Engine: ${r.enginePath ? `v${r.engineVersion}` : vscode.l10n.t('Not installed')}`,
				r.enginePath ? 'pass' : 'fail'
			),
			new StatusItem(`Node.js: ${r.node.version ?? 'Missing'}`, r.node.ok ? 'pass' : 'fail'),
			new StatusItem(`Claude Code: ${r.claudeCode.version ?? 'Missing'}`, r.claudeCode.ok ? 'pass' : 'fail'),
			new StatusItem(`Engram: ${r.engram.version ?? 'Not installed'}`, r.engram.ok ? 'pass' : 'fail'),
			new StatusItem(`GGA: ${r.gga.version ?? 'Not installed'}`, r.gga.ok ? 'pass' : 'info'),
			new SkillsStatusItem(r),
			new StatusItem(`Hooks: ${r.hooks.count} installed`, r.hooks.ok ? 'pass' : 'warn'),
			new StatusItem(`MCP SpecBox: ${r.mcpSpecbox.configured ? 'Configured' : 'Not configured'}`, r.mcpSpecbox.configured ? 'pass' : 'fail'),
			new StatusItem(`MCP Engram: ${r.mcpEngram.configured ? 'Configured' : 'Not configured'}`, r.mcpEngram.configured ? 'pass' : 'fail'),
		];
	}
}

class StatusItem extends vscode.TreeItem {
	constructor(label: string, status: 'pass' | 'fail' | 'warn' | 'info') {
		super(label, vscode.TreeItemCollapsibleState.None);
		const icons: Record<string, string> = {
			pass: 'testing-passed-icon',
			fail: 'testing-failed-icon',
			warn: 'warning',
			info: 'info',
		};
		this.iconPath = new vscode.ThemeIcon(icons[status]);
	}
}

/**
 * UC-9604 — Skills with only the SpecBox count (0/26 … 26/26). With skills missing it unfolds into
 * their names and the action that puts them back.
 */
class SkillsStatusItem extends StatusItem {
	readonly children: vscode.TreeItem[];

	constructor(r: HealthResult) {
		super(`Skills: ${specboxSkillsCount(r)}`, r.skills.missing.length === 0 ? 'pass' : 'warn');
		const missing = r.skills.missing;
		this.children = missing.map((name) => {
			const item = new vscode.TreeItem(name, vscode.TreeItemCollapsibleState.None);
			item.iconPath = new vscode.ThemeIcon('circle-slash');
			return item;
		});
		if (missing.length > 0) {
			this.collapsibleState = vscode.TreeItemCollapsibleState.Collapsed;
			const action = new vscode.TreeItem(vscode.l10n.t('Run "SpecBox: Install Engine" to restore them'), vscode.TreeItemCollapsibleState.None);
			action.iconPath = new vscode.ThemeIcon('rocket');
			action.command = { command: 'specbox.install', title: vscode.l10n.t('Run "SpecBox: Install Engine" to restore them') };
			this.children.push(action);
		}
	}
}

export class IdentityTreeItem extends vscode.TreeItem {
	constructor(label: string, icon: 'github-inverted' | 'person') {
		super(label, vscode.TreeItemCollapsibleState.None);
		this.iconPath = new vscode.ThemeIcon(icon);
		this.command = { command: 'specbox.identityQuickPick', title: '' };
	}
}
