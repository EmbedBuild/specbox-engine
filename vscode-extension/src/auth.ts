import * as vscode from 'vscode';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { startLoopbackServer, buildSignInUrl } from './oauth';
import { SecretsManager } from './secret-storage';
import { updateMcpServerConfigWithToken, clearMcpServerConfig, respawnMcpServer } from './mcp';

const ONBOARDING_DECISION_KEY = 'specbox.onboardingDecision';
const SIGN_IN_BASE_URL_CONFIG = 'specbox.signInBaseUrl';

export interface OnboardingDecision {
	mode: 'native' | 'freeform';
	timestamp: string;
	extVersion: string;
}

/**
 * UC-644 + UC-645 + UC-646 — runs the full sign-in flow:
 *   1. start loopback HTTP server (one-shot)
 *   2. open cloud sign-in URL in default browser
 *   3. await callback (5 min timeout)
 *   4. validate token, persist to SecretStorage
 *   5. update MCP config to use launcher + respawn
 */
export async function runSignIn(
	context: vscode.ExtensionContext,
	secrets: SecretsManager
): Promise<{ ok: boolean; error?: string }> {
	const cfg = vscode.workspace.getConfiguration();
	const baseUrl = cfg.get<string>(SIGN_IN_BASE_URL_CONFIG) || undefined;

	const server = await startLoopbackServer();
	try {
		const url = buildSignInUrl(server.port, server.state, baseUrl);
		const opened = await vscode.env.openExternal(vscode.Uri.parse(url));
		if (!opened) {
			server.close();
			return { ok: false, error: 'browser_blocked' };
		}

		const result = await server.awaitCallback;
		if (!result.ok) {
			return { ok: false, error: result.error };
		}

		await secrets.storeToken(result.token);
		try {
			updateMcpServerConfigWithToken();
			await respawnMcpServer();
		} catch (err) {
			// Token is stored; config update failure is recoverable on next reload.
			console.warn('[specbox.signIn] MCP config update failed:', err);
		}
		return { ok: true };
	} catch (err) {
		server.close();
		return { ok: false, error: (err instanceof Error ? err.message : String(err)) };
	}
}

/**
 * UC-646 — sign out: delete secret, clear MCP wrapper config, respawn.
 */
export async function runSignOut(secrets: SecretsManager): Promise<void> {
	await secrets.deleteToken();
	try {
		clearMcpServerConfig();
		await respawnMcpServer();
	} catch (err) {
		console.warn('[specbox.signOut] MCP config clear failed:', err);
	}
}

/**
 * UC-647 — onboarding gate. Shown exactly once on first activate (per workspace)
 * until the user picks a mode. Closing the notification (X) is NOT a decision.
 */
export async function maybeShowOnboarding(
	context: vscode.ExtensionContext,
	secrets: SecretsManager,
	options?: { skipLog?: boolean }
): Promise<OnboardingDecision | null> {
	const existing = context.workspaceState.get<OnboardingDecision>(ONBOARDING_DECISION_KEY);
	if (existing) { return existing; }

	// Backwards-compat: if a legacy token is already in env, treat as implicit native.
	if (process.env.SPECBOX_NATIVE_MCP_TOKEN) {
		const decision: OnboardingDecision = {
			mode: 'native',
			timestamp: new Date().toISOString(),
			extVersion: context.extension.packageJSON.version,
		};
		await context.workspaceState.update(ONBOARDING_DECISION_KEY, decision);
		return decision;
	}

	const signInLabel = vscode.l10n.t('Sign in with GitHub');
	const freeformLabel = vscode.l10n.t('Continue in local mode (FreeForm)');
	const choice = await vscode.window.showInformationMessage(
		vscode.l10n.t('Welcome to SpecBox Engine. Sign in to enable shared tracking, or continue in local mode.'),
		signInLabel,
		freeformLabel
	);

	if (!choice) {
		logOnboardingEvent('dismissed_without_decision', context, options?.skipLog);
		return null;
	}

	if (choice === signInLabel) {
		const result = await runSignIn(context, secrets);
		if (result.ok) {
			const decision: OnboardingDecision = {
				mode: 'native',
				timestamp: new Date().toISOString(),
				extVersion: context.extension.packageJSON.version,
			};
			await context.workspaceState.update(ONBOARDING_DECISION_KEY, decision);
			vscode.window.showInformationMessage(vscode.l10n.t('Signed in. Welcome!'));
			return decision;
		}
		vscode.window.showWarningMessage(
			vscode.l10n.t('Sign-in failed: {0}. You can try again later from the Command Palette.', result.error ?? 'unknown')
		);
		return null;
	}

	// FreeForm
	configureFreeformBackend();
	const decision: OnboardingDecision = {
		mode: 'freeform',
		timestamp: new Date().toISOString(),
		extVersion: context.extension.packageJSON.version,
	};
	await context.workspaceState.update(ONBOARDING_DECISION_KEY, decision);
	vscode.window.showInformationMessage(vscode.l10n.t('Continuing in local mode (FreeForm).'));
	return decision;
}

/**
 * Configures the workspace to use FreeForm backend with an absolute tracking path.
 * Mirrors the v5.29 freeform-path-guard logic on the client side.
 */
function configureFreeformBackend(): void {
	const folder = vscode.workspace.workspaceFolders?.[0];
	if (!folder) { return; }
	const root = folder.uri.fsPath;
	const claudeDir = path.join(root, '.claude');
	const settingsPath = path.join(claudeDir, 'settings.local.json');
	try {
		if (!fs.existsSync(claudeDir)) { fs.mkdirSync(claudeDir, { recursive: true }); }
		let settings: Record<string, unknown> = {};
		if (fs.existsSync(settingsPath)) {
			try { settings = JSON.parse(fs.readFileSync(settingsPath, 'utf-8')); } catch { settings = {}; }
		}
		const specbox = (settings.specbox as Record<string, unknown>) ?? {};
		specbox.backend_type = 'freeform';
		specbox.freeform_root_absolute = path.join(root, 'doc', 'tracking');
		settings.specbox = specbox;
		fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2));
	} catch (err) {
		console.warn('[specbox] failed to write freeform config:', err);
	}
}

function logOnboardingEvent(
	event: string,
	context: vscode.ExtensionContext,
	skip?: boolean
): void {
	if (skip) { return; }
	const folder = vscode.workspace.workspaceFolders?.[0];
	if (!folder) { return; }
	const logDir = path.join(folder.uri.fsPath, '.quality', 'logs');
	const logPath = path.join(logDir, 'onboarding.jsonl');
	try {
		if (!fs.existsSync(logDir)) { fs.mkdirSync(logDir, { recursive: true }); }
		const entry = {
			event,
			workspace_hash: hashWorkspace(folder.uri.fsPath),
			ext_version: context.extension.packageJSON.version,
			timestamp: new Date().toISOString(),
		};
		fs.appendFileSync(logPath, JSON.stringify(entry) + '\n');
	} catch {
		// Best-effort logging — never block onboarding on a write failure.
	}
}

function hashWorkspace(p: string): string {
	// crypto only at use-site to keep imports lazy
	const crypto = require('node:crypto') as typeof import('node:crypto');
	return crypto.createHash('sha256').update(p).digest('hex').slice(0, 16);
}
