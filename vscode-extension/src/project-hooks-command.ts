/**
 * UC-11201 — "SpecBox: Update project hooks": one command updates the hooks of
 * the open project, also with the remote MCP (no engine clone, no server).
 *
 * Lists what differs before touching anything; hooks changed locally are kept
 * unless the user ticks them (their new version is saved next to them).
 */
import * as vscode from 'vscode';
import type { CliLike } from './device-connection';
import { describeStatus, modifiedHooks, summarizeUpdate, type HooksStatus, type HooksUpdate } from './project-hooks';

const t = vscode.l10n.t;

export async function updateProjectHooks(cli: CliLike): Promise<void> {
	const folder = vscode.workspace.workspaceFolders?.[0];
	if (!folder) {
		void vscode.window.showWarningMessage(t('Open the project folder first.'));
		return;
	}
	const projectRoot = folder.uri.fsPath;
	const status = await cli.call<HooksStatus>('_hooks_status', { project_root: projectRoot }, 30_000);
	if (!status?.ok) {
		void vscode.window.showErrorMessage(t('Could not read the project hooks ({0}).', status?.reason ?? t('Node.js not found')));
		return;
	}
	if (!status.differs) {
		void vscode.window.showInformationMessage(t('The project hooks are up to date (SpecBox {0}).', status.version));
		return;
	}

	const update = t('Update');
	const choice = await vscode.window.showInformationMessage(
		t('Update the project hooks to SpecBox {0}?', status.version),
		{ modal: true, detail: describeStatus(status, t).join('\n') },
		update,
	);
	if (choice !== update) { return; }

	let overwrite: string[] = [];
	const modified = modifiedHooks(status);
	if (modified.length) {
		const picked = await vscode.window.showQuickPick(
			modified.map((path) => ({ label: path, picked: false })),
			{
				canPickMany: true,
				title: t('You changed these hooks: tick the ones to replace with the new version'),
				placeHolder: t('The others stay as they are; their new version is saved next to them as .new'),
			},
		);
		if (picked === undefined) { return; }
		overwrite = picked.map((p) => p.label);
	}

	const result = await cli.call<HooksUpdate>('_hooks_update', { project_root: projectRoot, overwrite }, 30_000);
	if (!result?.ok) {
		void vscode.window.showErrorMessage(t('Could not update the project hooks ({0}).', result?.reason ?? t('Node.js not found')));
		return;
	}
	void vscode.window.showInformationMessage(summarizeUpdate(result, t));
}
