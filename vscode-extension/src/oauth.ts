import * as vscode from 'vscode';
import * as http from 'node:http';
import * as crypto from 'node:crypto';
import { AddressInfo } from 'node:net';

const ALLOWED_ORIGINS = new Set([
	'https://cloud.specbox.build',
]);

const CALLBACK_TIMEOUT_MS = 5 * 60 * 1000; // 5 minutes
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

	const timeoutHandle = setTimeout(() => {
		if (!resolved) {
			resolved = true;
			try { server.close(); } catch { /* ignore */ }
			resolvePromise({ ok: false, error: 'timeout' });
		}
	}, CALLBACK_TIMEOUT_MS);

	awaitCallback.then(() => {
		clearTimeout(timeoutHandle);
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
		close: () => {
			clearTimeout(timeoutHandle);
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

function renderSuccessPage(): string {
	const title = vscode.l10n.t('Signed in to SpecBox');
	const message = vscode.l10n.t('You can close this tab and return to VS Code.');
	return `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>${escapeHtml(title)}</title>
<style>body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#1a1a2e;color:#e6e6e6;display:flex;align-items:center;justify-content:center;height:100vh;margin:0}main{max-width:480px;padding:32px;text-align:center}h1{font-size:24px;margin:0 0 12px}p{font-size:16px;opacity:.85}</style>
</head><body><main><h1>${escapeHtml(title)}</h1><p>${escapeHtml(message)}</p></main>
<script>setTimeout(function(){try{window.close();}catch(e){}}, 1500);</script>
</body></html>`;
}

function renderErrorPage(code: string, description?: string): string {
	const title = vscode.l10n.t('Sign-in failed');
	const safeDesc = description ?? code;
	return `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>${escapeHtml(title)}</title>
<style>body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#1a1a2e;color:#e6e6e6;display:flex;align-items:center;justify-content:center;height:100vh;margin:0}main{max-width:480px;padding:32px;text-align:center}h1{font-size:24px;margin:0 0 12px;color:#ff7676}p{font-size:14px;opacity:.85}</style>
</head><body><main><h1>${escapeHtml(title)}</h1><p>${escapeHtml(safeDesc)}</p></main></body></html>`;
}

function escapeHtml(s: string): string {
	return s.replace(/[&<>"']/g, (c) => ({
		'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
	}[c] as string));
}

/**
 * Build the cloud sign-in URL. The cloud endpoint is documented in
 * doc/decisions/native_default_oauth.md; the contract is:
 *   GET https://cloud.specbox.build/vscode/issue-token
 *     ?return_to=<URI-encoded loopback>
 *     &state=<csrf>
 */
export function buildSignInUrl(loopbackPort: number, state: string, baseUrl?: string): string {
	const base = baseUrl ?? 'https://cloud.specbox.build/vscode/issue-token';
	const returnTo = encodeURIComponent(`http://127.0.0.1:${loopbackPort}/callback`);
	return `${base}?return_to=${returnTo}&state=${state}`;
}
