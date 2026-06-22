/**
 * US-26 (UC-2601 / UC-2602) — Funnel closure: the VSCode extension emits the
 * `activation` event so the anonymous web funnel (site → install_intent) can be
 * correlated end-to-end with a real install.
 *
 * Flow:
 *   1. The site CTA opens a deep-link `vscode://EmbedBuild.specbox-engine/activate?anon_id=<uuid>`.
 *      `registerActivationUriHandler` parses it, validates the UUID and stores the
 *      anon_id in `context.globalState` (key `specbox.funnel.anonId`).
 *   2. On every activation, `maybeEmitActivation` posts a single, idempotent
 *      `activation` event to the public Supabase RPC `ingest_site_event`. The
 *      anon_id (if captured) links the install back to the anonymous web session;
 *      if it never arrived, the activation is emitted anonymously-without-origin.
 *
 * Idempotency: a `specbox.funnel.activationEmitted` flag in globalState guarantees
 * the event is emitted at most once per install. The flag is only set after a 2xx
 * response, so a transient network failure simply retries on the next activation
 * (best-effort).
 *
 * Privacy / integrity (UC-2602, AC-28):
 *   - The anon_id is opaque. It is NEVER enriched with user/repo data.
 *   - The payload `meta` carries ONLY ext_version / platform / vscode_version.
 *     No local paths, no git email, no tokens, no workspace info.
 *   - If the user disabled VS Code telemetry (`vscode.env.isTelemetryEnabled`),
 *     nothing is emitted (the flag is set so we never re-check on every startup).
 *
 * The whole emitter is fire-and-forget and wrapped in try/catch — it can never
 * throw out and must never block extension activation.
 */

import * as vscode from 'vscode';
import * as https from 'node:https';
import { SUPABASE_URL, SUPABASE_ANON_KEY } from './constants';

const ANON_ID_KEY = 'specbox.funnel.anonId';
const ACTIVATION_EMITTED_KEY = 'specbox.funnel.activationEmitted';
const RPC_PATH = '/rest/v1/rpc/ingest_site_event';
const REQUEST_TIMEOUT_MS = 5_000;

// RFC 4122 v4 UUID: 8-4-4-4-12 hex with version nibble `4` and variant `8|9|a|b`.
const UUID_V4_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

/** Pure: true when `s` looks like a canonical UUID v4. */
export function isValidAnonId(s: unknown): s is string {
	return typeof s === 'string' && UUID_V4_RE.test(s);
}

export interface ActivationPayload {
	p_anon_id: string | null;
	p_event_type: 'activation';
	p_page: null;
	p_ref_id: null;
	p_lang: null;
	p_meta: {
		ext_version: string;
		platform: string;
		vscode_version: string;
	};
}

export interface ActivationContext {
	anonId?: string | null;
	extVersion: string;
	platform: string;
	vscodeVersion: string;
}

/**
 * Pure: build the RPC body for an `activation` event. The anon_id is included
 * only when it is a valid UUID v4; otherwise null (anonymous-without-origin,
 * AC-26). `meta` is deliberately limited to non-PII technical fields (AC-28).
 */
export function buildActivationPayload(ctx: ActivationContext): ActivationPayload {
	return {
		p_anon_id: isValidAnonId(ctx.anonId) ? ctx.anonId : null,
		p_event_type: 'activation',
		p_page: null,
		p_ref_id: null,
		p_lang: null,
		p_meta: {
			ext_version: ctx.extVersion,
			platform: ctx.platform,
			vscode_version: ctx.vscodeVersion,
		},
	};
}

export interface HttpPostResult {
	status: number;
}

/** Injectable HTTP client so the POST can be unit-tested without node:https. */
export type HttpPostClient = (
	url: string,
	apiKey: string,
	body: string,
) => Promise<HttpPostResult>;

export interface PostActivationResult {
	ok: boolean;
	status?: number;
	error?: string;
}

/**
 * POST the activation payload to the Supabase RPC. Resilient by contract:
 * NEVER throws — any failure (network, timeout, non-2xx, bad client) resolves to
 * `{ ok: false }`. Only a 2xx response yields `{ ok: true }`.
 *
 * `httpClient` defaults to the node:https implementation; tests inject a mock.
 */
export async function postActivation(
	url: string,
	apiKey: string,
	payload: ActivationPayload,
	httpClient: HttpPostClient = httpsPost,
): Promise<PostActivationResult> {
	let body: string;
	try {
		body = JSON.stringify(payload);
	} catch (err) {
		return { ok: false, error: err instanceof Error ? err.message : String(err) };
	}

	try {
		const res = await httpClient(url, apiKey, body);
		const ok = res.status >= 200 && res.status < 300;
		return ok ? { ok: true, status: res.status } : { ok: false, status: res.status };
	} catch (err) {
		return { ok: false, error: err instanceof Error ? err.message : String(err) };
	}
}

/**
 * node:https POST to the Supabase RPC. Built-in only (zero runtime deps),
 * mirrors the httpsGet pattern in cloud-api.ts (5s timeout, destroy on timeout).
 */
function httpsPost(url: string, apiKey: string, body: string): Promise<HttpPostResult> {
	return new Promise((resolve, reject) => {
		const opts: https.RequestOptions = {
			method: 'POST',
			headers: {
				'apikey': apiKey,
				'Authorization': `Bearer ${apiKey}`,
				'Content-Type': 'application/json',
				'Content-Length': Buffer.byteLength(body),
				'User-Agent': 'specbox-vscode-extension',
			},
			timeout: REQUEST_TIMEOUT_MS,
		};
		const req = https.request(url, opts, (res) => {
			// Drain the response so the socket can be freed.
			res.on('data', () => { /* ignore body */ });
			res.on('end', () => resolve({ status: res.statusCode ?? 0 }));
			res.on('error', reject);
		});
		req.on('timeout', () => { req.destroy(new Error('timeout')); });
		req.on('error', reject);
		req.write(body);
		req.end();
	});
}

/**
 * Register the URI handler for `vscode://EmbedBuild.specbox-engine/activate`.
 * Parses `?anon_id=<uuid>`, validates it, and persists it to globalState so the
 * next `maybeEmitActivation` can correlate the install with the web funnel.
 *
 * No `package.json` `contributes` entry is required: a published extension's
 * `registerUriHandler` is wired to `vscode://<publisher>.<name>/...` by VS Code
 * automatically.
 */
export function registerActivationUriHandler(context: vscode.ExtensionContext): void {
	const handler: vscode.UriHandler = {
		handleUri(uri: vscode.Uri): void {
			try {
				if (uri.path !== '/activate') { return; }
				const params = new URLSearchParams(uri.query);
				const anonId = params.get('anon_id');
				if (isValidAnonId(anonId)) {
					void context.globalState.update(ANON_ID_KEY, anonId);
				} else {
					console.warn('[specbox] activation deep-link with missing/invalid anon_id — ignored');
				}
			} catch (err) {
				console.warn('[specbox] activation URI handler failed:', err);
			}
		},
	};
	context.subscriptions.push(vscode.window.registerUriHandler(handler));
}

/**
 * Emit the `activation` event at most once per install (UC-2601). Fire-and-forget,
 * fully guarded — must never throw or block activation.
 */
export async function maybeEmitActivation(context: vscode.ExtensionContext): Promise<void> {
	try {
		// 1. Idempotency — already emitted (or telemetry opt-out recorded).
		if (context.globalState.get<boolean>(ACTIVATION_EMITTED_KEY) === true) { return; }

		// 2. Privacy — respect the user's VS Code telemetry preference.
		if (vscode.env.isTelemetryEnabled === false) {
			await context.globalState.update(ACTIVATION_EMITTED_KEY, true);
			return;
		}

		// 3. anon_id (or null → anonymous-without-origin, AC-26).
		const anonId = context.globalState.get<string>(ANON_ID_KEY) ?? null;

		// 4. POST.
		const payload = buildActivationPayload({
			anonId,
			extVersion: String(context.extension.packageJSON.version ?? 'unknown'),
			platform: process.platform,
			vscodeVersion: vscode.version,
		});
		const url = `${SUPABASE_URL}${RPC_PATH}`;
		const result = await postActivation(url, SUPABASE_ANON_KEY, payload);

		// 5. Mark emitted only on success; otherwise retry next activation.
		if (result.ok) {
			await context.globalState.update(ACTIVATION_EMITTED_KEY, true);
		} else {
			console.warn(
				'[specbox] activation emit failed (will retry next activation):',
				result.status ?? result.error,
			);
		}
	} catch (err) {
		console.warn('[specbox] maybeEmitActivation unexpected failure:', err);
	}
}
