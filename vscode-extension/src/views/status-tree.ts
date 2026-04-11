import * as vscode from 'vscode';
import { HealthChecker, HealthResult } from '../health';

export class StatusTreeProvider implements vscode.TreeDataProvider<StatusItem> {
	private _onDidChangeTreeData = new vscode.EventEmitter<StatusItem | undefined>();
	readonly onDidChangeTreeData = this._onDidChangeTreeData.event;
	private cachedResult: HealthResult | null = null;
	private cacheTime = 0;
	private static readonly CACHE_TTL_MS = 10_000; // 10s — prevents duplicate checks on rapid UI events

	constructor(private health: HealthChecker) {}

	refresh(): void {
		this.cachedResult = null;
		this.cacheTime = 0;
		this._onDidChangeTreeData.fire(undefined);
	}

	getTreeItem(element: StatusItem): vscode.TreeItem {
		return element;
	}

	async getChildren(): Promise<StatusItem[]> {
		const now = Date.now();
		if (!this.cachedResult || (now - this.cacheTime) > StatusTreeProvider.CACHE_TTL_MS) {
			this.cachedResult = await this.health.run();
			this.cacheTime = now;
		}
		const r = this.cachedResult;

		return [
			new StatusItem(
				`Engine: ${r.engineInstalled ? `v${r.engineVersion}` : 'Not installed'}`,
				r.engineInstalled ? 'pass' : 'fail'
			),
			new StatusItem(`Node.js: ${r.node.version ?? 'Missing'}`, r.node.ok ? 'pass' : 'fail'),
			new StatusItem(`Python: ${r.python.version ?? 'Missing'}`, r.python.ok ? 'pass' : 'fail'),
			new StatusItem(`Claude Code: ${r.claudeCode.version ?? 'Missing'}`, r.claudeCode.ok ? 'pass' : 'fail'),
			new StatusItem(`Engram: ${r.engram.version ?? 'Not installed'}`, r.engram.ok ? 'pass' : 'fail'),
			new StatusItem(`GGA: ${r.gga.version ?? 'Not installed'}`, r.gga.ok ? 'pass' : 'info'),
			new StatusItem(
				`Skills: ${r.skills.installed.length}/${r.skills.installed.length + r.skills.missing.length}`,
				r.skills.missing.length === 0 ? 'pass' : 'warn'
			),
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
