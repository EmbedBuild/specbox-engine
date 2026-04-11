import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import {
	CLAUDE_SKILLS_DIR, CLAUDE_HOOKS_DIR, CLAUDE_HOOKS_LIB_DIR,
	CLAUDE_COMMANDS_DIR, CLAUDE_SETTINGS, CORE_SKILLS
} from './constants';
import { ensureDir, symlinkOrCopy, copyFile, readJson, writeJson } from './util';
import { HealthChecker } from './health';

export class InstallManager {
	private context: vscode.ExtensionContext;

	constructor(context: vscode.ExtensionContext) {
		this.context = context;
	}

	async runFullInstall(): Promise<void> {
		const health = new HealthChecker();
		const enginePath = await this.resolveEnginePath();
		if (!enginePath) { return; }

		await vscode.window.withProgress({
			location: vscode.ProgressLocation.Notification,
			title: 'SpecBox Engine',
			cancellable: false,
		}, async (progress) => {
			// 1. Skills
			progress.report({ message: 'Installing skills...', increment: 0 });
			const skillsResult = this.installSkills(enginePath);

			// 2. Hooks
			progress.report({ message: 'Installing hooks...', increment: 20 });
			const hooksResult = this.installHooks(enginePath);

			// 3. Commands (legacy)
			progress.report({ message: 'Installing commands...', increment: 40 });
			this.installCommands(enginePath);

			// 4. Settings
			progress.report({ message: 'Configuring settings...', increment: 60 });
			this.installSettings(enginePath);

			// 5. Health check
			progress.report({ message: 'Verifying installation...', increment: 80 });
			const result = await health.run();

			progress.report({ message: 'Done!', increment: 100 });

			// Summary
			const missing: string[] = [];
			if (!result.engram.ok) { missing.push('Engram'); }
			if (!result.mcpSpecbox.configured) { missing.push('MCP SpecBox server'); }
			if (!result.mcpEngram.configured) { missing.push('MCP Engram server'); }

			if (missing.length > 0) {
				const action = await vscode.window.showWarningMessage(
					`SpecBox installed (${skillsResult.count} skills, ${hooksResult.count} hooks). Missing: ${missing.join(', ')}. Configure now?`,
					'Configure MCP', 'Skip'
				);
				if (action === 'Configure MCP') {
					vscode.commands.executeCommand('specbox.configureMcp');
				}
			} else {
				vscode.window.showInformationMessage(
					`SpecBox Engine v${result.engineVersion} installed: ${skillsResult.count} skills, ${hooksResult.count} hooks, MCP configured.`
				);
			}
		});
	}

	async resolveEnginePath(): Promise<string | null> {
		// 1. Config
		const configured = vscode.workspace.getConfiguration('specbox').get<string>('enginePath');
		if (configured && fs.existsSync(path.join(configured, 'ENGINE_VERSION.yaml'))) {
			return configured;
		}

		// 2. Workspace
		for (const folder of vscode.workspace.workspaceFolders ?? []) {
			if (fs.existsSync(path.join(folder.uri.fsPath, 'ENGINE_VERSION.yaml'))) {
				return folder.uri.fsPath;
			}
		}

		// 3. Common locations
		const home = os.homedir();
		for (const rel of ['specbox-engine', 'Desktop/specbox-engine', 'dev/specbox-engine', 'projects/specbox-engine']) {
			const p = path.join(home, rel);
			if (fs.existsSync(path.join(p, 'ENGINE_VERSION.yaml'))) { return p; }
		}

		// 4. Ask user
		const result = await vscode.window.showOpenDialog({
			canSelectFolders: true,
			canSelectFiles: false,
			openLabel: 'Select SpecBox Engine folder',
			title: 'Where is the SpecBox Engine repository?',
		});

		if (result?.[0]) {
			const selected = result[0].fsPath;
			if (fs.existsSync(path.join(selected, 'ENGINE_VERSION.yaml'))) {
				// Save for future
				await vscode.workspace.getConfiguration('specbox').update('enginePath', selected, vscode.ConfigurationTarget.Global);
				return selected;
			}
			vscode.window.showErrorMessage('Selected folder does not contain ENGINE_VERSION.yaml. Not a SpecBox Engine repo.');
		}
		return null;
	}

	getInstalledSkills(): string[] {
		if (!fs.existsSync(CLAUDE_SKILLS_DIR)) { return []; }
		return CORE_SKILLS.filter(s =>
			fs.existsSync(path.join(CLAUDE_SKILLS_DIR, s, 'SKILL.md'))
		);
	}

	// --- Private ---

	private installSkills(enginePath: string): { count: number } {
		const srcDir = path.join(enginePath, '.claude', 'skills');
		ensureDir(CLAUDE_SKILLS_DIR);
		let count = 0;

		for (const entry of fs.readdirSync(srcDir, { withFileTypes: true })) {
			if (!entry.isDirectory()) { continue; }
			const src = path.join(srcDir, entry.name);
			const dest = path.join(CLAUDE_SKILLS_DIR, entry.name);
			symlinkOrCopy(src, dest, 'dir');
			count++;
		}
		return { count };
	}

	private installHooks(enginePath: string): { count: number } {
		const srcDir = path.join(enginePath, '.claude', 'hooks');
		ensureDir(CLAUDE_HOOKS_DIR);
		let count = 0;

		// Copy .mjs hook files
		for (const file of fs.readdirSync(srcDir)) {
			if (!file.endsWith('.mjs')) { continue; }
			copyFile(path.join(srcDir, file), path.join(CLAUDE_HOOKS_DIR, file));
			count++;
		}

		// Copy lib/ directory
		const libSrc = path.join(srcDir, 'lib');
		if (fs.existsSync(libSrc)) {
			ensureDir(CLAUDE_HOOKS_LIB_DIR);
			for (const file of fs.readdirSync(libSrc)) {
				copyFile(path.join(libSrc, file), path.join(CLAUDE_HOOKS_LIB_DIR, file));
			}
		}

		return { count };
	}

	private installCommands(enginePath: string): void {
		const srcDir = path.join(enginePath, 'commands');
		if (!fs.existsSync(srcDir)) { return; }
		ensureDir(CLAUDE_COMMANDS_DIR);

		for (const file of fs.readdirSync(srcDir)) {
			if (!file.endsWith('.md')) { continue; }
			const src = path.join(srcDir, file);
			const dest = path.join(CLAUDE_COMMANDS_DIR, file);
			symlinkOrCopy(src, dest, 'file');
		}
	}

	private installSettings(enginePath: string): void {
		if (fs.existsSync(CLAUDE_SETTINGS)) {
			// Merge: read existing, merge hooks from engine settings
			const existing = readJson<Record<string, unknown>>(CLAUDE_SETTINGS) ?? {};
			const engine = readJson<Record<string, unknown>>(path.join(enginePath, '.claude', 'settings.json'));
			if (engine) {
				// Merge hooks arrays (engine hooks take priority)
				const merged = this.mergeSettings(existing, engine);
				writeJson(CLAUDE_SETTINGS, merged);
			}
		} else {
			copyFile(
				path.join(enginePath, '.claude', 'settings.json'),
				CLAUDE_SETTINGS
			);
		}
	}

	private mergeSettings(
		existing: Record<string, unknown>,
		engine: Record<string, unknown>
	): Record<string, unknown> {
		const result = { ...existing };

		// Merge all engine keys that don't exist in user settings (additive only)
		for (const key of Object.keys(engine)) {
			if (['PreToolUse', 'PostToolUse', 'Stop'].includes(key)) {
				continue; // handled below
			}
			if (!(key in result)) {
				result[key] = engine[key];
			}
		}

		// Merge hook arrays by event type (deduplicate by matcher+command)
		for (const event of ['PreToolUse', 'PostToolUse', 'Stop']) {
			const rawEngineHooks = (engine as Record<string, unknown>)[event];
			if (!Array.isArray(rawEngineHooks)) { continue; }

			const rawExisting = (result as Record<string, unknown>)[event];
			const existingHooks: Array<Record<string, unknown>> = Array.isArray(rawExisting) ? rawExisting : [];
			const existingKeys = new Set(
				existingHooks
					.filter(h => typeof h.matcher === 'string' && typeof h.command === 'string')
					.map(h => `${h.matcher}::${h.command}`)
			);

			for (const hook of rawEngineHooks) {
				if (typeof hook !== 'object' || hook === null) { continue; }
				const h = hook as Record<string, unknown>;
				if (typeof h.matcher !== 'string' || typeof h.command !== 'string') { continue; }
				const hookKey = `${h.matcher}::${h.command}`;
				if (!existingKeys.has(hookKey)) {
					existingHooks.push(h);
				}
			}
			(result as Record<string, unknown>)[event] = existingHooks;
		}

		return result;
	}
}
