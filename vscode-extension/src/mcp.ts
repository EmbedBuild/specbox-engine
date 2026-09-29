import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';
import { CLAUDE_DIR, CLAUDE_SETTINGS_LOCAL } from './constants';
import { readJson, writeJson, commandExists } from './util';
import type { ClaudeConfigResult, SpecboxCli } from './specbox-cli';

// US-VSCODE-ZERO-PY (zero-runtime onboarding): the SpecBox MCP server is consumed
// exclusively through the free hosted endpoint. The legacy local mode was removed
// to keep the client onboarding path free of any extra language runtime.
export const REMOTE_MCP_URL = 'https://mcp-specbox-engine.jpsdeveloper.com/mcp';

interface McpServerConfig {
	command: string;
	args?: string[];
	env?: Record<string, string>;
}

// --- Pure, vscode-free helpers (testable with node:test) ---

/**
 * UC-3901 AC-03 — what the old extension wrote for SpecBox-MCP in
 * ~/.claude/settings.local.json and never worked: Claude Code does not read MCP
 * servers from settings files, and the launcher expected a
 * `${secretStorage:…}` value nobody resolves (plus a path inside the installed
 * extension, which changes with every version). Removes only those shapes —
 * the launcher, the `npx mcp-remote <SpecBox URL>` bridge or the placeholder —
 * and leaves any other SpecBox-MCP entry (and every other key) untouched.
 */
export function stripLegacySpecboxEntry(settings: Record<string, unknown>): {
	changed: boolean;
	settings: Record<string, unknown>;
} {
	const servers = (settings?.mcpServers ?? {}) as Record<string, McpServerConfig>;
	const entry = servers['SpecBox-MCP'];
	if (!entry) { return { changed: false, settings }; }
	const args = Array.isArray(entry.args) ? entry.args.map(String) : [];
	const launcher = entry.command === 'node' && args.some((a) => a.endsWith('mcp-launcher.mjs'));
	const bridge = entry.command === 'npx' && args.includes('mcp-remote') && args.includes(REMOTE_MCP_URL);
	const placeholder = JSON.stringify(entry.env ?? {}).includes('${secretStorage:');
	if (!launcher && !bridge && !placeholder) { return { changed: false, settings }; }
	const remaining = { ...servers };
	delete remaining['SpecBox-MCP'];
	const next: Record<string, unknown> = { ...settings };
	if (Object.keys(remaining).length > 0) {
		next.mcpServers = remaining;
	} else {
		delete next.mcpServers;
	}
	return { changed: true, settings: next };
}

/**
 * Remove that dead entry from ~/.claude/settings.local.json, keeping a backup
 * next to it. Called only after Claude Code has the working entry (http +
 * headers helper) in ~/.claude.json.
 */
export function removeLegacyLauncherEntry(settingsPath: string = CLAUDE_SETTINGS_LOCAL, now: Date = new Date()): boolean {
	const settings = readJson<Record<string, unknown>>(settingsPath);
	if (!settings) { return false; }
	const { changed, settings: next } = stripLegacySpecboxEntry(settings);
	if (!changed) { return false; }
	try {
		const stamp = now.toISOString().replace(/[-:]/g, '').replace(/\.\d+Z$/, 'Z');
		fs.copyFileSync(settingsPath, `${settingsPath}.bak-uc3904-${stamp}`);
		writeJson(settingsPath, next);
		return true;
	} catch (err) {
		console.warn('[specbox] could not clean the legacy SpecBox-MCP entry:', err);
		return false;
	}
}

/** Offer the exact command when Claude Code could not be configured automatically. */
export async function showManualClaudeCommand(manual: string | undefined): Promise<void> {
	if (!manual) { return; }
	const copy = vscode.l10n.t('Copy command');
	const choice = await vscode.window.showWarningMessage(
		vscode.l10n.t('Claude Code could not be configured automatically. Run this command in a terminal: {0}', manual),
		copy,
	);
	if (choice === copy) {
		await vscode.env.clipboard.writeText(manual);
	}
}

export interface EngramInstallPlan {
	method: 'brew' | 'manual';
	command: string | null;
	manualUrl: string;
}

// UC-662 — FreeForm first-class onboarding (no Python).
//
// Choosing FreeForm in the onboarding gate must produce a fully operational
// project: tracking lives locally in doc/tracking/, but the MCP server is the
// SAME free hosted endpoint as every other backend (content-passing via the
// bridge, UC-660/661). No local MCP, no Python/uv — that was the v6.7.0 (#82)
// regression this UC reverts.

/** Default relative location of the FreeForm tracking dir, mirrored from the engine. */
export const FREEFORM_ROOT_RELATIVE = 'doc/tracking';

// UC-3801 AC-05: the client-side signal that the MCP server is remote. SpecBox
// hooks (freeform-path-guard) and skills read it to pass the local items.json
// as `items_content` instead of naming a directory the server cannot reach.
export const REMOTE_MCP_URL_ENV = 'SPECBOX_ENGINE_MCP_URL';

export interface FreeformProjectSettings {
	specbox: {
		backend_type: 'freeform';
		freeform_root_absolute: string;
	};
	env: {
		[REMOTE_MCP_URL_ENV]: string;
	};
}

/**
 * Build the project-level settings.local.json fragment that marks a project as
 * FreeForm. `freeform_root_absolute` MUST be absolute (the v5.29 BLOCKER: a
 * relative path would resolve against the remote server CWD). The caller passes
 * the workspace root; we join the canonical doc/tracking under it.
 *
 * The `env` block activates content-passing (UC-3801 AC-05): with the hosted
 * MCP the server never touches a directory, so the tracking file stays on this
 * machine and travels inside each tool call. Claude Code applies `env` from
 * settings.local.json to the session, so hooks and skills see the variable.
 *
 * Deliberately contains NO python/uv/local-mode keys — AC-06 asserts the output
 * is clean of any runtime reference.
 */
export function buildFreeformProjectSettings(workspaceRootAbsolute: string): FreeformProjectSettings {
	if (!path.isAbsolute(workspaceRootAbsolute)) {
		throw new Error(
			`buildFreeformProjectSettings: workspace root must be absolute, got ${workspaceRootAbsolute}`,
		);
	}
	return {
		specbox: {
			backend_type: 'freeform',
			freeform_root_absolute: path.join(workspaceRootAbsolute, FREEFORM_ROOT_RELATIVE),
		},
		env: {
			[REMOTE_MCP_URL_ENV]: REMOTE_MCP_URL,
		},
	};
}

/**
 * How to install Engram. Engram is a native single-file binary with zero
 * dependencies — no extra language runtime needed. Preferred install is
 * Homebrew; when brew is absent we point the user at the manual binary install.
 */
export function buildEngramInstallPlan(hasBrew: boolean): EngramInstallPlan {
	const manualUrl = 'https://github.com/Gentleman-Programming/engram';
	if (hasBrew) {
		return { method: 'brew', command: 'brew install gentleman-programming/tap/engram', manualUrl };
	}
	return { method: 'manual', command: null, manualUrl };
}

interface ClaudeSettings {
	mcpServers?: Record<string, McpServerConfig>;
	[key: string]: unknown;
}

export class McpConfigurator {

	/** The bundled `specbox` CLI (UC-3904); without it SpecBox-MCP cannot be configured. */
	constructor(private readonly cli?: SpecboxCli) {}

	async configureAll(): Promise<void> {
		const actions: string[] = [];

		// 1. Engram
		const engramOk = await this.configureEngram();
		if (engramOk) { actions.push('Engram MCP'); }

		// 2. SpecBox MCP server
		const specboxOk = await this.configureSpecbox();
		if (specboxOk) { actions.push('SpecBox MCP'); }

		if (actions.length > 0) {
			vscode.window.showInformationMessage(`MCP configured: ${actions.join(', ')}`);
		} else {
			vscode.window.showWarningMessage('No MCP servers were configured. Check prerequisites.');
		}
	}

	async configureEngram(): Promise<boolean> {
		const hasEngram = await commandExists('engram');
		if (!hasEngram) {
			const hasBrew = await commandExists('brew');
			const plan = buildEngramInstallPlan(hasBrew);

			if (plan.method === 'brew' && plan.command) {
				const action = await vscode.window.showWarningMessage(
					'Engram is not installed. It provides persistent memory for Claude Code (mandatory for token efficiency). Install it now?',
					'Install with Homebrew', 'Skip'
				);
				if (action === 'Install with Homebrew') {
					const result = await this.runInstallCommand(plan.command);
					if (!result) { return false; }
				} else {
					return false;
				}
			} else {
				// No Homebrew available — point the user at the native binary install.
				// Engram ships as a single self-contained binary with zero deps.
				await vscode.window.showWarningMessage(
					`Engram is not installed and Homebrew was not found. Install the Engram binary manually from ${plan.manualUrl} (single binary, no extra runtime needed), then re-run "Configure MCP Servers".`,
					'Open install guide'
				).then((choice) => {
					if (choice === 'Open install guide') {
						vscode.env.openExternal(vscode.Uri.parse(plan.manualUrl));
					}
				});
				return false;
			}
		}

		// Add to Claude settings
		this.addMcpServer('engram', {
			command: 'engram',
			args: ['mcp', '--tools=agent'],
		});

		// Also add to workspace .vscode/mcp.json if workspace is open
		this.addWorkspaceMcp('engram', {
			command: 'engram',
			args: ['mcp', '--tools=agent'],
		});

		return true;
	}

	/**
	 * UC-3901 AC-03 — SpecBox-MCP in Claude Code (~/.claude.json, user scope) as
	 * `{type: "http", url, headersHelper}`: the helper sends the token of this
	 * device on every connection (or nothing, before signing in). Written by the
	 * bundled CLI through `claude mcp add-json`, the same way `specbox login` does.
	 */
	async configureSpecbox(): Promise<boolean> {
		if (!this.cli) { return false; }
		const res = await this.cli.call<{ ok: boolean; claude?: ClaudeConfigResult }>('_configure');
		if (!res) {
			vscode.window.showWarningMessage(
				vscode.l10n.t('Node.js is needed to configure the SpecBox MCP server in Claude Code. Install Node.js 18 or newer and try again.')
			);
			return false;
		}
		if (!res.claude?.ok) {
			await showManualClaudeCommand(res.claude?.manual);
			return false;
		}
		removeLegacyLauncherEntry();
		return true;
	}

	// --- Private ---

	private addMcpServer(name: string, config: McpServerConfig): void {
		try {
			const settingsPath = path.join(CLAUDE_DIR, 'settings.local.json');
			const settings: ClaudeSettings = readJson<ClaudeSettings>(settingsPath) ?? {};

			if (!settings.mcpServers) { settings.mcpServers = {}; }
			settings.mcpServers[name] = config;

			writeJson(settingsPath, settings);
		} catch (err) {
			vscode.window.showErrorMessage(`Failed to write MCP config for ${name}: ${err instanceof Error ? err.message : String(err)}`);
		}
	}

	private addWorkspaceMcp(name: string, config: McpServerConfig): void {
		const folders = vscode.workspace.workspaceFolders;
		if (!folders?.[0]) { return; }

		try {
			const mcpPath = path.join(folders[0].uri.fsPath, '.vscode', 'mcp.json');
			const data = readJson<{ servers?: Record<string, McpServerConfig> }>(mcpPath) ?? {};

			if (!data.servers) { data.servers = {}; }
			data.servers[name] = { ...config };

			writeJson(mcpPath, data);
		} catch (err) {
			vscode.window.showWarningMessage(`Failed to write workspace MCP config: ${err instanceof Error ? err.message : String(err)}`);
		}
	}

	private async runInstallCommand(cmd: string): Promise<boolean> {
		const terminal = vscode.window.createTerminal('SpecBox Setup');
		terminal.sendText(cmd);
		terminal.show();

		const ok = await vscode.window.showInformationMessage(
			`Running: ${cmd}. Click OK when the installation finishes.`,
			'OK', 'Failed'
		);
		return ok === 'OK';
	}
}

// ---------------------------------------------------------------------------
// UC-646 → UC-3904: the SecretStorage launcher (bin/mcp-launcher.mjs) is gone.
// Claude Code gets the token from the headers helper the bundled `specbox` CLI
// installs; see configureSpecbox() and stripLegacySpecboxEntry().
// ---------------------------------------------------------------------------

/**
 * Restart the MCP server so the new handshake takes effect. The Claude Code
 * extension exposes a restart command; we try it and fall back to a notification
 * asking the user to reload the window if the command is unavailable.
 */
export async function respawnMcpServer(): Promise<void> {
	try {
		await vscode.commands.executeCommand('claude.mcpRestart', 'SpecBox-MCP');
	} catch {
		const reload = vscode.l10n.t('Reload Window');
		const action = await vscode.window.showInformationMessage(
			vscode.l10n.t('MCP server config updated. Reload the window to apply.'),
			reload
		);
		if (action === reload) {
			await vscode.commands.executeCommand('workbench.action.reloadWindow');
		}
	}
}
