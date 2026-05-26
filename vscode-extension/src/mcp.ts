import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import { CLAUDE_DIR } from './constants';
import { readJson, writeJson, ensureDir, commandExists, exec } from './util';

// UC-646: the MCP server config references this env var; the wrapper launcher
// (vscode-extension/bin/mcp-launcher.mjs) resolves the value from SecretStorage
// at spawn time so the plaintext token never lands in settings.json.
export const SPECBOX_NATIVE_MCP_TOKEN_ENV = 'SPECBOX_NATIVE_MCP_TOKEN';
const LAUNCHER_BIN_RELATIVE = '../bin/mcp-launcher.mjs';

interface McpServerConfig {
	command: string;
	args?: string[];
	env?: Record<string, string>;
}

interface ClaudeSettings {
	mcpServers?: Record<string, McpServerConfig>;
	[key: string]: unknown;
}

export class McpConfigurator {

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
			const action = await vscode.window.showWarningMessage(
				'Engram is not installed. It provides persistent memory for Claude Code (mandatory for token efficiency). Install it now?',
				'Install with pip', 'Install with pipx', 'Skip'
			);
			if (action === 'Install with pip') {
				const result = await this.runInstallCommand('pip install engram');
				if (!result) { return false; }
			} else if (action === 'Install with pipx') {
				const result = await this.runInstallCommand('pipx install engram');
				if (!result) { return false; }
			} else {
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

	async configureSpecbox(): Promise<boolean> {
		// Ask user: local or remote MCP server?
		const mode = await vscode.window.showQuickPick([
			{ label: 'Remote (recommended)', description: 'Connect to https://mcp-specbox-engine.jpsdeveloper.com/mcp', value: 'remote' },
			{ label: 'Local', description: 'Run MCP server locally (requires Python 3.12+)', value: 'local' },
		], { placeHolder: 'How should the SpecBox MCP server connect?' });

		if (!mode) { return false; }

		if (mode.value === 'remote') {
			this.addMcpServer('SpecBox-MCP', {
				command: 'npx',
				args: ['mcp-remote', 'https://mcp-specbox-engine.jpsdeveloper.com/mcp'],
			});
			return true;
		}

		// Local mode
		const enginePath = await this.findEnginePath();
		if (!enginePath) {
			vscode.window.showWarningMessage('SpecBox Engine path not found. Install the engine first.');
			return false;
		}

		const hasPython = await commandExists('python3') || await commandExists('python');
		if (!hasPython) {
			vscode.window.showErrorMessage('Python 3.12+ is required for the local SpecBox MCP server.');
			return false;
		}

		// Determine how to run the MCP server
		// Option A: uv run (preferred — handles venv automatically)
		// Option B: python -m server.server
		const hasUv = await commandExists('uv');

		let serverConfig: McpServerConfig;
		if (hasUv) {
			serverConfig = {
				command: 'uv',
				args: ['run', '--directory', enginePath, 'specbox-engine'],
			};
		} else {
			const pythonCmd = await commandExists('python3') ? 'python3' : 'python';
			serverConfig = {
				command: pythonCmd,
				args: ['-m', 'server.server'],
				env: { PYTHONPATH: enginePath },
			};
		}

		this.addMcpServer('SpecBox-MCP', serverConfig);

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

	private async findEnginePath(): Promise<string | null> {
		const configured = vscode.workspace.getConfiguration('specbox').get<string>('enginePath');
		if (configured && fs.existsSync(path.join(configured, 'ENGINE_VERSION.yaml'))) {
			return configured;
		}
		for (const folder of vscode.workspace.workspaceFolders ?? []) {
			if (fs.existsSync(path.join(folder.uri.fsPath, 'ENGINE_VERSION.yaml'))) {
				return folder.uri.fsPath;
			}
		}
		const home = os.homedir();
		for (const rel of ['specbox-engine', 'Desktop/specbox-engine', 'dev/specbox-engine', 'projects/specbox-engine']) {
			const p = path.join(home, rel);
			if (fs.existsSync(path.join(p, 'ENGINE_VERSION.yaml'))) { return p; }
		}
		return null;
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
// UC-646 — MCP handshake helpers (SecretStorage-backed launcher)
// ---------------------------------------------------------------------------

interface ClaudeMcpServer {
	command: string;
	args?: string[];
	env?: Record<string, string>;
	[key: string]: unknown;
}

interface ClaudeMcpSettings {
	mcpServers?: Record<string, ClaudeMcpServer>;
	[key: string]: unknown;
}

function readClaudeSettings(): { settingsPath: string; settings: ClaudeMcpSettings } {
	const settingsPath = path.join(CLAUDE_DIR, 'settings.local.json');
	const settings = readJson<ClaudeMcpSettings>(settingsPath) ?? {};
	if (!settings.mcpServers) { settings.mcpServers = {}; }
	return { settingsPath, settings };
}

function resolveLauncherPath(): string | null {
	const ext = vscode.extensions.getExtension('EmbedBuild.specbox-engine');
	const base = ext?.extensionPath;
	if (!base) { return null; }
	return path.join(base, 'bin', 'mcp-launcher.mjs');
}

/**
 * Update the SpecBox-MCP server entry so it launches through the wrapper that
 * reads the token from VSCode SecretStorage. Does NOT write the token to disk
 * — only a placeholder env var name that the launcher resolves at spawn time.
 */
export function updateMcpServerConfigWithToken(): void {
	const { settingsPath, settings } = readClaudeSettings();
	const launcher = resolveLauncherPath();
	if (!launcher) { return; }

	const existing = settings.mcpServers!['SpecBox-MCP'] ?? { command: '', args: [] };
	// Preserve the underlying command/args so the launcher can forward them.
	const inner = {
		command: existing.command,
		args: existing.args ?? [],
	};
	settings.mcpServers!['SpecBox-MCP'] = {
		command: 'node',
		args: [launcher, JSON.stringify(inner)],
		env: { [SPECBOX_NATIVE_MCP_TOKEN_ENV]: '${secretStorage:specbox.mcpToken}' },
	};
	writeJson(settingsPath, settings);
}

/**
 * Strip the wrapper launcher from the SpecBox-MCP entry and restore the
 * underlying server command. Idempotent: safe to call when not configured.
 */
export function clearMcpServerConfig(): void {
	const { settingsPath, settings } = readClaudeSettings();
	const entry = settings.mcpServers!['SpecBox-MCP'];
	if (!entry) { return; }
	const launcher = resolveLauncherPath();
	if (!launcher) { return; }
	// If the entry currently points at the launcher, restore the inner command.
	if (entry.command === 'node' && Array.isArray(entry.args) && entry.args[0] === launcher) {
		try {
			const inner = JSON.parse(String(entry.args[1] ?? '{}')) as { command: string; args?: string[] };
			settings.mcpServers!['SpecBox-MCP'] = { command: inner.command, args: inner.args ?? [] };
		} catch {
			delete settings.mcpServers!['SpecBox-MCP'];
		}
	} else if (entry.env && SPECBOX_NATIVE_MCP_TOKEN_ENV in (entry.env ?? {})) {
		const newEnv = { ...entry.env };
		delete newEnv[SPECBOX_NATIVE_MCP_TOKEN_ENV];
		settings.mcpServers!['SpecBox-MCP'] = { ...entry, env: newEnv };
	}
	writeJson(settingsPath, settings);
}

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
