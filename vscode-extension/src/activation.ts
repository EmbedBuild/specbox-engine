/**
 * US-26 (UC-2601 / UC-2602) + US-118 (UC-11801) — the VSCode extension emits the
 * `activation` event once per install, so SpecBox knows how many installs there
 * are and the anonymous web funnel (site → install_intent) can be correlated with
 * a real install.
 *
 * Identity of an install (UC-11801):
 *   - If the install came through the site, the CTA opened the deep link
 *     `vscode://EmbedBuild.specbox-engine/activate?anon_id=<uuid>`;
 *     `registerActivationUriHandler` validates the UUID and stores it in
 *     `context.globalState` (`specbox.funnel.anonId`). That visit id becomes the
 *     install id and the event carries `meta.origin = "site"`.
 *   - Otherwise (installed straight from the Marketplace) the extension generates
 *     a random UUID v4 and the event carries `meta.origin = "marketplace"`.
 *   The chosen id and origin are stored (`specbox.funnel.installId`,
 *   `specbox.funnel.origin`) and never change: the daily heartbeat (UC-11802) uses
 *   the same id. Before UC-11801 the extension sent `p_anon_id: null` when the
 *   deep link never arrived and the database rejected it, so no activation was
 *   ever stored.
 *
 * Timing: the first emission waits a few seconds so a deep link that is still
 * being delivered can land first; the URI handler also triggers the emission
 * itself. An in-memory guard keeps the two from racing.
 *
 * Idempotency: `specbox.funnel.activationEmitted` is set only after a 2xx, so a
 * network failure or a non-2xx simply retries on the next start, silently. The
 * database keeps at most one activation per install id (UC-11803), so a retry
 * that already reached it is harmless.
 *
 * Privacy / integrity (UC-2602, AC-28):
 *   - The install id is random and opaque. It is NEVER enriched with user/repo data.
 *   - `meta` carries ONLY ext_version / platform / vscode_version / origin.
 *     No local paths, no git email, no tokens, no workspace info.
 *   - If the user disabled VS Code telemetry (`vscode.env.isTelemetryEnabled`),
 *     nothing is emitted (the flag is set so we never re-check on every startup).
 *
 * The whole emitter is fire-and-forget and wrapped in try/catch — it can never
 * throw out and must never block extension activation.
 */

import * as vscode from 'vscode';
import * as https from 'node:https';
import { randomUUID } from 'node:crypto';
import { SUPABASE_URL, SUPABASE_ANON_KEY } from './constants';

const ANON_ID_KEY = 'specbox.funnel.anonId';
const INSTALL_ID_KEY = 'specbox.funnel.installId';
const ORIGIN_KEY = 'specbox.funnel.origin';
const ACTIVATION_EMITTED_KEY = 'specbox.funnel.activationEmitted';
export const RPC_PATH = '/rest/v1/rpc/ingest_site_event';
const REQUEST_TIMEOUT_MS = 5_000;
/** How long the first emission waits for a deep link that is still being delivered. */
export const DEEP_LINK_GRACE_MS = 5_000;

// RFC 4122 v4 UUID: 8-4-4-4-12 hex with version nibble `4` and variant `8|9|a|b`.
const UUID_V4_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

/** Pure: true when `s` looks like a canonical UUID v4. */
export function isValidAnonId(s: unknown): s is string {
	return typeof s === 'string' && UUID_V4_RE.test(s);
}

/** Where the install came from: the site's deep link, or straight from the Marketplace. */
export type ActivationOrigin = 'site' | 'marketplace';

export interface InstallIdentity {
	installId: string;
	origin: ActivationOrigin;
	/** True when the identity was just chosen and still has to be stored. */
	isNew: boolean;
}

/**
 * Pure (UC-11801): the identity of this install.
 *   1. an identity already stored wins (it never changes once chosen);
 *   2. else the site visit id from the deep link, with origin "site";
 *   3. else a freshly generated UUID v4, with origin "marketplace".
 */
export function resolveInstallIdentity(
	stored: { installId?: unknown; origin?: unknown; siteAnonId?: unknown },
	generate: () => string,
): InstallIdentity {
	if (isValidAnonId(stored.installId)) {
		return { installId: stored.installId, origin: stored.origin === 'site' ? 'site' : 'marketplace', isNew: false };
	}
	if (isValidAnonId(stored.siteAnonId)) {
		return { installId: stored.siteAnonId, origin: 'site', isNew: true };
	}
	return { installId: generate(), origin: 'marketplace', isNew: true };
}

export interface ActivationPayload {
	p_anon_id: string;
	p_event_type: 'activation';
	p_page: null;
	p_ref_id: null;
	p_lang: null;
	p_meta: {
		ext_version: string;
		platform: string;
		vscode_version: string;
		origin: ActivationOrigin;
	};
}

export interface ActivationContext {
	installId: string;
	origin: ActivationOrigin;
	extVersion: string;
	platform: string;
	vscodeVersion: string;
}

/**
 * Pure: build the RPC body for an `activation` event. `meta` is deliberately
 * limited to non-PII technical fields plus the origin (AC-28, UC-11801 AC-03).
 */
export function buildActivationPayload(ctx: ActivationContext): ActivationPayload {
	return {
		p_anon_id: ctx.installId,
		p_event_type: 'activation',
		p_page: null,
		p_ref_id: null,
		p_lang: null,
		p_meta: {
			ext_version: ctx.extVersion,
			platform: ctx.platform,
			vscode_version: ctx.vscodeVersion,
			origin: ctx.origin,
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
 * POST an event payload to the Supabase RPC. Resilient by contract:
 * NEVER throws — any failure (network, timeout, non-2xx, bad client) resolves to
 * `{ ok: false }`. Only a 2xx response yields `{ ok: true }`.
 *
 * `httpClient` defaults to the node:https implementation; tests inject a mock.
 */
export async function postActivation(
	url: string,
	apiKey: string,
	payload: unknown,
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

/** Minimal globalState surface the emitter needs (lets the tests use a plain Map). */
export interface FunnelState {
	get<T>(key: string): T | undefined;
	update(key: string, value: unknown): Thenable<void> | Promise<void>;
}

export interface EmitActivationDeps {
	state: FunnelState;
	telemetryEnabled: () => boolean;
	extVersion: string;
	platform: string;
	vscodeVersion: string;
	httpClient?: HttpPostClient;
	generateId?: () => string;
	delay?: (ms: number) => Promise<void>;
	/** Wait for a deep link before the first emission (0 when the deep link itself triggers it). */
	graceMs?: number;
	log?: (msg: string, detail?: unknown) => void;
}

let emissionInFlight = false;

/**
 * Emit the `activation` event at most once per install (UC-2601, UC-11801).
 * Never throws; a failure leaves the activation pending for the next start.
 */
export async function emitActivation(deps: EmitActivationDeps): Promise<'emitted' | 'already' | 'opted_out' | 'busy' | 'failed'> {
	const { state } = deps;
	const log = deps.log ?? ((msg: string, detail?: unknown) => console.warn(msg, detail ?? ''));
	if (state.get<boolean>(ACTIVATION_EMITTED_KEY) === true) { return 'already'; }
	if (emissionInFlight) { return 'busy'; }
	emissionInFlight = true;
	try {
		// Privacy — respect the user's VS Code telemetry preference (AC-04).
		if (!deps.telemetryEnabled()) {
			await state.update(ACTIVATION_EMITTED_KEY, true);
			return 'opted_out';
		}

		// First time ever: give a deep link that is still arriving a chance to land.
		const graceMs = deps.graceMs ?? DEEP_LINK_GRACE_MS;
		if (graceMs > 0 && !isValidAnonId(state.get<string>(INSTALL_ID_KEY))) {
			await (deps.delay ?? ((ms: number) => new Promise<void>((r) => setTimeout(r, ms))))(graceMs);
		}

		const identity = resolveInstallIdentity(
			{ installId: state.get(INSTALL_ID_KEY), origin: state.get(ORIGIN_KEY), siteAnonId: state.get(ANON_ID_KEY) },
			deps.generateId ?? randomUUID,
		);
		if (identity.isNew) {
			// Stored before the POST, so a retry after a failure keeps the same id (AC-05).
			await state.update(INSTALL_ID_KEY, identity.installId);
			await state.update(ORIGIN_KEY, identity.origin);
		}

		const payload = buildActivationPayload({
			installId: identity.installId,
			origin: identity.origin,
			extVersion: deps.extVersion,
			platform: deps.platform,
			vscodeVersion: deps.vscodeVersion,
		});
		const result = await postActivation(`${SUPABASE_URL}${RPC_PATH}`, SUPABASE_ANON_KEY, payload, deps.httpClient);

		// Mark emitted only on success; otherwise retry on the next start, silently (AC-05).
		if (result.ok) {
			await state.update(ACTIVATION_EMITTED_KEY, true);
			return 'emitted';
		}
		log('[specbox] activation emit failed (will retry next start):', result.status ?? result.error);
		return 'failed';
	} catch (err) {
		log('[specbox] activation emit unexpected failure:', err);
		return 'failed';
	} finally {
		emissionInFlight = false;
	}
}

/** Read-only: the install id once the activation chose it (used by the daily heartbeat, UC-11802). */
export function getInstallId(state: FunnelState): string | undefined {
	const id = state.get<string>(INSTALL_ID_KEY);
	return isValidAnonId(id) ? id : undefined;
}

/** Test hook: reset the in-memory guard between tests. */
export function _resetEmissionGuardForTests(): void {
	emissionInFlight = false;
}

function depsFromContext(context: vscode.ExtensionContext, graceMs?: number): EmitActivationDeps {
	return {
		state: context.globalState,
		telemetryEnabled: () => vscode.env.isTelemetryEnabled !== false,
		extVersion: String(context.extension.packageJSON.version ?? 'unknown'),
		platform: process.platform,
		vscodeVersion: vscode.version,
		graceMs,
	};
}

/**
 * Register the URI handler for `vscode://EmbedBuild.specbox-engine/activate`.
 * Parses `?anon_id=<uuid>`, validates it, persists it to globalState and, if the
 * activation has not been sent yet, sends it now with origin "site".
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
					void Promise.resolve(context.globalState.update(ANON_ID_KEY, anonId)).then(() =>
						emitActivation(depsFromContext(context, 0)));
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
 * Emit the `activation` event at most once per install (UC-2601, UC-11801).
 * Fire-and-forget, fully guarded — must never throw or block activation.
 */
export async function maybeEmitActivation(context: vscode.ExtensionContext): Promise<void> {
	try {
		await emitActivation(depsFromContext(context));
	} catch (err) {
		console.warn('[specbox] maybeEmitActivation unexpected failure:', err);
	}
}
