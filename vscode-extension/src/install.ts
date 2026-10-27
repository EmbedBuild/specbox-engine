import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import * as cp from 'child_process';
import {
	CLAUDE_SKILLS_DIR, CLAUDE_HOOKS_DIR, CLAUDE_HOOKS_LIB_DIR,
	CLAUDE_COMMANDS_DIR, CLAUDE_SETTINGS, KNOWN_SKILLS
} from './constants';
import { ensureDir, symlinkOrCopy, copyFile, readJson, writeJson } from './util';
import { HealthChecker, isReadableFile, specboxSkillsState } from './health';

import { markDone } from './design';
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
// in updater.ts: fetch the remote, find the newest published release, and compare
// it (semver-numeric) against the local ENGINE_VERSION.yaml.
//
// UC-10807 (US-108): the managed clone follows the published releases, the vX.Y.Z
// tags, not `main`. Before, every activation pulled `main`, so any commit there
// reached every user within two activations, without a tag or the Marketplace
// (audit of 2026-10-27, ENG-D-02).

/** The newest release tag (`vX.Y.Z`) the clone knows, or null. Never throws. */
export async function latestReleaseTag(
	enginePath: string,
	gitRunner: GitRunner = defaultGitRunner,
): Promise<string | null> {
	const res = await gitRunner(['tag', '--list', 'v*', '--sort=-v:refname'], enginePath);
	if (res.code !== 0) { return null; }
	return res.stdout.split('\n').map((s) => s.trim()).find((t) => /^v\d+\.\d+\.\d+$/.test(t)) ?? null;
}

/** Put the clone on a release tag (detached). Returns the git result; never throws. */
export async function checkoutRelease(
	enginePath: string,
	tag: string,
	gitRunner: GitRunner = defaultGitRunner,
): Promise<GitRunResult> {
	return gitRunner(['checkout', '--quiet', '--detach', tag], enginePath);
}

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
 * UC-4307 — reinstall the extension only when the engine is strictly newer.
 * A local engine that is behind (or equal) never triggers a reinstall, so the
 * automatic update can never install an older version than the running one.
 */
export function shouldReinstallExtension(engineVersion: string, extensionVersion: string): boolean {
	return compareSemver(engineVersion, extensionVersion) > 0;
}

/**
 * UC-4307 — the version `install-ext.mjs` reports as actually installed (its
 * `INSTALLED_VERSION=x.y.z` line), or null when it did not report one.
 */
export function parseInstalledVersion(stdout: string | null | undefined): string | null {
	const m = /^INSTALLED_VERSION=(\S+)\s*$/m.exec(stdout ?? '');
	return m ? m[1] : null;
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

		// UC-10807: start on the newest published release, not on `main`.
		const tag = await latestReleaseTag(dest, gitRunner);
		if (tag) {
			const moved = await checkoutRelease(dest, tag, gitRunner);
			if (moved.code !== 0) {
				cleanupPartial();
				return { ok: false, error: moved.stderr.trim() || `git checkout ${tag} exited with code ${moved.code}` };
			}
		}

		return { ok: true, path: dest };
	} catch (err) {
		cleanupPartial();
		return { ok: false, error: err instanceof Error ? err.message : String(err) };
	}
}

// UC-9602 (US-96) — the managed clone puts back the files an earlier install deleted.
//
// Before UC-9601, installing twice on Windows could delete, through the junctions of
// ~/.claude/skills, every skill file of the managed clone (git status: " D"). Only the managed
// clone is touched, and only the files git lists as deleted: `git checkout-index` writes them from
// the index and never overwrites a file that exists, so a modified file stays as it is. `-u`
// refreshes their entries in the index: without it, with core.autocrlf (the Windows default) git
// takes every written file as modified, and the updater's `git pull --ff-only` would refuse.

/** What restoreManagedEngine did; `skipped` says why it did nothing. */
export interface RestoreResult {
	/** Paths written back, as git lists them. */
	restored: string[];
	/** Skills under .claude/skills with at least one file written back. */
	skills: string[];
	skipped?: 'not_managed' | 'no_clone' | 'git_failed';
}

/** Paths per `git checkout-index` call, so the command line stays short on Windows. */
const RESTORE_BATCH = 200;

/** Write back the versioned files missing from the managed clone. Never throws. */
export async function restoreManagedEngine(
	enginePath: string,
	gitRunner: GitRunner = defaultGitRunner,
	existsSync: (p: string) => boolean = fs.existsSync,
): Promise<RestoreResult> {
	if (!isManagedPath(enginePath)) { return { restored: [], skills: [], skipped: 'not_managed' }; }
	if (!existsSync(path.join(enginePath, '.git'))) { return { restored: [], skills: [], skipped: 'no_clone' }; }
	const listed = await gitRunner(['ls-files', '--deleted', '-z'], enginePath);
	if (listed.code !== 0) { return { restored: [], skills: [], skipped: 'git_failed' }; }
	const deleted = [...new Set(listed.stdout.split('\0').filter(Boolean))];
	const restored: string[] = [];
	for (let i = 0; i < deleted.length; i += RESTORE_BATCH) {
		const batch = deleted.slice(i, i + RESTORE_BATCH);
		const res = await gitRunner(['checkout-index', '-u', '--', ...batch], enginePath);
		if (res.code !== 0) { return { restored, skills: skillsIn(restored), skipped: 'git_failed' }; }
		restored.push(...batch);
	}
	return { restored, skills: skillsIn(restored) };
}

function skillsIn(paths: string[]): string[] {
	const names = new Set<string>();
	for (const p of paths) {
		const m = /^\.claude\/skills\/([^/]+)\//.exec(p);
		if (m) { names.add(m[1]); }
	}
	return [...names].sort();
}

// UC-9603 (US-96) — the final notice of «Install Engine» checks the skills it leaves.

export interface InstallSummaryInput {
	engineVersion: string | null;
	/** Skills installed from the engine whose SKILL.md opens through their entry. */
	readableSkills: number;
	/** SpecBox skills Claude Code cannot read after installing. */
	missingSkills: string[];
	hooks: number;
	/** Engram and MCP servers still missing, already in the person's language. */
	missingPieces: string[];
}

export interface InstallSummary {
	level: 'info' | 'warning';
	text: string;
	/** Buttons to offer, in order. */
	actions: Array<'healthCheck' | 'configureMcp'>;
}

/**
 * The final notice. With a SpecBox skill missing it never says the install went well: it names
 * the skills and offers the Health Check. Pure apart from l10n (stubbed in tests).
 */
export function buildInstallSummary(i: InstallSummaryInput): InstallSummary {
	const t = vscode.l10n.t;
	if (i.missingSkills.length > 0) {
		const also = i.missingPieces.length > 0 ? ` ${t('Also missing: {0}.', i.missingPieces.join(', '))}` : '';
		return {
			level: 'warning',
			text: t('SpecBox could not install {0} of {1} SpecBox skills: {2}.', i.missingSkills.length, KNOWN_SKILLS.length, i.missingSkills.join(', ')) + also,
			actions: i.missingPieces.length > 0 ? ['healthCheck', 'configureMcp'] : ['healthCheck'],
		};
	}
	if (i.missingPieces.length > 0) {
		return {
			level: 'warning',
			text: t('SpecBox installed ({0} skills, {1} hooks). Missing: {2}. Configure now?', i.readableSkills, i.hooks, i.missingPieces.join(', ')),
			actions: ['configureMcp'],
		};
	}
	return {
		level: 'info',
		text: markDone(t('SpecBox Engine v{0} installed: {1} skills, {2} hooks, MCP configured.', i.engineVersion ?? '', i.readableSkills, i.hooks)),
		actions: [],
	};
}

export class InstallManager {
	private context: vscode.ExtensionContext;

	/** @param gitRunner injectable so the repair of the managed clone (UC-9602) is testable. */
	constructor(context: vscode.ExtensionContext, private gitRunner: GitRunner = defaultGitRunner) {
		this.context = context;
	}

	/**
	 * UC-9602 — on activation, put back what an earlier install deleted from the managed clone and
	 * say how many skills came back. The links in ~/.claude/skills still point at those folders, so
	 * the skills work again without running a command. A clone elsewhere is never touched. Never throws.
	 */
	async repairManagedEngine(): Promise<RestoreResult> {
		const result = await restoreManagedEngine(managedEnginePath(), this.gitRunner);
		if (result.skills.length === 1) {
			vscode.window.showInformationMessage(
				markDone(vscode.l10n.t('SpecBox recovered 1 skill that an earlier install had deleted from its engine copy.'))
			);
		} else if (result.skills.length > 1) {
			vscode.window.showInformationMessage(
				markDone(vscode.l10n.t('SpecBox recovered {0} skills that an earlier install had deleted from its engine copy.', result.skills.length))
			);
		} else if (result.restored.length > 0) {
			vscode.window.showInformationMessage(
				markDone(vscode.l10n.t('SpecBox restored {0} files missing from its engine copy.', result.restored.length))
			);
		}
		return result;
	}

	async runFullInstall(): Promise<void> {
		const health = new HealthChecker();
		const enginePath = await this.resolveEnginePath();
		if (!enginePath) { return; }

		await vscode.window.withProgress({
			location: vscode.ProgressLocation.Notification,
			title: vscode.l10n.t('SpecBox Engine'),
			cancellable: false,
		}, async (progress) => {
			// 1. Skills — first put back what an earlier install deleted from the managed clone (UC-9602).
			progress.report({ message: vscode.l10n.t('Installing skills...'), increment: 0 });
			await restoreManagedEngine(enginePath, this.gitRunner);
			const skillsResult = this.installSkills(enginePath);

			// 2. Hooks
			progress.report({ message: vscode.l10n.t('Installing hooks...'), increment: 20 });
			const hooksResult = this.installHooks(enginePath);

			// 3. Commands (legacy)
			progress.report({ message: vscode.l10n.t('Installing commands...'), increment: 40 });
			this.installCommands(enginePath);

			// 4. Settings
			progress.report({ message: vscode.l10n.t('Configuring settings...'), increment: 60 });
			this.installSettings(enginePath);

			// 5. Health check
			progress.report({ message: vscode.l10n.t('Verifying installation...'), increment: 80 });
			const result = await health.run();

			progress.report({ message: vscode.l10n.t('Done!'), increment: 100 });

			// Summary — UC-9603: what Claude Code can read, not the links created.
			const missing: string[] = [];
			if (!result.engram.ok) { missing.push('Engram'); }
			if (!result.mcpSpecbox.configured) { missing.push(vscode.l10n.t('MCP SpecBox server')); }
			if (!result.mcpEngram.configured) { missing.push(vscode.l10n.t('MCP Engram server')); }
			const summary = buildInstallSummary({
				engineVersion: result.engineVersion,
				readableSkills: skillsResult.count,
				missingSkills: specboxSkillsState(CLAUDE_SKILLS_DIR).missing,
				hooks: hooksResult.count,
				missingPieces: missing,
			});

			if (summary.level === 'info') {
				vscode.window.showInformationMessage(summary.text);
				return;
			}
			const openHealth = vscode.l10n.t('Open Health Check');
			const configureMcp = vscode.l10n.t('Configure MCP');
			const buttons = summary.actions.map((a) => (a === 'healthCheck' ? openHealth : configureMcp));
			const action = await vscode.window.showWarningMessage(summary.text, ...buttons, vscode.l10n.t('Skip'));
			if (action === openHealth) {
				vscode.commands.executeCommand('specbox.healthCheck');
			} else if (action === configureMcp) {
				vscode.commands.executeCommand('specbox.configureMcp');
			}
		});
	}

	async resolveEnginePath(): Promise<string | null> {
		// 1. Config
		const configured = vscode.workspace.getConfiguration('specbox').get<string>('enginePath');
		if (configured && fs.existsSync(path.join(configured, 'ENGINE_VERSION.yaml'))) {
			return configured;
		}

		// 2. Workspace — only a trusted one (UC-10807): in Restricted Mode, or from a
		// folder you have not trusted, its hooks and skills are never installed.
		for (const folder of vscode.workspace.isTrusted ? vscode.workspace.workspaceFolders ?? [] : []) {
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
			openLabel: vscode.l10n.t('Select SpecBox Engine folder'),
			title: vscode.l10n.t('Where is the SpecBox Engine repository?'),
		});

		if (result?.[0]) {
			const selected = result[0].fsPath;
			if (fs.existsSync(path.join(selected, 'ENGINE_VERSION.yaml'))) {
				// Save for future
				await vscode.workspace.getConfiguration('specbox').update('enginePath', selected, vscode.ConfigurationTarget.Global);
				return selected;
			}
			vscode.window.showErrorMessage(vscode.l10n.t('Selected folder does not contain ENGINE_VERSION.yaml. Not a SpecBox Engine repo.'));
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
			vscode.window.showInformationMessage(markDone(vscode.l10n.t('SpecBox Engine cloned.')));
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
		const names: string[] = [];

		for (const entry of fs.readdirSync(srcDir, { withFileTypes: true })) {
			if (!entry.isDirectory()) { continue; }
			const src = path.join(srcDir, entry.name);
			const dest = path.join(CLAUDE_SKILLS_DIR, entry.name);
			// One skill that cannot be linked does not stop the rest: the final notice names it (UC-9603).
			try {
				symlinkOrCopy(src, dest, 'dir');
			} catch (err) {
				console.warn(`[specbox] could not install the skill ${entry.name}:`, err);
			}
			names.push(entry.name);
		}
		// UC-9603 — count the skills whose SKILL.md opens through their entry, not the entries created.
		return { count: names.filter((n) => isReadableFile(path.join(CLAUDE_SKILLS_DIR, n, 'SKILL.md'))).length };
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
