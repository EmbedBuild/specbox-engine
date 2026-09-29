/**
 * UC-3901 AC-03 / UC-3904 AC-03 — keep this computer connected without manual
 * steps. Runs at startup (and the renewal part once a day):
 *
 *   - After updating the extension, a token kept in SecretStorage but issued
 *     before devices existed becomes a device token (`_adopt`): it goes to the
 *     system secure store, the headers helper is installed and Claude Code is
 *     configured to send it. A project that was already configured keeps
 *     working, now identified.
 *   - When `specbox login` (terminal) connected this computer, the extension
 *     picks that token up too: one computer, one device, one token.
 *   - The token renews itself from 14 days before it expires (`_renew`), and
 *     the SecretStorage copy follows it.
 *   - If Claude Code lost the helper configuration, it is restored.
 *
 * No vscode import: the CLI and the token store are injected (tests).
 */
import type { AdoptResult, ClaudeConfigResult, CredentialMeta, RenewResult, StatusResult } from './specbox-cli';

export type ConnectionState = 'connected' | 'adopted' | 'signed_out' | 'no_node' | 'adopt_failed';

export interface CliLike {
	call<T>(command: string, input?: unknown, timeoutMs?: number): Promise<T | null>;
}

export interface TokenStore {
	getToken(): Promise<string | undefined>;
	storeToken(token: string): Promise<void>;
}

export interface ConnectionReport {
	state: ConnectionState;
	meta?: CredentialMeta;
	reason?: string;
}

export async function ensureDeviceConnection(
	cli: CliLike,
	secrets: TokenStore,
	cleanupLegacy: () => void = () => {},
): Promise<ConnectionReport> {
	const status = await cli.call<StatusResult>('_status', undefined, 20_000);
	if (!status) { return { state: 'no_node' }; }
	const token = await secrets.getToken();

	if (status.connected) {
		const renewed = await cli.call<RenewResult>('_renew', undefined, 20_000);
		if (renewed?.token && renewed.token !== token) {
			await secrets.storeToken(renewed.token);
		}
		if (status.claude_helper) {
			cleanupLegacy();
		} else {
			const configured = await cli.call<{ ok: boolean; claude?: ClaudeConfigResult }>('_configure');
			if (configured?.claude?.ok) { cleanupLegacy(); }
		}
		return { state: 'connected', meta: renewed ?? status };
	}

	if (!token) { return { state: 'signed_out' }; }

	const adopted = await cli.call<AdoptResult>('_adopt', { token, issued_via: 'vscode' });
	if (adopted?.ok && adopted.token) {
		await secrets.storeToken(adopted.token);
		if (adopted.claude?.ok) { cleanupLegacy(); }
		return { state: 'adopted', meta: adopted };
	}
	return { state: 'adopt_failed', reason: adopted?.reason ?? 'unknown' };
}

/** Daily: renew if due and keep the SecretStorage copy in sync. True if the token changed. */
export async function syncRenewal(cli: CliLike, secrets: TokenStore): Promise<boolean> {
	const renewed = await cli.call<RenewResult>('_renew', undefined, 20_000);
	if (!renewed?.connected || !renewed.token) { return false; }
	if (renewed.token === (await secrets.getToken())) { return false; }
	await secrets.storeToken(renewed.token);
	return true;
}
