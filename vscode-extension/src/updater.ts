import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';
import * as cp from 'child_process';
import {
  ClientConfigCase, MigrationPlan,
  detectClientConfigCase, planMigration, buildMigrationSummary, renderSummaryText,
  backupAndMigrate, readClientSettings, settingsLocalPath,
} from './migration';
import { GitRunner, defaultGitRunner, isManagedPath } from './install';

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
	constructor(private extensionVersion: string) {}

	/**
	 * Orchestrate the full post-update flow without blocking activation.
	 * Each phase has its own try/catch so a thrown error is logged and the flow
	 * continues to the next phase or exits cleanly (AC-01 of UC-666).
	 */
	async runUpdateFlow(enginePath: string | null): Promise<void> {
		const engineVersion = this.resolveEngineVersion(enginePath);
		if (!engineVersion) { return; }

		// Phase 0 — pull the managed clone up to date before reinstalling skills/hooks
		// (UC-111). Only touches the managed dir; a user clone is skipped. A failed
		// pull (no network, diverged history) is a non-blocking warning — the flow
		// continues with the local copy and never aborts activation (AC-07,
		// fire-and-forget pattern of v6.6.2).
		if (enginePath) {
			try {
				const pull = await pullManagedEngine(enginePath);
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
