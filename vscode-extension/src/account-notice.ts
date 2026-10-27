import * as vscode from 'vscode';

/**
 * UC-3901: the first day (UTC) the hosted SpecBox MCP rejects a connection without an account.
 * Matches SPECBOX_TRANSPORT_AUTH_GRACE_UNTIL on the server.
 */
export const ACCOUNT_REQUIRED_FROM = '2026-10-30';

const SHOWN_ON_KEY = 'specbox.accountNoticeShownOn';

export interface AccountNotice {
	severity: 'warning' | 'error';
	/** Short line for the Status view. */
	label: string;
	/** What happens and what to do, for the notification and the tooltip. */
	text: string;
}

/**
 * UC-11013: what to tell someone whose SpecBox MCP is configured but who has not connected an
 * account. FreeForm stays free and keeps the board in the repository, but the hosted MCP only
 * accepts connections with a token from ACCOUNT_REQUIRED_FROM. null when there is nothing to say.
 */
export function accountNotice(input: { mcpConfigured: boolean; signedIn: boolean; today?: Date }): AccountNotice | null {
	if (!input.mcpConfigured || input.signedIn) { return null; }
	const today = (input.today ?? new Date()).toISOString().slice(0, 10);
	if (today < ACCOUNT_REQUIRED_FROM) {
		return {
			severity: 'warning',
			label: vscode.l10n.t('Sign in with GitHub: required from 30 October 2026'),
			text: vscode.l10n.t('From 30 October 2026 the SpecBox MCP only accepts connections with an account. Sign in with GitHub: it is free, and with FreeForm the board stays in your repository.'),
		};
	}
	return {
		severity: 'error',
		label: vscode.l10n.t('Sign in with GitHub: required since 30 October 2026'),
		text: vscode.l10n.t('Since 30 October 2026 the SpecBox MCP only accepts connections with an account. Sign in with GitHub to keep using it: it is free, and with FreeForm the board stays in your repository.'),
	};
}

/**
 * Startup reminder, at most once a day: the Status view keeps the notice until the person signs in.
 * Returns true when it was shown.
 */
export async function showAccountNoticeOnce(
	context: vscode.ExtensionContext,
	input: { mcpConfigured: boolean; signedIn: boolean; today?: Date },
): Promise<boolean> {
	const notice = accountNotice(input);
	if (!notice) { return false; }
	const day = (input.today ?? new Date()).toISOString().slice(0, 10);
	if (context.globalState.get<string>(SHOWN_ON_KEY) === day) { return false; }
	await context.globalState.update(SHOWN_ON_KEY, day);
	const signIn = vscode.l10n.t('Sign in with GitHub');
	const show = notice.severity === 'error' ? vscode.window.showErrorMessage : vscode.window.showWarningMessage;
	const pick = await show(notice.text, signIn, vscode.l10n.t('Later'));
	if (pick === signIn) { await vscode.commands.executeCommand('specbox.signIn'); }
	return true;
}
