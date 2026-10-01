import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import { InstallManager } from './install';
import { McpConfigurator } from './mcp';
import { HealthChecker } from './health';
import { exec } from './util';
import { markDone } from './design';

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
		const startSetup = vscode.l10n.t('Start Setup');
		const proceed = await vscode.window.showInformationMessage(
			vscode.l10n.t('Welcome to SpecBox Engine! This wizard will set up everything you need for agentic development with Claude Code.'),
			{ modal: true, detail: this.prerequisiteSummary(initial) },
			startSetup
		);
		if (proceed !== startSetup) { return; }

		// Step 2: Locate or clone engine
		const enginePath = await this.installer.resolveEnginePath();
		if (!enginePath) {
			const cloneFromGithub = vscode.l10n.t('Clone from GitHub');
			const action = await vscode.window.showErrorMessage(
				vscode.l10n.t('SpecBox Engine repository not found.'),
				cloneFromGithub, vscode.l10n.t('Cancel')
			);
			if (action === cloneFromGithub) {
				await this.cloneEngine();
			}
			return;
		}

		// Step 3: Install skills + hooks + settings
		await vscode.window.withProgress({
			location: vscode.ProgressLocation.Notification,
			title: vscode.l10n.t('SpecBox: Installing engine components...'),
		}, async () => {
			await this.installer.runFullInstall();
		});

		// Step 4: Configure MCP servers
		const configure = vscode.l10n.t('Configure');
		const configureMcp = await vscode.window.showInformationMessage(
			vscode.l10n.t('Engine installed. Now configure MCP servers (SpecBox + Engram) for Claude Code?'),
			configure, vscode.l10n.t('Skip')
		);
		if (configureMcp === configure) {
			await this.mcp.configureAll();
		}

		// Step 5: Final health check + summary
		const final = await health.run();
		this.showSummary(final);
	}

	private prerequisiteSummary(h: {
		node: { ok: boolean; version: string | null };
		claudeCode: { ok: boolean; version: string | null };
		engram: { ok: boolean; version: string | null };
	}): string {
		// The state as a word with the system's terminal box ([x] / [ ]), like the diagnostics.
		const check = (ok: boolean) => ok ? `[x] ${vscode.l10n.t('OK')}` : `[ ] ${vscode.l10n.t('Missing')}`;
		return [
			`Node.js: ${check(h.node.ok)} ${h.node.version ?? ''}`,
			`Claude Code: ${check(h.claudeCode.ok)} ${h.claudeCode.version ?? ''}`,
			`Engram: ${check(h.engram.ok)} ${h.engram.version ?? ''}`,
			'',
			vscode.l10n.t('The wizard will install what it can and guide you for the rest.'),
		].join('\n');
	}

	private async cloneEngine(): Promise<void> {
		const home = os.homedir();
		const targetDir = path.join(home, 'specbox-engine');

		if (fs.existsSync(path.join(targetDir, 'ENGINE_VERSION.yaml'))) {
			vscode.window.showInformationMessage(vscode.l10n.t('SpecBox Engine already exists at {0}', '~/specbox-engine'));
			return;
		}

		const cloned = await vscode.window.withProgress({
			location: vscode.ProgressLocation.Notification,
			title: vscode.l10n.t('SpecBox: Cloning repository...'),
			cancellable: false,
		}, async (progress) => {
			progress.report({ message: vscode.l10n.t('git clone in progress...') });
			const result = await exec(
				`git clone https://github.com/EmbedBuild/specbox-engine.git "${targetDir}"`,
				home
			);
			return result !== null;
		});

		if (cloned && fs.existsSync(path.join(targetDir, 'ENGINE_VERSION.yaml'))) {
			await vscode.workspace.getConfiguration('specbox').update('enginePath', targetDir, vscode.ConfigurationTarget.Global);
			const install = vscode.l10n.t('Install');
			const action = await vscode.window.showInformationMessage(
				markDone(vscode.l10n.t('SpecBox Engine cloned. Install now?')),
				install, vscode.l10n.t('Later')
			);
			if (action === install) {
				await vscode.commands.executeCommand('specbox.install');
			}
		} else {
			vscode.window.showErrorMessage(vscode.l10n.t('Clone failed. Check your network connection and try again.'));
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
			lines.push(markDone(vscode.l10n.t('SpecBox Engine v{0} installed', h.engineVersion ?? '')));
		}
		lines.push(markDone(vscode.l10n.t('Skills: {0} installed', h.skills.installed.length)));
		lines.push(markDone(vscode.l10n.t('Hooks: {0} active', h.hooks.count)));

		const warnings: string[] = [];
		if (!h.mcpSpecbox.configured) { warnings.push(vscode.l10n.t('SpecBox MCP not configured')); }
		if (!h.mcpEngram.configured) { warnings.push(vscode.l10n.t('Engram MCP not configured')); }
		if (!h.engram.ok) { warnings.push(vscode.l10n.t('Engram not installed')); }

		if (warnings.length > 0) {
			lines.push(...warnings.map((w) => `[ ] ${w}`));
		} else {
			lines.push(markDone(vscode.l10n.t('All systems operational. You can now use /prd, /plan, /implement in Claude Code.')));
		}

		if (warnings.length > 0) {
			vscode.window.showWarningMessage(lines.join(' | '));
		} else {
			vscode.window.showInformationMessage(lines.join(' | '));
		}
	}
}
