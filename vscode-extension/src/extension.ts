import * as vscode from 'vscode';
import { InstallManager } from './install';
import { HealthChecker } from './health';
import { StatusBarManager } from './statusbar';
import { OnboardWizard } from './onboard';
import { McpConfigurator } from './mcp';
import { ExtensionUpdater } from './updater';
import { StatusTreeProvider } from './views/status-tree';
import { SkillsTreeProvider } from './views/skills-tree';

let statusBar: StatusBarManager | undefined;

export async function activate(context: vscode.ExtensionContext) {
	const installer = new InstallManager(context);
	const health = new HealthChecker();
	const mcpConfig = new McpConfigurator();

	// Status bar — created early, added to subscriptions for auto-disposal
	statusBar = new StatusBarManager();
	context.subscriptions.push(statusBar.item);

	// Tree views
	const statusTree = new StatusTreeProvider(health);
	const skillsTree = new SkillsTreeProvider(installer);
	vscode.window.registerTreeDataProvider('specbox.status', statusTree);
	vscode.window.registerTreeDataProvider('specbox.skills', skillsTree);

	// Commands
	context.subscriptions.push(
		vscode.commands.registerCommand('specbox.install', async () => {
			await installer.runFullInstall();
			const result = await health.run();
			statusTree.refresh();
			skillsTree.refresh();
			statusBar?.update(result);
			await vscode.commands.executeCommand('setContext', 'specbox.installed', result.engineInstalled);
		}),

		vscode.commands.registerCommand('specbox.healthCheck', async () => {
			const result = await health.run();
			statusBar?.update(result);
			statusTree.refresh();
			health.showReport(result);
		}),

		vscode.commands.registerCommand('specbox.onboard', async () => {
			const wizard = new OnboardWizard(context, installer, mcpConfig);
			await wizard.start();
		}),

		vscode.commands.registerCommand('specbox.showStatus', async () => {
			const result = await health.run();
			health.showReport(result);
		}),

		vscode.commands.registerCommand('specbox.openDashboard', () => {
			const url = vscode.workspace.getConfiguration('specbox').get<string>('dashboardUrl') || 'http://localhost:8080';
			vscode.env.openExternal(vscode.Uri.parse(url));
		}),

		vscode.commands.registerCommand('specbox.configureMcp', async () => {
			await mcpConfig.configureAll();
		}),
	);

	// Auto health check on startup
	const config = vscode.workspace.getConfiguration('specbox');
	if (config.get<boolean>('autoHealthCheck', true)) {
		const result = await health.run();
		statusBar.update(result);

		// Set context for welcome views
		await vscode.commands.executeCommand('setContext', 'specbox.installed', result.engineInstalled);

		if (!result.engineInstalled) {
			const action = await vscode.window.showInformationMessage(
				'SpecBox Engine detected but not installed. Run the setup wizard?',
				'Run Wizard',
				'Install Now',
				'Later'
			);
			if (action === 'Run Wizard') {
				await vscode.commands.executeCommand('specbox.onboard');
			} else if (action === 'Install Now') {
				await vscode.commands.executeCommand('specbox.install');
			}
		}

		// Self-update check: compare extension version vs engine version
		if (result.enginePath) {
			const extVersion = context.extension.packageJSON.version as string;
			const updater = new ExtensionUpdater(extVersion);
			await updater.checkAndUpdate(result.enginePath);
		}
	}
}

export function deactivate() {
	// StatusBarItem is disposed via context.subscriptions
	statusBar = undefined;
}
