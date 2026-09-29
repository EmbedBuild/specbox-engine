import * as vscode from 'vscode';
import { InstallManager } from './install';
import { HealthChecker } from './health';
import { StatusBarManager } from './statusbar';
import { OnboardWizard } from './onboard';
import { McpConfigurator, REMOTE_MCP_URL, removeLegacyLauncherEntry } from './mcp';
import { ExtensionUpdater } from './updater';
import { StatusTreeProvider } from './views/status-tree';
import { SkillsTreeProvider } from './views/skills-tree';
import { showSkillCard } from './views/skill-card';
import { SkillInfo } from './views/skill-loader';
import { SecretsManager } from './secret-storage';
import { runSignIn, runSignOut, maybeShowOnboarding, describeSignInError, reportConnection } from './auth';
import { whoamiStatus } from './cloud-api';
import { showPrereqGate } from './prerequisites';
import { registerRevertCommand } from './migration';
import { registerActivationUriHandler, maybeEmitActivation } from './activation';
import { SpecboxCli, cloudApiBase } from './specbox-cli';
import { ensureDeviceConnection, syncRenewal } from './device-connection';
import { howToConnectUrl } from './constants';

let statusBar: StatusBarManager | undefined;
let identityPollingHandle: NodeJS.Timeout | undefined;
let renewalHandle: NodeJS.Timeout | undefined;
const IDENTITY_POLL_INTERVAL_MS = 60_000;
/** UC-3904 AC-03 — once a day the token is renewed if due (the helper also does it on connect). */
const RENEWAL_INTERVAL_MS = 24 * 60 * 60 * 1000;
/** UC-3904 AC-07 — the "connection ended" notice is shown once per session. */
let connectionEndedNotified = false;
/** UC-3904 — the bundled CLI, reachable from refreshIdentity (polling). */
let activeCli: SpecboxCli | undefined;

export async function activate(context: vscode.ExtensionContext) {
	const installer = new InstallManager(context);
	const health = new HealthChecker();
	// UC-3904 — the bundled `specbox` CLI does the secure store, the headers
	// helper and the Claude Code configuration, exactly as `specbox login`.
	const signInBaseUrl = vscode.workspace.getConfiguration().get<string>('specbox.signInBaseUrl') || undefined;
	const cli = new SpecboxCli(context.extensionPath, { cloudApi: cloudApiBase(signInBaseUrl), mcpUrl: REMOTE_MCP_URL });
	activeCli = cli;
	const mcpConfig = new McpConfigurator(cli);
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

		vscode.commands.registerCommand('specbox.checkPrerequisites', async () => {
			const result = await health.run();
			statusBar?.update(result);
			statusTree.refresh();
			await showPrereqGate(result, { onStartup: false });
		}),

		vscode.commands.registerCommand('specbox.signIn', async () => {
			const result = await runSignIn(context, secrets, cli);
			if (result.ok) {
				connectionEndedNotified = false;
				vscode.window.showInformationMessage(
					result.handle
						? vscode.l10n.t('Signed in as @{0}. Welcome!', result.handle)
						: vscode.l10n.t('Signed in. Welcome!')
				);
				void reportConnection(result);
				await refreshIdentity(statusTree, secrets);
			} else {
				vscode.window.showWarningMessage(
					vscode.l10n.t('Sign-in failed: {0}.', describeSignInError(result.error))
				);
			}
		}),

		vscode.commands.registerCommand('specbox.signOut', async () => {
			await runSignOut(secrets, cli);
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

	// UC-665 — "SpecBox: Revert last migration" command (config rollback).
	registerRevertCommand(context);

	// US-26 (UC-2601) — funnel deep-link handler. Registered synchronously so a
	// vscode://EmbedBuild.specbox-engine/activate?anon_id=... link that triggered
	// activation is captured even on this very startup.
	registerActivationUriHandler(context);

	// Identity polling — registered synchronously so its disposal is wired up
	// regardless of how the async startup tasks below resolve.
	identityPollingHandle = setInterval(() => {
		refreshIdentity(statusTree, secrets).catch(() => { /* ignore */ });
	}, IDENTITY_POLL_INTERVAL_MS);
	// UC-3904 AC-03 — daily renewal; the SecretStorage copy follows the token.
	renewalHandle = setInterval(() => {
		syncRenewal(cli, secrets)
			.then((changed) => (changed ? refreshIdentity(statusTree, secrets) : undefined))
			.catch(() => { /* ignore */ });
	}, RENEWAL_INTERVAL_MS);
	context.subscriptions.push({
		dispose: () => {
			if (identityPollingHandle) { clearInterval(identityPollingHandle); identityPollingHandle = undefined; }
			if (renewalHandle) { clearInterval(renewalHandle); renewalHandle = undefined; }
		},
	});

	// CRITICAL: activate() must resolve fast. Health check, the engine-update
	// prompt, the onboarding gate and the identity refresh all either hit the
	// network or block on user input (showInformationMessage). Awaiting them
	// here kept the extension stuck on "Activating…" until the user clicked a
	// notification — which is exactly what happened to every user after a
	// version bump (the updater's "Update extension?" prompt blocked startup).
	// We fire them in the background and never await; failures are swallowed so
	// they can never wedge activation.
	void runStartupTasks(context, { health, statusBar: statusBar!, statusTree, skillsTree, secrets, cli });
}

interface StartupDeps {
	health: HealthChecker;
	statusBar: StatusBarManager;
	statusTree: StatusTreeProvider;
	skillsTree: SkillsTreeProvider;
	secrets: SecretsManager;
	cli: SpecboxCli;
}

/**
 * Non-blocking startup work. Runs AFTER activate() has already resolved, so
 * VS Code marks the extension active immediately. Nothing here may throw out
 * — each step guards itself and logs on failure.
 */
async function runStartupTasks(context: vscode.ExtensionContext, deps: StartupDeps): Promise<void> {
	const { health, statusBar: bar, statusTree, skillsTree, secrets, cli } = deps;

	const config = vscode.workspace.getConfiguration('specbox');
	if (config.get<boolean>('autoHealthCheck', true)) {
		try {
			const result = await health.run();
			bar.update(result);
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

			// Self-update + post-update orchestration (UC-666): binary → detect
			// config case → migrate → summary. Fire-and-forget per phase so a
			// failure never wedges activation.
			if (result.enginePath) {
				const extVersion = context.extension.packageJSON.version as string;
				const updater = new ExtensionUpdater(extVersion);
				await updater.runUpdateFlow(result.enginePath);
			}
		} catch (err) {
			console.warn('[specbox] startup health/update task failed:', err);
		}

		// US-VSCODE-PREREQ-GATE — non-blocking prerequisites gate. Warns (and
		// only warns) when a critical prerequisite is missing so the user knows
		// SpecBox may not work correctly. Silent when everything is ready.
		try {
			const result = await health.run();
			await showPrereqGate(result, { onStartup: true });
		} catch (err) {
			console.warn('[specbox] prerequisites gate failed:', err);
		}
	}

	// UC-647 — onboarding gate (only when no decision yet).
	await maybeShowOnboarding(context, secrets, undefined, cli).catch((err) => {
		console.warn('[specbox] onboarding gate failed:', err);
	});

	// UC-3901 AC-03 / UC-3904 — keep this computer connected without manual
	// steps: adopt a token kept from an older version as a device token, renew
	// it when due, restore the Claude Code helper config, drop the dead entry.
	try {
		const report = await ensureDeviceConnection(cli, secrets, () => { removeLegacyLauncherEntry(); });
		if (report.state === 'adopted') {
			vscode.window.showInformationMessage(
				vscode.l10n.t('This computer now connects to SpecBox with your account. New Claude Code sessions use it automatically.')
			);
		}
	} catch (err) {
		console.warn('[specbox] device connection check failed:', err);
	}

	// Skills context bootstrapping (drives viewsWelcome for specbox.skills).
	await updateSkillsContext(skillsTree).catch((err) => {
		console.warn('[specbox] skills context bootstrap failed:', err);
	});

	// UC-649 — initial identity refresh (polling already armed in activate()).
	await refreshIdentity(statusTree, secrets).catch((err) => {
		console.warn('[specbox] initial identity refresh failed:', err);
	});

	// US-26 (UC-2601) — emit the one-shot `activation` funnel event. Idempotent,
	// privacy-respecting, fully self-guarded — fired without await so a slow or
	// failing POST can never wedge activation.
	void maybeEmitActivation(context);
}

async function refreshIdentity(tree: StatusTreeProvider, secrets: SecretsManager, retried = false): Promise<void> {
	const token = await secrets.getToken();
	if (!token) {
		tree.updateIdentity({ signedIn: false });
		statusBar?.setIdentity(null);
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

	const res = await whoamiStatus(token);
	if (res.status === 'ok') {
		tree.updateIdentity({ signedIn: true, handle: res.me.handle });
		// UC-3904 AC-06 — person, device, expiry and automatic renewal.
		statusBar?.setIdentity({
			handle: res.me.handle,
			deviceName: res.me.device?.device_name ?? null,
			expiresAt: res.me.device?.expires_at ?? null,
			renews: Boolean(res.me.device?.expires_at),
		});
		return;
	}
	if (res.status === 'unauthorized') {
		// The headers helper may have renewed the token on its own (which revokes
		// the previous one): take the current token from the secure store before
		// deciding that the connection has ended.
		if (!retried && activeCli && (await syncRenewal(activeCli, secrets))) {
			return refreshIdentity(tree, secrets, true);
		}
		// UC-3904 AC-07 — expired or revoked: the connection from this device
		// has ended. Forget the dead token and say how to reconnect (never
		// asking to paste a token).
		await secrets.deleteToken();
		tree.updateIdentity({ signedIn: false });
		statusBar?.setIdentity(null);
		await vscode.commands.executeCommand('setContext', 'specbox.signedIn', false);
		if (!connectionEndedNotified) {
			connectionEndedNotified = true;
			void notifyConnectionEnded();
		}
	}
}

async function notifyConnectionEnded(): Promise<void> {
	const signIn = vscode.l10n.t('Sign in with GitHub');
	const howItWorks = vscode.l10n.t('How SpecBox connects');
	const choice = await vscode.window.showWarningMessage(
		vscode.l10n.t('The connection from this device has ended: its token expired or was revoked. Reconnect with "SpecBox: Sign in with GitHub" or by running `specbox login` in a terminal.'),
		signIn,
		howItWorks
	);
	if (choice === signIn) {
		await vscode.commands.executeCommand('specbox.signIn');
	} else if (choice === howItWorks) {
		await vscode.env.openExternal(vscode.Uri.parse(howToConnectUrl(vscode.env.language)));
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
	if (renewalHandle) { clearInterval(renewalHandle); renewalHandle = undefined; }
	statusBar = undefined;
}
