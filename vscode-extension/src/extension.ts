import * as vscode from 'vscode';
import { InstallManager } from './install';
import { HealthChecker } from './health';
import { StatusBarManager } from './statusbar';
import { OnboardWizard } from './onboard';
import { McpConfigurator } from './mcp';
import { ExtensionUpdater } from './updater';
import { StatusTreeProvider, IdentityState } from './views/status-tree';
import { SkillsTreeProvider } from './views/skills-tree';
import { showSkillCard } from './views/skill-card';
import { SkillInfo } from './views/skill-loader';
import { SecretsManager } from './secret-storage';
import { runSignIn, runSignOut, maybeShowOnboarding, describeSignInError } from './auth';
import { fetchWhoami } from './cloud-api';

let statusBar: StatusBarManager | undefined;
let identityPollingHandle: NodeJS.Timeout | undefined;
const IDENTITY_POLL_INTERVAL_MS = 60_000;

export async function activate(context: vscode.ExtensionContext) {
	const installer = new InstallManager(context);
	const health = new HealthChecker();
	const mcpConfig = new McpConfigurator();
	const secrets = new SecretsManager(context);
	const workspaceFolders = (vscode.workspace.workspaceFolders ?? []).map(f => f.uri.fsPath);

	// Status bar — created early, added to subscriptions for auto-disposal
	statusBar = new StatusBarManager();
	context.subscriptions.push(statusBar.item);

	// Tree views
	const statusTree = new StatusTreeProvider(health, secrets);
	const skillsTree = new SkillsTreeProvider(workspaceFolders);
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
			await updateSkillsContext(skillsTree);
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

		vscode.commands.registerCommand('specbox.configureMcp', async () => {
			await mcpConfig.configureAll();
		}),

		vscode.commands.registerCommand('specbox.signIn', async () => {
			const result = await runSignIn(context, secrets);
			if (result.ok) {
				vscode.window.showInformationMessage(
					result.handle
						? vscode.l10n.t('Signed in as @{0}. Welcome!', result.handle)
						: vscode.l10n.t('Signed in. Welcome!')
				);
				await refreshIdentity(statusTree, secrets);
			} else {
				vscode.window.showWarningMessage(
					vscode.l10n.t('Sign-in failed: {0}.', describeSignInError(result.error))
				);
			}
		}),

		vscode.commands.registerCommand('specbox.signOut', async () => {
			await runSignOut(secrets);
			vscode.window.showInformationMessage(vscode.l10n.t('Signed out.'));
			await refreshIdentity(statusTree, secrets);
		}),

		vscode.commands.registerCommand('specbox.showSkillCard', async (skill: SkillInfo) => {
			if (!skill || typeof skill.name !== 'string') {
				vscode.window.showWarningMessage(vscode.l10n.t('Invalid skill — refresh the sidebar and try again.'));
				return;
			}
			await showSkillCard(skill);
		}),

		vscode.commands.registerCommand('specbox.refresh', async () => {
			skillsTree.refresh();
			statusTree.refresh();
			await updateSkillsContext(skillsTree);
		}),

		vscode.commands.registerCommand('specbox.identityQuickPick', async () => {
			const signedIn = await secrets.hasToken();
			if (signedIn) {
				const signOut = vscode.l10n.t('Sign out');
				const openProfile = vscode.l10n.t('Open profile on cloud.specbox.build');
				const pick = await vscode.window.showQuickPick([signOut, openProfile]);
				if (pick === signOut) {
					await vscode.commands.executeCommand('specbox.signOut');
				} else if (pick === openProfile) {
					await vscode.env.openExternal(vscode.Uri.parse('https://cloud.specbox.build/profile'));
				}
			} else {
				const signIn = vscode.l10n.t('Sign in with GitHub');
				const pick = await vscode.window.showQuickPick([signIn]);
				if (pick === signIn) {
					await vscode.commands.executeCommand('specbox.signIn');
				}
			}
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
			const runWizard = vscode.l10n.t('Run Wizard');
			const installNow = vscode.l10n.t('Install Now');
			const later = vscode.l10n.t('Later');
			const action = await vscode.window.showInformationMessage(
				vscode.l10n.t('SpecBox Engine detected but not installed. Run the setup wizard?'),
				runWizard,
				installNow,
				later
			);
			if (action === runWizard) {
				await vscode.commands.executeCommand('specbox.onboard');
			} else if (action === installNow) {
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

	// UC-647 — onboarding gate (only when no decision yet)
	await maybeShowOnboarding(context, secrets).catch((err) => {
		console.warn('[specbox] onboarding gate failed:', err);
	});

	// Skills context bootstrapping (drives viewsWelcome for specbox.skills)
	await updateSkillsContext(skillsTree);

	// UC-649 — identity polling + initial refresh
	await refreshIdentity(statusTree, secrets);
	identityPollingHandle = setInterval(() => {
		refreshIdentity(statusTree, secrets).catch(() => { /* ignore */ });
	}, IDENTITY_POLL_INTERVAL_MS);
	context.subscriptions.push({
		dispose: () => {
			if (identityPollingHandle) { clearInterval(identityPollingHandle); identityPollingHandle = undefined; }
		},
	});
}

async function refreshIdentity(tree: StatusTreeProvider, secrets: SecretsManager): Promise<void> {
	const token = await secrets.getToken();
	if (!token) {
		tree.updateIdentity({ signedIn: false });
		await vscode.commands.executeCommand('setContext', 'specbox.signedIn', false);
		return;
	}
	// Try resolving the real GitHub handle via cloud /api/whoami. If the
	// endpoint isn't deployed yet (SPA fallback returns text/html), or the
	// request fails for any other transient reason, fall back to the token
	// mask so the sidebar still reflects the signed-in state.
	const initialHandle = maskHandle(token);
	tree.updateIdentity({ signedIn: true, handle: initialHandle });
	await vscode.commands.executeCommand('setContext', 'specbox.signedIn', true);

	const me = await fetchWhoami(token);
	if (me && me.handle && me.handle !== initialHandle) {
		tree.updateIdentity({ signedIn: true, handle: me.handle });
	}
}

async function updateSkillsContext(skillsTree: SkillsTreeProvider): Promise<void> {
	const skills = skillsTree.getLoadedSkills();
	await vscode.commands.executeCommand('setContext', 'specbox.hasSkills', skills.length > 0);
}

function maskHandle(token: string): string {
	// Show the first 6 chars of the token hash as a stable pseudo-handle until
	// the whoami() integration lands. The real handle is resolved by UC-649 polling.
	return token.slice(0, 6);
}

export function deactivate() {
	if (identityPollingHandle) { clearInterval(identityPollingHandle); identityPollingHandle = undefined; }
	statusBar = undefined;
}
