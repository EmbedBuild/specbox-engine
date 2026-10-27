import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';
import * as cp from 'child_process';
import { markDone } from './design';
import {
  ClientConfigCase, MigrationPlan,
  detectClientConfigCase, planMigration, buildMigrationSummary, renderSummaryText,
  backupAndMigrate, readClientSettings, settingsLocalPath,
} from './migration';
import {
	GitRunner, defaultGitRunner, isManagedPath,
	fetchRemote, latestReleaseTag, checkoutRelease, compareSemver,
	shouldReinstallExtension, parseInstalledVersion,
} from './install';
import { HealthChecker } from './health';

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

		// Phase -1 — remote version check (US-14, UC-1401..1404): fetch the tags,
		// and if the newest published release is newer than the local one, offer an
		// actionable X→Y upgrade. Self-contained and fire-and-forget — any failure
		// (no network, no git) skips silently and the rest of the flow continues
		// unchanged (AC-03). When the user accepts and the upgrade applies, Phase 1's
		// rebuild + reload supersede the rest, so we return.
		//
		// UC-10807: there is no automatic pull any more. The managed clone only
		// moves when the person accepts a release here, so «Later» really waits and
		// a commit on `main` never reaches anyone without a tag.
		if (enginePath) {
			try {
				const handled = await this.checkRemoteAndOffer(enginePath, engineVersion);
				if (handled === 'reloading') { return; }
			} catch (err) {
				console.warn('[specbox] updater: remote-check phase failed:', err);
			}
		}

		// Phase 1 — binary: reinstall the extension when the engine is NEWER than
		// the running extension. Equal or older is a no-op (UC-4307: an engine
		// behind the extension must never trigger a downgrade), and the rest of the
		// flow still runs (config migration is independent of an extension rebuild).
		if (enginePath && shouldReinstallExtension(engineVersion, this.extensionVersion)) {
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
			// UC-9605 — the same MCP check as the «MCP SpecBox» row of the panel.
			const mcpConfigured = new HealthChecker().checkMcpConfigured('specbox-engine').configured;
			detected = detectClientConfigCase(settings, { mcpConfigured });
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
		// Actionable case: offer its button (non-blocking) — undo the migration, or run the
		// command that finishes the setup, with the title VSCode shows for it (UC-9605).
		const label = summary.button === 'onboard' ? vscode.l10n.t('SpecBox: Onboard Project') : vscode.l10n.t('Revert');
		const command = summary.button === 'onboard' ? 'specbox.onboard' : 'specbox.revertMigration';
		vscode.window.showInformationMessage(text, label).then((choice) => {
			if (choice === label) {
				vscode.commands.executeCommand(command);
			}
		});
	}

	private async rebuildExtension(enginePath: string, engineVersion: string): Promise<void> {
		// UC-10807: only the managed clone, and only in a trusted workspace, may run
		// its install-ext.mjs. Before, any folder with an ENGINE_VERSION.yaml of a
		// higher version ran its own script, also in Restricted Mode (ENG-D-01).
		if (!isManagedPath(enginePath) || !vscode.workspace.isTrusted) {
			vscode.window.showInformationMessage(
				vscode.l10n.t('SpecBox Engine v{0} is available: update the SpecBox extension from the Marketplace.', engineVersion),
			);
			return;
		}
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
			// UC-4307 — ask for exactly this version: the Marketplace first, then a
			// local package of that same version, then a build. Never "whatever
			// .vsix happens to be in the folder".
			const result = await new Promise<string | null>((resolve) => {
				cp.execFile(
					'node',
					[scriptPath, '--prefer-marketplace', '--expect', engineVersion],
					{ cwd: enginePath, timeout: 180_000 },
					(err, stdout) => { resolve(err ? null : stdout.trim()); },
				);
			});
			const installed = parseInstalledVersion(result);
			if (result !== null && installed === engineVersion) {
				const reload = vscode.l10n.t('Reload Now');
				const choice = await vscode.window.showInformationMessage(
					markDone(vscode.l10n.t('SpecBox Extension updated to v{0}. Reload to activate?', installed)),
					reload,
				);
				if (choice === reload) {
					await vscode.commands.executeCommand('workbench.action.reloadWindow');
				}
			} else if (result !== null && installed) {
				vscode.window.showErrorMessage(
					vscode.l10n.t('SpecBox Extension update installed v{0} instead of v{1}. Install it from the Marketplace or run: node vscode-extension/install-ext.mjs', installed, engineVersion),
				);
			} else {
				vscode.window.showErrorMessage(
					vscode.l10n.t('Extension update failed. Try manually: node vscode-extension/install-ext.mjs'),
				);
			}
		});
	}

	/**
	 * Phase -1 (US-14): fetch the tags, find the newest release, and — if it is
	 * strictly newer than `localVersion` — offer an actionable X→Y upgrade. Only for
	 * the managed clone (UC-10807): a clone of your own is yours to update.
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
		if (!isManagedPath(enginePath)) { return 'noop'; }

		// UC-1401 AC-01: fetch (tags included). Non-throwing; a failure (no network,
		// no git → code 127) just means we cannot compare → skip silently (AC-03).
		const fetched = await fetchRemote(enginePath, this.gitRunner);
		if (fetched.code !== 0) { return 'noop'; }

		// UC-10807: the newest published release (vX.Y.Z tag). null → skip silently.
		const tag = await latestReleaseTag(enginePath, this.gitRunner);
		if (!tag) { return 'noop'; }
		const remoteVersion = tag.replace(/^v/, '');

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
			return this.applyUpgrade(enginePath, tag);
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
	 * Apply the accepted upgrade (UC-1403): put the managed clone on the release tag
	 * inside a progress notification, then VERIFY by re-reading ENGINE_VERSION.yaml —
	 * a checkout that reports success but did not move the version is surfaced as an
	 * error, never declared a success (AC-11). A failed checkout (local changes in
	 * the clone) is a warning and nothing is reset. Returns 'reloading' only when the
	 * upgrade applied and the user chose to reload.
	 */
	private async applyUpgrade(enginePath: string, tag: string): Promise<'reloading' | 'noop'> {
		const moved = await vscode.window.withProgress({
			location: vscode.ProgressLocation.Notification,
			title: vscode.l10n.t('SpecBox: updating engine…'),
			cancellable: false,
		}, async () => checkoutRelease(enginePath, tag, this.gitRunner));

		if (moved.code !== 0) {
			vscode.window.showWarningMessage(
				vscode.l10n.t('SpecBox: could not update the engine ({0}). Continuing with the local copy.', moved.stderr.trim() || `git exited with code ${moved.code}`),
			);
			return 'noop';
		}

		return this.verifyAndFinish(enginePath, tag.replace(/^v/, ''));
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
		// AC-11: the checkout "succeeded" but the version did not change → do not lie.
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
