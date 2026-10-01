import { brandBlock, escapeHtml, lucideIcon, pageTheme, renderPage } from './design';
import * as vscode from 'vscode';
import * as http from 'node:http';
import * as crypto from 'node:crypto';
import { AddressInfo } from 'node:net';

const ALLOWED_ORIGINS = new Set([
	'https://cloud.specbox.build',
]);

// The user has to read the cloud "Confirm your account" screen, possibly
// switch GitHub accounts, and clear VS Code's "open external website" trust
// dialog — all inside this window. 5 minutes was too tight in practice
// (users hit ERR_CONNECTION_REFUSED because the loopback had already closed).
// The clock is also armed AFTER the browser opens (see armTimeout), not when
// the server is created, so setup time is not counted against the user.
const CALLBACK_TIMEOUT_MS = 10 * 60 * 1000; // 10 minutes
// Token shape is `spbx_<base64url(32 bytes)>` — frozen by the cloud's
// `issueMcpToken()` in apps/api/src/lib/tokens.ts (US-09 of specbox_cloud).
// Base64url charset is [A-Za-z0-9_-]; randomBytes(32) yields a 43-char body
// (no padding). We allow 32–128 chars to be tolerant of future entropy bumps
// without losing the prefix invariant.
const MCP_TOKEN_REGEX = /^spbx_[A-Za-z0-9_-]{32,128}$/;

export type CallbackResult =
	| { ok: true; token: string; state: string }
	| { ok: false; error: string; description?: string; state?: string };

export interface LoopbackServer {
	port: number;
	state: string;
	awaitCallback: Promise<CallbackResult>;
	/**
	 * Arm the inactivity timeout. Call this AFTER the browser has actually
	 * opened, so the window the user gets to complete sign-in is not eaten by
	 * the time spent opening the browser / clearing trust dialogs. Idempotent.
	 */
	armTimeout: () => void;
	close: () => void;
}

/**
 * Start a one-shot HTTP server on 127.0.0.1 that accepts a single GET /callback.
 * Returns the bound port (assigned by the OS) and a promise that resolves with
 * the parsed callback result. Auto-closes after the first callback or after
 * CALLBACK_TIMEOUT_MS, whichever comes first.
 */
export async function startLoopbackServer(): Promise<LoopbackServer> {
	const state = crypto.randomBytes(32).toString('hex');
	let resolved = false;
	let resolvePromise!: (r: CallbackResult) => void;
	const awaitCallback = new Promise<CallbackResult>((res) => {
		resolvePromise = res;
	});

	const server = http.createServer((req, res) => {
		const handle = handleRequest(req, res, state);
		if (handle && !resolved) {
			resolved = true;
			resolvePromise(handle);
		}
	});

	let timeoutHandle: ReturnType<typeof setTimeout> | null = null;

	awaitCallback.then(() => {
		if (timeoutHandle) { clearTimeout(timeoutHandle); }
		// Small delay so the success HTML reaches the browser before closing.
		setTimeout(() => { try { server.close(); } catch { /* ignore */ } }, 250);
	});

	await new Promise<void>((res, rej) => {
		server.once('error', rej);
		server.listen(0, '127.0.0.1', () => res());
	});

	const addr = server.address() as AddressInfo;
	const port = addr.port;

	return {
		port,
		state,
		awaitCallback,
		armTimeout: () => {
			// Idempotent: only the first call arms the clock.
			if (timeoutHandle || resolved) { return; }
			timeoutHandle = setTimeout(() => {
				if (!resolved) {
					resolved = true;
					try { server.close(); } catch { /* ignore */ }
					resolvePromise({ ok: false, error: 'timeout' });
				}
			}, CALLBACK_TIMEOUT_MS);
		},
		close: () => {
			if (timeoutHandle) { clearTimeout(timeoutHandle); }
			try { server.close(); } catch { /* ignore */ }
			if (!resolved) {
				resolved = true;
				resolvePromise({ ok: false, error: 'closed' });
			}
		},
	};
}

function handleRequest(
	req: http.IncomingMessage,
	res: http.ServerResponse,
	expectedState: string
): CallbackResult | null {
	if (req.method !== 'GET') {
		res.statusCode = 400;
		res.end('Method not allowed');
		return null;
	}

	const url = new URL(req.url ?? '/', 'http://127.0.0.1');
	if (url.pathname !== '/callback') {
		res.statusCode = 404;
		res.end('Not found');
		return null;
	}

	const origin = req.headers.origin;
	if (origin && !ALLOWED_ORIGINS.has(origin)) {
		res.statusCode = 400;
		res.end('Origin rejected');
		return null;
	}

	const params = url.searchParams;
	const state = params.get('state') ?? undefined;

	if (state !== expectedState) {
		res.statusCode = 400;
		res.end('State mismatch');
		return { ok: false, error: 'state_mismatch', state };
	}

	const errorCode = params.get('error');
	if (errorCode) {
		const description = params.get('error_description') ?? undefined;
		res.statusCode = 400;
		res.setHeader('Content-Type', 'text/html; charset=utf-8');
		res.end(renderErrorPage(errorCode, description));
		return { ok: false, error: errorCode, description, state };
	}

	const token = params.get('mcp_token');
	if (!token || !MCP_TOKEN_REGEX.test(token)) {
		res.statusCode = 400;
		res.end('Invalid token shape');
		return { ok: false, error: 'invalid_token_shape', state };
	}

	res.statusCode = 200;
	res.setHeader('Content-Type', 'text/html; charset=utf-8');
	res.end(renderSuccessPage());
	return { ok: true, token, state };
}

/** UC-4903 — la página de retorno, con el sistema «Tinta»: tokens, tema de VSCode, símbolo e icono. */
const CALLBACK_CSS = `
.page { min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: var(--space-6); box-sizing: border-box; }
main { width: 100%; max-width: var(--prose-max); padding: var(--space-8); background: var(--paper-100); border: var(--stroke-hair) solid var(--line-100); border-radius: var(--radius-lg); box-shadow: var(--shadow-sm); }
.state { display: flex; align-items: center; gap: var(--space-2); margin: 0 0 var(--space-3); }
.done { color: var(--status-done-text); }
.failed { color: var(--danger-text); }
.detail { margin-top: var(--space-3); color: var(--ink-700); }
h1 { margin-bottom: var(--space-2); }
`;

export function renderSuccessPage(): string {
	const theme = pageTheme();
	const title = vscode.l10n.t('Signed in to SpecBox');
	const message = vscode.l10n.t('You can close this tab and return to VS Code.');
	const state = vscode.l10n.t('Done');
	return renderPage({
		title,
		theme,
		css: CALLBACK_CSS,
		body: `<div class="page"><main>${brandBlock(theme)}
<p class="state done label">${lucideIcon('circle-check', { label: state })}<span>[x] ${escapeHtml(state)}</span></p>
<h1 class="display-lg">${escapeHtml(title)}</h1>
<p class="body-lg">${escapeHtml(message)}</p></main></div>`,
		script: 'setTimeout(function(){try{window.close();}catch(e){}}, 1500);',
	});
}

export function renderErrorPage(code: string, description?: string): string {
	const theme = pageTheme();
	const title = vscode.l10n.t('Sign-in failed');
	const state = vscode.l10n.t('Failed');
	const safeDesc = description ?? code;
	return renderPage({
		title,
		theme,
		css: CALLBACK_CSS,
		body: `<div class="page"><main>${brandBlock(theme)}
<p class="state failed label">${lucideIcon('circle-x', { label: state })}<span>${escapeHtml(state)}</span></p>
<h1 class="display-lg">${escapeHtml(title)}</h1>
<p class="body-lg">${escapeHtml(safeDesc)}</p>
<p class="detail data-md">${escapeHtml(code)}</p></main></div>`,
	});
}

/**
 * Build the cloud sign-in URL. The cloud endpoint is documented in
 * doc/decisions/native_default_oauth.md; the contract is:
 *   GET https://cloud.specbox.build/vscode/issue-token
 *     ?return_to=<URI-encoded loopback>
 *     &state=<csrf>
 *     [&device_id=<sha256>&host=<computer>&client=claude-code]   (UC-3904)
 *
 * With the device data the cloud issues a DEVICE token (automatic name, it
 * replaces the previous token of this computer instead of adding one).
 */
export function buildSignInUrl(
	loopbackPort: number,
	state: string,
	baseUrl?: string,
	device?: { device_id: string; host: string; client: string },
): string {
	const base = baseUrl ?? 'https://cloud.specbox.build/vscode/issue-token';
	const returnTo = encodeURIComponent(`http://127.0.0.1:${loopbackPort}/callback`);
	const url = `${base}?return_to=${returnTo}&state=${state}`;
	if (!device) { return url; }
	return (
		`${url}&device_id=${encodeURIComponent(device.device_id)}` +
		`&host=${encodeURIComponent(device.host)}&client=${encodeURIComponent(device.client)}`
	);
}
