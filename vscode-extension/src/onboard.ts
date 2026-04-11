import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import { InstallManager } from './install';
import { McpConfigurator } from './mcp';
import { HealthChecker } from './health';
import { exec } from './util';

/**
 * Step-by-step onboarding wizard using native VSCode UI (no webview).
 * Guides new users through the full SpecBox Engine setup.
 */
export class OnboardWizard {
	constructor(
		private context: vscode.ExtensionContext,
		private installer: InstallManager,
		private mcp: McpConfigurator,
	) {}

	async start(): Promise<void> {
		const health = new HealthChecker();
		const initial = await health.run();

		// Step 1: Welcome + Prerequisites
		const proceed = await vscode.window.showInformationMessage(
			'Welcome to SpecBox Engine! This wizard will set up everything you need for agentic development with Claude Code.',
			{ modal: true, detail: this.prerequisiteSummary(initial) },
			'Start Setup'
		);
		if (proceed !== 'Start Setup') { return; }

		// Step 2: Locate or clone engine
		const enginePath = await this.installer.resolveEnginePath();
		if (!enginePath) {
			const action = await vscode.window.showErrorMessage(
				'SpecBox Engine repository not found.',
				'Clone from GitHub', 'Cancel'
			);
			if (action === 'Clone from GitHub') {
				await this.cloneEngine();
			}
			return;
		}

		// Step 3: Install skills + hooks + settings
		await vscode.window.withProgress({
			location: vscode.ProgressLocation.Notification,
			title: 'SpecBox: Installing engine components...',
		}, async () => {
			await this.installer.runFullInstall();
		});

		// Step 4: Configure MCP servers
		const configureMcp = await vscode.window.showInformationMessage(
			'Engine installed. Now configure MCP servers (SpecBox + Engram) for Claude Code?',
			'Configure', 'Skip'
		);
		if (configureMcp === 'Configure') {
			await this.mcp.configureAll();
		}

		// Step 5: Final health check + summary
		const final = await health.run();
		this.showSummary(final);
	}

	private prerequisiteSummary(h: {
		node: { ok: boolean; version: string | null };
		python: { ok: boolean; version: string | null };
		claudeCode: { ok: boolean; version: string | null };
		engram: { ok: boolean; version: string | null };
	}): string {
		const check = (ok: boolean) => ok ? 'OK' : 'MISSING';
		return [
			`Node.js: ${check(h.node.ok)} ${h.node.version ?? ''}`,
			`Python 3.12+: ${check(h.python.ok)} ${h.python.version ?? ''}`,
			`Claude Code: ${check(h.claudeCode.ok)} ${h.claudeCode.version ?? ''}`,
			`Engram: ${check(h.engram.ok)} ${h.engram.version ?? ''}`,
			'',
			'The wizard will install what it can and guide you for the rest.',
		].join('\n');
	}

	private async cloneEngine(): Promise<void> {
		const home = os.homedir();
		const targetDir = path.join(home, 'specbox-engine');

		if (fs.existsSync(path.join(targetDir, 'ENGINE_VERSION.yaml'))) {
			vscode.window.showInformationMessage('SpecBox Engine already exists at ~/specbox-engine');
			return;
		}

		const cloned = await vscode.window.withProgress({
			location: vscode.ProgressLocation.Notification,
			title: 'SpecBox: Cloning repository...',
			cancellable: false,
		}, async (progress) => {
			progress.report({ message: 'git clone in progress...' });
			const result = await exec(
				`git clone https://github.com/jpsdeveloper/specbox-engine.git "${targetDir}"`,
				home
			);
			return result !== null;
		});

		if (cloned && fs.existsSync(path.join(targetDir, 'ENGINE_VERSION.yaml'))) {
			await vscode.workspace.getConfiguration('specbox').update('enginePath', targetDir, vscode.ConfigurationTarget.Global);
			const action = await vscode.window.showInformationMessage(
				'SpecBox Engine cloned successfully. Install now?',
				'Install', 'Later'
			);
			if (action === 'Install') {
				await vscode.commands.executeCommand('specbox.install');
			}
		} else {
			vscode.window.showErrorMessage('Clone failed. Check your network connection and try again.');
		}
	}

	private showSummary(h: {
		engineInstalled: boolean;
		engineVersion: string | null;
		skills: { installed: string[]; missing: string[] };
		hooks: { count: number };
		mcpSpecbox: { configured: boolean };
		mcpEngram: { configured: boolean };
		engram: { ok: boolean };
	}): void {
		const lines: string[] = [];
		if (h.engineInstalled) {
			lines.push(`SpecBox Engine v${h.engineVersion} installed successfully!`);
		}
		lines.push(`Skills: ${h.skills.installed.length} installed`);
		lines.push(`Hooks: ${h.hooks.count} active`);

		const warnings: string[] = [];
		if (!h.mcpSpecbox.configured) { warnings.push('MCP SpecBox not configured'); }
		if (!h.mcpEngram.configured) { warnings.push('MCP Engram not configured'); }
		if (!h.engram.ok) { warnings.push('Engram not installed'); }

		if (warnings.length > 0) {
			lines.push(`\nAction needed: ${warnings.join(', ')}`);
		} else {
			lines.push('\nAll systems operational. You can now use /prd, /plan, /implement in Claude Code.');
		}

		if (warnings.length > 0) {
			vscode.window.showWarningMessage(lines.join(' | '));
		} else {
			vscode.window.showInformationMessage(lines.join(' | '));
		}
	}
}
