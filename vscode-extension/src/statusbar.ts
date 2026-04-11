import * as vscode from 'vscode';
import { HealthResult } from './health';

export class StatusBarManager {
	readonly item: vscode.StatusBarItem;

	constructor() {
		this.item = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 50);
		this.item.command = 'specbox.showStatus';
		this.item.text = '$(loading~spin) SpecBox';
		this.item.tooltip = 'SpecBox Engine — checking...';
		this.item.show();
	}

	update(health: HealthResult): void {
		if (!health.engineInstalled) {
			this.item.text = '$(warning) SpecBox';
			this.item.tooltip = 'SpecBox Engine — not installed. Click to run setup.';
			this.item.command = 'specbox.onboard';
			return;
		}

		const issues: string[] = [];
		if (!health.engram.ok) { issues.push('Engram missing'); }
		if (!health.mcpSpecbox.configured) { issues.push('MCP not configured'); }
		if (!health.mcpEngram.configured) { issues.push('Engram MCP not configured'); }
		if (!health.python.ok) { issues.push('Python 3.12+ missing'); }

		if (issues.length > 0) {
			this.item.text = `$(alert) SpecBox v${health.engineVersion}`;
			this.item.tooltip = `SpecBox Engine — Issues: ${issues.join(', ')}`;
			this.item.command = 'specbox.showStatus';
		} else {
			this.item.text = `$(check) SpecBox v${health.engineVersion}`;
			this.item.tooltip = 'SpecBox Engine — all systems operational';
			this.item.command = 'specbox.showStatus';
		}
	}

	dispose(): void {
		this.item.dispose();
	}
}
