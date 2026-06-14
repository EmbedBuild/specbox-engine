import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import * as cp from 'child_process';
import {
	CLAUDE_SKILLS_DIR, CLAUDE_HOOKS_DIR, CLAUDE_HOOKS_LIB_DIR,
	CLAUDE_COMMANDS_DIR, CLAUDE_SETTINGS
} from './constants';
import { ensureDir, symlinkOrCopy, copyFile, readJson, writeJson } from './util';
import { HealthChecker } from './health';

// US-VSCODE-AUTOCLONE / UC-109 — managed-engine pure helpers.
//
// Pure core (no vscode, no git, no network) so it is testable from
// out/install.js with node:test, mirroring the pure/UI split of
// prerequisites.ts. The auto-clone effects (UC-110) live below in the class
// and accept an injectable git runner so tests never touch git or the network.

/** Canonical public engine repo, cloned when the extension can't find a local copy. */
export const ENGINE_REPO_URL = 'https://github.com/EmbedBuild/specbox-engine.git';

/** Absolute path of the extension-managed engine clone: `~/.specbox/specbox-engine`. */
export function managedEnginePath(): string {
	return path.join(os.homedir(), '.specbox', 'specbox-engine');
}

/**
 * True only when `p` resolves to exactly the managed clone directory.
 * A user's own clone in any other location returns false — that copy is never
 * touched by auto-clone or auto-pull (ICP-1 protection).
 */
export function isManagedPath(p: string): boolean {
	if (!p) { return false; }
	return path.resolve(p) === managedEnginePath();
}

/** Result of a git invocation: exit code + captured streams. Never throws. */
export interface GitRunResult { code: number; stdout: string; stderr: string; }

/** Injectable git runner — defaults to `git` via child_process; tests pass a stub. */
export type GitRunner = (args: string[], cwd?: string) => Promise<GitRunResult>;

/** Default git runner. Resolves with code 127 + stderr if `git` is absent (ENOENT). */
export const defaultGitRunner: GitRunner = (args, cwd) =>
	new Promise((resolve) => {
		cp.execFile('git', args, { cwd, timeout: 120_000 }, (err, stdout, stderr) => {
			if (err && (err as NodeJS.ErrnoException).code === 'ENOENT') {
				resolve({ code: 127, stdout: '', stderr: 'git not found' });
				return;
			}
			const code = err && typeof (err as { code?: unknown }).code === 'number'
				? (err as { code: number }).code
				: (err ? 1 : 0);
			resolve({ code, stdout: stdout ?? '', stderr: stderr ?? '' });
		});
	});

// US-14 (UC-1401, UC-1402) — remote-version pure helpers.
//
// Same pure/IO split as the auto-clone helpers above: a git runner is injected
// so tests never touch git or the network. These power the start-up remote check
// in updater.ts: fetch the remote, read the version published on origin/<branch>,
// and compare it (semver-numeric) against the local ENGINE_VERSION.yaml.

/** Default branch the managed clone tracks. The remote version is read from its tip. */
export const DEFAULT_REMOTE_BRANCH = 'main';

/**
 * Fetch from origin (tags included). Effects (git) but NEVER throws — returns the
 * GitRunResult so the caller stays fire-and-forget. A missing git resolves to
 * code 127, a network error to a non-zero code; both are handled by the caller
 * (no dialog, activation continues — US-14 AC-03).
 */
export async function fetchRemote(
	enginePath: string,
	gitRunner: GitRunner = defaultGitRunner,
): Promise<GitRunResult> {
	return gitRunner(['fetch', 'origin', '--tags'], enginePath);
}

/**
 * Read the `version:` field of ENGINE_VERSION.yaml as published on
 * `origin/<branch>` (default `main`) via `git show`. Returns the trimmed version
 * string, or null when the command fails (no network, no remote, file absent) —
 * the caller then silently skips the remote check (US-14 AC-02, AC-03).
 *
 * Uses the same `/^version:\s*(.+)/m` regex as updater.ts::resolveEngineVersion
 * so the local and remote sides parse identically.
 */
export async function remoteEngineVersion(
	enginePath: string,
	gitRunner: GitRunner = defaultGitRunner,
	branch: string = DEFAULT_REMOTE_BRANCH,
): Promise<string | null> {
	const res = await gitRunner(['show', `origin/${branch}:ENGINE_VERSION.yaml`], enginePath);
	if (res.code !== 0) { return null; }
	const m = res.stdout.match(/^version:\s*(.+)/m);
	return m?.[1]?.trim() ?? null;
}

/**
 * Compare two semver-ish strings numerically (major.minor.patch). Returns
 * -1 if a<b, 0 if equal, 1 if a>b. Missing segments count as 0, so "6.10" == "6.10.0".
 * A non-numeric segment is treated as 0. This is why a plain string compare is
 * wrong: "6.9.4" > "6.10.2" lexicographically, but 6.9.4 < 6.10.2 numerically
 * (US-14 AC-04). Local ~15-line helper to avoid pulling a semver dependency.
 */
export function compareSemver(a: string, b: string): -1 | 0 | 1 {
	const parse = (v: string): number[] =>
		v.trim().replace(/^v/, '').split('.').slice(0, 3).map((s) => {
			const n = parseInt(s, 10);
			return Number.isNaN(n) ? 0 : n;
		});
	const pa = parse(a);
	const pb = parse(b);
	for (let i = 0; i < 3; i++) {
		const x = pa[i] ?? 0;
		const y = pb[i] ?? 0;
		if (x < y) { return -1; }
		if (x > y) { return 1; }
	}
	return 0;
}

/**
 * Decide whether a failed `git pull --ff-only` failed *because the history
 * diverged* (local commits / a feature branch that is not a fast-forward of the
 * remote) rather than for a transient reason. Combines the stderr text with the
 * ahead-count from `git rev-list` so detection does not rely on git's wording
 * alone (which varies by git version and locale) — US-14 AC-12.
 *
 * Returns false on a clean tree, on a transient error (network), or when git is
 * absent. Never throws.
 */
export async function isDivergedFromRemote(
	enginePath: string,
	gitRunner: GitRunner = defaultGitRunner,
	branch: string = DEFAULT_REMOTE_BRANCH,
): Promise<boolean> {
	const res = await gitRunner(
		['rev-list', '--left-right', '--count', `origin/${branch}...HEAD`],
		enginePath,
	);
	if (res.code !== 0) { return false; }
	// Output is "<behind>\t<ahead>". Ahead > 0 means local has commits the remote
	// lacks → a --ff-only pull cannot fast-forward.
	const parts = res.stdout.trim().split(/\s+/);
	const ahead = parseInt(parts[1] ?? '0', 10);
	return Number.isFinite(ahead) && ahead > 0;
}

/** Injectable filesystem + git deps for cloneManagedEngine — all optional, real by default. */
export interface CloneDeps {
	gitRunner?: GitRunner;
	existsSync?: (p: string) => boolean;
	mkdirSync?: (p: string, opts: fs.MakeDirectoryOptions) => void;
	rmSync?: (p: string, opts: fs.RmOptions) => void;
}

export interface CloneResult { ok: boolean; path?: string; error?: string; }

/**
 * Clone the public engine into the managed directory (`~/.specbox/specbox-engine`).
 *
 * Effects (git + fs) but NEVER throws — returns a plain result so the caller's
 * activation flow can stay fire-and-forget (NFR: no activation hang). On any
 * failure (git missing, network down, clone produced no ENGINE_VERSION.yaml) it
 * removes the partial directory so future detections aren't poisoned (AC-05),
 * and reports `{ ok:false, error }`.
 */
export async function cloneManagedEngine(deps: CloneDeps = {}): Promise<CloneResult> {
	const gitRunner = deps.gitRunner ?? defaultGitRunner;
	const existsSync = deps.existsSync ?? fs.existsSync;
	const mkdirSync = deps.mkdirSync ?? fs.mkdirSync;
	const rmSync = deps.rmSync ?? fs.rmSync;

	const dest = managedEnginePath();
	const parent = path.dirname(dest); // ~/.specbox

	const cleanupPartial = () => {
		try {
			if (existsSync(dest)) { rmSync(dest, { recursive: true, force: true }); }
		} catch { /* best-effort cleanup */ }
	};

	try {
		if (!existsSync(parent)) { mkdirSync(parent, { recursive: true }); }

		const res = await gitRunner(['clone', ENGINE_REPO_URL, dest]);
		if (res.code !== 0) {
			cleanupPartial();
			const why = res.code === 127 ? 'git is not installed' : (res.stderr.trim() || `git exited with code ${res.code}`);
			return { ok: false, error: why };
		}

		// A successful clone must yield a real engine repo.
		if (!existsSync(path.join(dest, 'ENGINE_VERSION.yaml'))) {
			cleanupPartial();
			return { ok: false, error: 'clone completed but ENGINE_VERSION.yaml is missing' };
		}

		return { ok: true, path: dest };
	} catch (err) {
		cleanupPartial();
		return { ok: false, error: err instanceof Error ? err.message : String(err) };
	}
}

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

		// 3.5. Auto-clone the public engine into the managed dir (UC-110).
		// Automatic (notify, don't ask) — the repo is public and the destination
		// is our own managed folder. The showOpenDialog below is reached only if
		// the clone fails. Idempotent: a managed clone already on disk is returned
		// without re-cloning (it would also have matched step 3 if at a common path).
		const autoCloned = await this.tryAutoCloneEngine();
		if (autoCloned) { return autoCloned; }

		// 4. Ask user (degradation: clone unavailable/failed)
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

	/**
	 * Step 3.5 of resolveEnginePath: auto-clone the managed engine when no local
	 * copy was found. Returns the managed path on success, or null to fall through
	 * to the showOpenDialog degradation. Never throws (cloneManagedEngine is safe).
	 *
	 * @param deps injectable for tests (clone fn + existence probe).
	 */
	async tryAutoCloneEngine(deps: {
		clone?: (d?: CloneDeps) => Promise<CloneResult>;
		existsSync?: (p: string) => boolean;
	} = {}): Promise<string | null> {
		const clone = deps.clone ?? cloneManagedEngine;
		const existsSync = deps.existsSync ?? fs.existsSync;
		const managed = managedEnginePath();

		// Idempotency (NFR): a managed clone already on disk is used as-is.
		if (existsSync(path.join(managed, 'ENGINE_VERSION.yaml'))) {
			return managed;
		}

		const result = await vscode.window.withProgress({
			location: vscode.ProgressLocation.Notification,
			title: vscode.l10n.t('SpecBox Engine'),
			cancellable: false,
		}, async (progress) => {
			progress.report({ message: vscode.l10n.t('Cloning SpecBox Engine…') });
			return clone();
		});

		if (result.ok && result.path) {
			vscode.window.showInformationMessage(vscode.l10n.t('SpecBox Engine cloned.'));
			await vscode.workspace.getConfiguration('specbox').update('enginePath', result.path, vscode.ConfigurationTarget.Global);
			return result.path;
		}

		// Degrade to manual selection with an actionable message.
		vscode.window.showErrorMessage(
			vscode.l10n.t('Could not clone the SpecBox Engine ({0}). Install git and check your network, or select the folder manually.', result.error ?? 'unknown error'),
		);
		return null;
	}

	getInstalledSkills(): string[] {
		if (!fs.existsSync(CLAUDE_SKILLS_DIR)) { return []; }
		let entries: fs.Dirent[];
		try {
			entries = fs.readdirSync(CLAUDE_SKILLS_DIR, { withFileTypes: true });
		} catch {
			return [];
		}
		// Accept both real directories and symlinks (installSkills() uses
		// symlinkOrCopy(), so most entries are symlinks pointing at the
		// engine repo). Dirent.isDirectory() is false for symlinks.
		return entries
			.filter(e => (e.isDirectory() || e.isSymbolicLink()) && fs.existsSync(path.join(CLAUDE_SKILLS_DIR, e.name, 'SKILL.md')))
			.map(e => e.name)
			.sort();
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
