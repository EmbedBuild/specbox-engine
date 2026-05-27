import * as vscode from 'vscode';
import * as https from 'node:https';
import * as http from 'node:http';
import { URL } from 'node:url';

// Cloud has two distinct hostnames:
//   cloud.specbox.build     — frontend SPA (Vite/Astro) and OAuth pages.
//   api-cloud.specbox.build — backend API endpoints (/api/whoami, etc.).
// We default to the API host here. The signInBaseUrl override targets the
// frontend (for E2E tests against the mock cloud); we derive the API host
// from it by adding the "api-" prefix to the hostname when applicable.
const DEFAULT_API_BASE_URL = 'https://api-cloud.specbox.build';
const SIGN_IN_BASE_URL_CONFIG = 'specbox.signInBaseUrl';
const REQUEST_TIMEOUT_MS = 5_000;
const CACHE_TTL_MS = 30_000;

export interface WhoamiResponse {
	handle: string;
	developer_id: string;
	github_user_id?: number;
	avatar_url?: string;
}

interface CacheEntry {
	value: WhoamiResponse;
	expiresAt: number;
}

const cache = new Map<string, CacheEntry>();

export function _resetCacheForTests(): void {
	cache.clear();
}

/**
 * Derive the cloud API base URL. Production lives at
 * api-cloud.specbox.build (separate hostname from the frontend SPA at
 * cloud.specbox.build).
 *
 * For E2E tests, `specbox.signInBaseUrl` points at a mock cloud at
 * http://127.0.0.1:<port>/vscode/issue-token; in that case we use the same
 * host:port for the API (mock servers expose both endpoints).
 */
function getCloudBaseUrl(): string {
	const cfg = vscode.workspace.getConfiguration();
	const raw = cfg.get<string>(SIGN_IN_BASE_URL_CONFIG);
	if (!raw) { return DEFAULT_API_BASE_URL; }
	try {
		const u = new URL(raw);
		return `${u.protocol}//${u.host}`;
	} catch {
		return DEFAULT_API_BASE_URL;
	}
}

/**
 * Resolve a GitHub handle from the cloud given the user's mcp_token.
 *
 * Returns:
 *   - `null` if the cloud endpoint is not reachable or not yet deployed.
 *     Callers should fall back to a mask of the token in that case so the
 *     sidebar still shows something meaningful.
 *   - `null` on network / 5xx errors (transient).
 *   - `null` on 401 — we treat the token as not-resolvable but the caller
 *     keeps the signed-in flag (the token was good enough to reach us, the
 *     cloud just doesn't know it yet).
 *
 * Throws nothing — every failure path returns null with a console warn so the
 * sidebar refresh path can never crash because of cloud unavailability.
 */
export async function fetchWhoami(token: string): Promise<WhoamiResponse | null> {
	const cached = cache.get(token);
	const now = Date.now();
	if (cached && cached.expiresAt > now) {
		return cached.value;
	}

	const base = getCloudBaseUrl();
	const url = `${base}/api/whoami`;

	let body: string;
	let contentType: string;
	let status: number;

	try {
		const res = await httpsGet(url, token);
		status = res.status;
		contentType = res.contentType;
		body = res.body;
	} catch (err) {
		console.warn('[specbox] whoami network error:', err instanceof Error ? err.message : err);
		return null;
	}

	// Endpoint not yet deployed: SPA fallback returns the HTML index.
	// Treat as unavailable, not as auth failure.
	if (!contentType.includes('application/json')) {
		return null;
	}

	if (status === 401) {
		// Token rejected by cloud — don't cache, don't surface as handle.
		return null;
	}

	if (status < 200 || status >= 300) {
		console.warn(`[specbox] whoami status ${status}: ${body.slice(0, 200)}`);
		return null;
	}

	let parsed: WhoamiResponse;
	try {
		parsed = JSON.parse(body) as WhoamiResponse;
	} catch (err) {
		console.warn('[specbox] whoami JSON parse error:', err);
		return null;
	}

	if (!parsed || typeof parsed.handle !== 'string' || !parsed.handle.trim()) {
		console.warn('[specbox] whoami response missing handle field');
		return null;
	}

	cache.set(token, { value: parsed, expiresAt: now + CACHE_TTL_MS });
	return parsed;
}

interface HttpsGetResult {
	status: number;
	contentType: string;
	body: string;
}

function httpsGet(url: string, bearer: string): Promise<HttpsGetResult> {
	return new Promise((resolve, reject) => {
		const opts: https.RequestOptions = {
			method: 'GET',
			headers: {
				'Authorization': `Bearer ${bearer}`,
				'Accept': 'application/json',
				'User-Agent': 'specbox-vscode-extension',
			},
			timeout: REQUEST_TIMEOUT_MS,
		};

		// Switch transport based on URL scheme so plain HTTP localhost works in
		// E2E tests where the mock cloud server doesn't speak TLS.
		const transport = url.startsWith('http://') ? http : https;
		const req = transport.request(url, opts, (res) => {
			const chunks: Buffer[] = [];
			res.on('data', (c) => chunks.push(c));
			res.on('end', () => {
				const body = Buffer.concat(chunks).toString('utf8');
				resolve({
					status: res.statusCode ?? 0,
					contentType: String(res.headers['content-type'] ?? ''),
					body,
				});
			});
			res.on('error', reject);
		});
		req.on('timeout', () => {
			req.destroy(new Error('timeout'));
		});
		req.on('error', reject);
		req.end();
	});
}
