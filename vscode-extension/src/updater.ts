import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';
import * as cp from 'child_process';

/**
 * Self-update mechanism: compares the installed extension version against
 * ENGINE_VERSION.yaml in the engine repo. If mismatched, rebuilds and
 * reinstalls the extension automatically.
 */
export class ExtensionUpdater {
	constructor(private extensionVersion: string) {}

	async checkAndUpdate(enginePath: string | null): Promise<void> {
		if (!enginePath) { return; }

		const engineVersion = this.readEngineVersion(enginePath);
		if (!engineVersion) { return; }

		if (engineVersion === this.extensionVersion) { return; }

		const action = await vscode.window.showInformationMessage(
			`SpecBox Engine updated to v${engineVersion} (extension is v${this.extensionVersion}). Update extension?`,
			'Update Now',
			'Later'
		);

		if (action !== 'Update Now') { return; }

		await vscode.window.withProgress({
			location: vscode.ProgressLocation.Notification,
			title: 'SpecBox: Updating extension...',
			cancellable: false,
		}, async (progress) => {
			const scriptPath = path.join(enginePath, 'vscode-extension', 'install-ext.mjs');

			if (!fs.existsSync(scriptPath)) {
				vscode.window.showErrorMessage('install-ext.mjs not found in engine repo. Pull the latest version.');
				return;
			}

			progress.report({ message: 'Building and installing...' });
			// Use execFile to avoid shell injection — passes args as array, not interpolated string
			const result = await new Promise<string | null>(resolve => {
				cp.execFile('node', [scriptPath], { cwd: enginePath, timeout: 120_000 }, (err, stdout) => {
					resolve(err ? null : stdout.trim());
				});
			});

			if (result !== null) {
				const reload = await vscode.window.showInformationMessage(
					`SpecBox Extension updated to v${engineVersion}. Reload to activate?`,
					'Reload Now'
				);
				if (reload === 'Reload Now') {
					await vscode.commands.executeCommand('workbench.action.reloadWindow');
				}
			} else {
				vscode.window.showErrorMessage(
					'Extension update failed. Try manually: node vscode-extension/install-ext.mjs'
				);
			}
		});
	}

	private readEngineVersion(enginePath: string): string | null {
		try {
			const content = fs.readFileSync(
				path.join(enginePath, 'ENGINE_VERSION.yaml'), 'utf-8'
			);
			const m = content.match(/^version:\s*(.+)/m);
			return m?.[1]?.trim() ?? null;
		} catch {
			return null;
		}
	}
}
