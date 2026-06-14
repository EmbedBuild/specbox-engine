import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';
import * as cp from 'child_process';
import {
  ClientConfigCase, MigrationPlan,
  detectClientConfigCase, planMigration, buildMigrationSummary, renderSummaryText,
  backupAndMigrate, readClientSettings, settingsLocalPath,
} from './migration';
import {
	GitRunner, defaultGitRunner, isManagedPath,
	fetchRemote, remoteEngineVersion, compareSemver, isDivergedFromRemote,
	DEFAULT_REMOTE_BRANCH,
} from './install';

/** Outcome of pulling the managed clone. `skipped` means the engine is a user clone (untouched). */
export interface PullResult { ok: boolean; skipped?: boolean; error?: string; }

/**
 * Fast-forward the managed engine clone (UC-111). Effects (git) but NEVER throws.
 *
 * - If `enginePath` is NOT the managed dir → no-op `{ ok:true, skipped:true }`:
 *   a user's own clone is never touched (AC-06, ICP-1 protection).
 * - `git pull --ff-only` so local edits are never overwritten and a diverged
 *   history fails cleanly into a non-blocking warning (AC-07).
 */
export async function pullManagedEngine(
  enginePath: string,
  deps: { gitRunner?: GitRunner } = {},
): Promise<PullResult> {
  if (!isManagedPath(enginePath)) { return { ok: true, skipped: true }; }
  const gitRunner = deps.gitRunner ?? defaultGitRunner;
  try {
    const res = await gitRunner(['pull', '--ff-only'], enginePath);
    if (res.code !== 0) {
      return { ok: false, error: res.stderr.trim() || `git pull exited with code ${res.code}` };
    }
    return { ok: true };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : String(err) };
  }
}

/**
 * Self-update mechanism + post-update orchestrator (UC-666).
 *
 * The update flow runs as a pipeline of phases:
 *   binary (rebuild/reinstall) → detect config case → migrate → summary
 *
 * Each phase is wrapped so a failure in one CANNOT wedge activation or abort the
 * rest of the flow (fire-and-forget pattern of v6.6.2 — see extension.ts, which
 * calls runUpdateFlow with `void`, never awaiting it). UC-665's destructive gate
 * is respected here: only auto-applicable (transport-only) plans run
 * automatically; anything that moves data is surfaced for explicit confirmation.
 */
export class ExtensionUpdater {
	/** Remote versions the user chose to postpone — lives for this session only (US-14 AC-08). */
	private postponedVersions = new Set<string>();

	/**
	 * @param extensionVersion the running extension version (package.json).
	 * @param gitRunner injectable git runner so the remote check (US-14) is testable
	 *   without touching git or the network; defaults to the real runner.
	 */
	constructor(
		private extensionVersion: string,
		private gitRunner: GitRunner = defaultGitRunner,
	) {}

	/**
	 * Orchestrate the full post-update flow without blocking activation.
	 * Each phase has its own try/catch so a thrown error is logged and the flow
	 * continues to the next phase or exits cleanly (AC-01 of UC-666).
	 */
	async runUpdateFlow(enginePath: string | null): Promise<void> {
		const engineVersion = this.resolveEngineVersion(enginePath);
		if (!engineVersion) { return; }

		// Phase -1 — remote version check (US-14, UC-1401..1404). BEFORE the pull:
		// fetch origin, read the version on origin/main, and if it is newer than the
		// local one, offer an actionable X→Y upgrade. Self-contained and fire-and-
		// forget — any failure (no network, no git) skips silently and the rest of
		// the flow continues unchanged (AC-03). When the user accepts and the upgrade
		// applies, the engineVersion below is already stale, but Phase 1's rebuild +
		// reload supersede it, so we simply return after a successful applied upgrade.
		if (enginePath) {
			try {
				const handled = await this.checkRemoteAndOffer(enginePath, engineVersion);
				if (handled === 'reloading') { return; }
			} catch (err) {
				console.warn('[specbox] updater: remote-check phase failed:', err);
			}
		}

		// Phase 0 — pull the managed clone up to date before reinstalling skills/hooks
		// (UC-111). Only touches the managed dir; a user clone is skipped. A failed
		// pull (no network, diverged history) is a non-blocking warning — the flow
		// continues with the local copy and never aborts activation (AC-07,
		// fire-and-forget pattern of v6.6.2).
		if (enginePath) {
			try {
				const pull = await pullManagedEngine(enginePath, { gitRunner: this.gitRunner });
				if (!pull.ok && !pull.skipped) {
					vscode.window.showWarningMessage(
						vscode.l10n.t('SpecBox: could not update the managed engine ({0}). Continuing with the local copy.', pull.error ?? 'unknown error'),
					);
				}
			} catch (err) {
				console.warn('[specbox] updater: pull phase failed:', err);
			}
		}

		// Phase 1 — binary: rebuild/reinstall the extension if the version drifted.
		// On a version match this is a no-op and the rest of the flow still runs
		// (config migration is independent of an extension rebuild).
		if (engineVersion !== this.extensionVersion && enginePath) {
			try {
				await this.rebuildExtension(enginePath, engineVersion);
			} catch (err) {
				console.warn('[specbox] updater: binary phase failed:', err);
			}
		}

		// Phase 2 — detect config case (never throws; defaults to onboarding_incomplete).
		let detected: ClientConfigCase = 'onboarding_incomplete';
		let plan: MigrationPlan;
		try {
			const settingsPath = settingsLocalPath();
			const settings = readClientSettings(settingsPath);
			detected = detectClientConfigCase(settings);
			plan = planMigration(detected, this.extensionVersion);
		} catch (err) {
			console.warn('[specbox] updater: detect phase failed:', err);
			plan = planMigration('onboarding_incomplete', this.extensionVersion);
		}

		// Phase 3 — migrate (only when auto-applicable; destructive plans are gated).
		let backupPath: string | null = null;
		try {
			if (plan.autoApplicable && !plan.requiresConfirmation) {
				backupPath = this.migrate();
			}
		} catch (err) {
			console.warn('[specbox] updater: migrate phase failed:', err);
		}

		// Phase 4 — summary (non-blocking notification, per-case copy).
		try {
			this.showSummary(plan, engineVersion, backupPath);
		} catch (err) {
			console.warn('[specbox] updater: summary phase failed:', err);
		}
	}

	/** Back up + migrate settings.local.json. Returns the backup path. */
	private migrate(): string | null {
		const settingsPath = settingsLocalPath();
		const stamp = utcStamp();
		const { backupPath } = backupAndMigrate(settingsPath, stamp);
		return backupPath;
	}

	/** Show the per-case pedagogical summary (minimal for no-op cases — AC-02). */
	private showSummary(plan: MigrationPlan, toVersion: string, backupPath: string | null): void {
		const summary = buildMigrationSummary(plan, { toVersion, backupPath });
		const text = renderSummaryText(summary);
		if (summary.minimal) {
			// AC-02 of UC-666: minimal, no prompts.
			vscode.window.showInformationMessage(text);
			return;
		}
		// Actionable case: offer revert as a button (non-blocking).
		const revert = vscode.l10n.t('Revert');
		vscode.window.showInformationMessage(text, revert).then((choice) => {
			if (choice === revert) {
				vscode.commands.executeCommand('specbox.revertMigration');
			}
		});
	}

	private async rebuildExtension(enginePath: string, engineVersion: string): Promise<void> {
		await vscode.window.withProgress({
			location: vscode.ProgressLocation.Notification,
			title: vscode.l10n.t('SpecBox: Updating extension...'),
			cancellable: false,
		}, async (progress) => {
			const scriptPath = path.join(enginePath, 'vscode-extension', 'install-ext.mjs');
			if (!fs.existsSync(scriptPath)) {
				vscode.window.showErrorMessage(
					vscode.l10n.t('install-ext.mjs not found in engine repo. Pull the latest version.'),
				);
				return;
			}
			progress.report({ message: vscode.l10n.t('Building and installing...') });
			const result = await new Promise<string | null>((resolve) => {
				cp.execFile('node', [scriptPath], { cwd: enginePath, timeout: 120_000 }, (err, stdout) => {
					resolve(err ? null : stdout.trim());
				});
			});
			if (result !== null) {
				const reload = vscode.l10n.t('Reload Now');
				const choice = await vscode.window.showInformationMessage(
					vscode.l10n.t('SpecBox Extension updated to v{0}. Reload to activate?', engineVersion),
					reload,
				);
				if (choice === reload) {
					await vscode.commands.executeCommand('workbench.action.reloadWindow');
				}
			} else {
				vscode.window.showErrorMessage(
					vscode.l10n.t('Extension update failed. Try manually: node vscode-extension/install-ext.mjs'),
				);
			}
		});
	}

	/**
	 * Phase -1 (US-14): fetch origin, read the remote version, and — if it is
	 * strictly newer than `localVersion` — offer an actionable X→Y upgrade.
	 *
	 * Returns:
	 *  - 'reloading' when the upgrade applied AND the user accepted a reload (the
	 *    caller stops the flow; the window is reloading).
	 *  - 'noop' for every other path: no network, no upgrade available, the user
	 *    postponed, the upgrade was offered but not completed, etc. The caller
	 *    continues the normal flow.
	 *
	 * Never throws (callers also wrap it). UC-1401 AC-01..03, UC-1402 AC-04..08.
	 */
	private async checkRemoteAndOffer(
		enginePath: string,
		localVersion: string,
	): Promise<'reloading' | 'noop'> {
		// UC-1401 AC-01: fetch (tags included). Non-throwing; a failure (no network,
		// no git → code 127) just means we cannot compare → skip silently (AC-03).
		const fetched = await fetchRemote(enginePath, this.gitRunner);
		if (fetched.code !== 0) { return 'noop'; }

		// UC-1401 AC-02: read origin/main:ENGINE_VERSION.yaml. null → skip silently.
		const remoteVersion = await remoteEngineVersion(enginePath, this.gitRunner);
		if (!remoteVersion) { return 'noop'; }

		// UC-1402 AC-04 / AC-06: numeric semver compare. Only a strictly-newer remote
		// is an upgrade; equal or local-ahead (the engine developer's case) shows nothing.
		if (compareSemver(remoteVersion, localVersion) <= 0) { return 'noop'; }

		// UC-1402 AC-08: do not re-prompt for a version the user already postponed
		// this session. A still-newer version would not be in the set, so it re-prompts.
		if (this.postponedVersions.has(remoteVersion)) { return 'noop'; }

		// UC-1402 AC-05: actionable modal X→Y with the three canonical buttons.
		const update = vscode.l10n.t('Update now');
		const changes = vscode.l10n.t('View changes');
		const later = vscode.l10n.t('Later');
		const choice = await vscode.window.showInformationMessage(
			vscode.l10n.t('SpecBox Engine v{0} → v{1} available. Update?', localVersion, remoteVersion),
			{ modal: true },
			update, changes, later,
		);

		if (choice === changes) {
			// UC-1402 AC-07: open the CHANGELOG, then re-offer the decision.
			await this.openChangelog(enginePath);
			return this.checkRemoteAndOffer(enginePath, localVersion);
		}
		if (choice === update) {
			return this.applyUpgrade(enginePath, remoteVersion);
		}
		// Later or dismissed (undefined): postpone this version for the session.
		this.postponedVersions.add(remoteVersion);
		return 'noop';
	}

	/** Open the engine CHANGELOG.md in a preview (UC-1402 AC-07). Best-effort. */
	private async openChangelog(enginePath: string): Promise<void> {
		const changelog = path.join(enginePath, 'CHANGELOG.md');
		if (!fs.existsSync(changelog)) { return; }
		try {
			const doc = await vscode.workspace.openTextDocument(changelog);
			await vscode.window.showTextDocument(doc, { preview: true });
		} catch (err) {
			console.warn('[specbox] updater: could not open CHANGELOG:', err);
		}
	}

	/**
	 * Apply the accepted upgrade (UC-1403). `git pull --ff-only` inside a progress
	 * notification, then VERIFY by re-reading ENGINE_VERSION.yaml — a pull that
	 * reports success but did not move the version is surfaced as an error, never
	 * declared a success (AC-11). On a diverged history (--ff-only fails) it routes
	 * to the gated reset path (UC-1404). Returns 'reloading' only when the upgrade
	 * applied and the user chose to reload.
	 */
	private async applyUpgrade(enginePath: string, targetVersion: string): Promise<'reloading' | 'noop'> {
		const pull = await vscode.window.withProgress({
			location: vscode.ProgressLocation.Notification,
			title: vscode.l10n.t('SpecBox: updating engine…'),
			cancellable: false,
		}, async () => this.gitRunner(['pull', '--ff-only'], enginePath));

		if (pull.code !== 0) {
			// --ff-only failed. If it is because the history diverged, offer the gated
			// reset-with-backup path (UC-1404). Otherwise it is a transient failure.
			const diverged = await isDivergedFromRemote(enginePath, this.gitRunner);
			if (diverged) {
				return this.handleDivergence(enginePath, targetVersion);
			}
			vscode.window.showWarningMessage(
				vscode.l10n.t('SpecBox: could not update the engine ({0}). Continuing with the local copy.', pull.stderr.trim() || `git exited with code ${pull.code}`),
			);
			return 'noop';
		}

		return this.verifyAndFinish(enginePath, targetVersion);
	}

	/**
	 * Re-read ENGINE_VERSION.yaml and confirm it now equals `targetVersion`
	 * (UC-1403 AC-10/AC-11). On match → rebuild + offer reload. On mismatch →
	 * actionable error, NOT a silent success.
	 */
	private async verifyAndFinish(enginePath: string, targetVersion: string): Promise<'reloading' | 'noop'> {
		const applied = this.resolveEngineVersion(enginePath);
		if (applied && compareSemver(applied, targetVersion) === 0) {
			// AC-10: version moved as expected → rebuild the extension and offer reload.
			await this.rebuildExtension(enginePath, applied);
			return 'reloading';
		}
		// AC-11: the pull "succeeded" but the version did not change → do not lie.
		const openTerminal = vscode.l10n.t('Open Terminal');
		const choice = await vscode.window.showErrorMessage(
			vscode.l10n.t('SpecBox: the upgrade did not apply — still on v{0}. Update manually from a terminal.', applied ?? 'unknown'),
			openTerminal,
		);
		if (choice === openTerminal) {
			vscode.commands.executeCommand('workbench.action.terminal.new');
		}
		return 'noop';
	}

	/**
	 * Diverged managed clone (UC-1404): the engine developer's case. NEVER resets a
	 * user clone (isManagedPath gate, ICP-1). On the managed clone, ask for explicit
	 * confirmation, back up the current branch FIRST (recoverable), then
	 * fetch → checkout default → reset --hard, and verify like AC-10/AC-11.
	 */
	private async handleDivergence(enginePath: string, targetVersion: string): Promise<'reloading' | 'noop'> {
		const branch = await this.currentBranch(enginePath);

		// AC-15 guard / ICP-1: a user clone is never reset — only an informational notice.
		if (!isManagedPath(enginePath)) {
			vscode.window.showWarningMessage(
				vscode.l10n.t('SpecBox: the local engine clone has diverged (branch {0}). Update it manually.', branch ?? 'unknown'),
			);
			return 'noop';
		}

		// AC-12: explicit, modal, destructive confirmation. No reset without it.
		const doReset = vscode.l10n.t('Reset with backup');
		const cancel = vscode.l10n.t('Cancel');
		const choice = await vscode.window.showWarningMessage(
			vscode.l10n.t('The local engine clone has diverged (branch {0}). Updating requires resetting to origin/{1}. Your current branch will be backed up. Continue?', branch ?? 'unknown', DEFAULT_REMOTE_BRANCH),
			{ modal: true },
			doReset, cancel,
		);
		// AC-15: Cancel (or dismiss) leaves the clone untouched — no fetch, checkout or reset.
		if (choice !== doReset) {
			vscode.window.showInformationMessage(
				vscode.l10n.t('SpecBox: engine update cancelled. Continuing with the local copy.'),
			);
			return 'noop';
		}

		// AC-13: back up the current branch BEFORE touching anything (recoverable SHA).
		const backupRef = `specbox-backup/${branch ?? 'detached'}-${utcStamp()}`;
		const backup = await this.gitRunner(['branch', backupRef], enginePath);
		if (backup.code !== 0) {
			vscode.window.showErrorMessage(
				vscode.l10n.t('SpecBox: could not create the backup branch ({0}). Aborting the reset.', backup.stderr.trim() || `git exited with code ${backup.code}`),
			);
			return 'noop';
		}

		// AC-14: only after confirmation → fetch + checkout default + reset --hard, then verify.
		const result = await vscode.window.withProgress({
			location: vscode.ProgressLocation.Notification,
			title: vscode.l10n.t('SpecBox: updating engine…'),
			cancellable: false,
		}, async (): Promise<'reloading' | 'noop'> => {
			const steps: string[][] = [
				['fetch', 'origin'],
				['checkout', DEFAULT_REMOTE_BRANCH],
				['reset', '--hard', `origin/${DEFAULT_REMOTE_BRANCH}`],
			];
			for (const args of steps) {
				const r = await this.gitRunner(args, enginePath);
				if (r.code !== 0) {
					vscode.window.showErrorMessage(
						vscode.l10n.t('SpecBox: reset failed at `git {0}` ({1}). Your branch is safe at {2}.', args.join(' '), r.stderr.trim() || `code ${r.code}`, backupRef),
					);
					return 'noop';
				}
			}
			return this.verifyAndFinish(enginePath, targetVersion);
		});

		if (result === 'reloading') {
			vscode.window.showInformationMessage(
				vscode.l10n.t('SpecBox: engine reset to origin/{0}. Previous work backed up at {1}.', DEFAULT_REMOTE_BRANCH, backupRef),
			);
		}
		return result;
	}

	/** Current branch name (or null if detached / git fails). Used for backup naming. */
	private async currentBranch(enginePath: string): Promise<string | null> {
		const r = await this.gitRunner(['rev-parse', '--abbrev-ref', 'HEAD'], enginePath);
		if (r.code !== 0) { return null; }
		const name = r.stdout.trim();
		return name && name !== 'HEAD' ? name : null;
	}

	/** Backwards-compatible alias for the old entry point. */
	async checkAndUpdate(enginePath: string | null): Promise<void> {
		return this.runUpdateFlow(enginePath);
	}

	private resolveEngineVersion(enginePath: string | null): string | null {
		if (!enginePath) { return null; }
		try {
			const content = fs.readFileSync(path.join(enginePath, 'ENGINE_VERSION.yaml'), 'utf-8');
			const m = content.match(/^version:\s*(.+)/m);
			return m?.[1]?.trim() ?? null;
		} catch {
			return null;
		}
	}
}

/** UTC timestamp YYYYMMDDTHHMMSSZ for backup filenames. */
function utcStamp(): string {
	const d = new Date();
	const p = (n: number) => String(n).padStart(2, '0');
	return `${d.getUTCFullYear()}${p(d.getUTCMonth() + 1)}${p(d.getUTCDate())}`
		+ `T${p(d.getUTCHours())}${p(d.getUTCMinutes())}${p(d.getUTCSeconds())}Z`;
}
