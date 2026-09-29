/**
 * UC-3901 AC-03 / UC-3904 — bridge to the `specbox` package bundled with the
 * extension (`specbox-cli/`, copied from packages/specbox-cli at compile time).
 *
 * The extension does not reimplement the secure store, the headers helper or
 * the Claude Code configuration: it runs the very same code `specbox login`
 * uses, through the CLI's internal JSON commands, with the system Node (a
 * prerequisite of the extension since v6.7.0). So signing in from VS Code or
 * from a terminal leaves one computer in exactly the same state, and both
 * replace each other's token (same device id).
 *
 * The token only travels through the child process' stdin; the internal
 * commands never print it except `_adopt` / `_renew`, which hand the current
 * token back so the extension can keep its SecretStorage copy in sync.
 */
import * as cp from 'node:child_process';
import * as path from 'node:path';
import { exec } from './util';
import type { WhoamiResponse } from './cloud-api';

export const DEFAULT_CLOUD_API = 'https://api-cloud.specbox.build/api';
export const CLIENT = 'claude-code';

export interface DeviceInfo {
	device_id: string;
	host: string;
	client: string;
}

export interface CredentialMeta {
	token_sha?: string;
	token_id?: string | null;
	device_id?: string | null;
	device_name?: string | null;
	client?: string | null;
	expires_at?: string | null;
	renew_after?: string | null;
	developer?: { developer_id: string; display_name: string; handle: string | null } | null;
}

export interface ClaudeConfigResult {
	ok: boolean;
	reason?: string;
	manual?: string;
	updated?: Array<{ scope: string; name: string; cwd: string | null }>;
	failed?: Array<{ scope: string; name: string; cwd: string | null }>;
}

export interface StatusResult extends CredentialMeta {
	connected: boolean;
	store: string;
	claude_helper: boolean;
}

export interface ConnectResult extends CredentialMeta {
	ok: boolean;
	reason?: string;
	store?: string;
	claude?: ClaudeConfigResult;
}

export interface AdoptResult extends ConnectResult {
	token?: string;
}

export interface RenewResult extends CredentialMeta {
	connected: boolean;
	renewed?: boolean;
	token?: string;
}

// --- Pure helpers (tested with node:test) ---

/** API base the CLI talks to (`--cloud`). The E2E override points at a mock cloud. */
export function cloudApiBase(signInBaseUrl?: string): string {
	if (!signInBaseUrl) { return DEFAULT_CLOUD_API; }
	try {
		const url = new URL(signInBaseUrl);
		return `${url.protocol}//${url.host}/api`;
	} catch {
		return DEFAULT_CLOUD_API;
	}
}

/** The CLI prints one JSON line; anything else (warnings) is ignored. */
export function parseCliJson<T>(stdout: string): T | null {
	const line = stdout.trim().split(/\r?\n/).filter(Boolean).pop();
	if (!line) { return null; }
	try {
		return JSON.parse(line) as T;
	} catch {
		return null;
	}
}

/**
 * The credential the CLI stores, built from the token the loopback received
 * and the device data `/api/whoami` reports for it (UC-3904 AC-06).
 */
export function credentialFromWhoami(
	token: string,
	me: WhoamiResponse,
	device: DeviceInfo | null,
	cloudApi: string,
): Record<string, unknown> {
	return {
		token,
		token_id: me.device?.token_id ?? null,
		expires_at: me.device?.expires_at ?? null,
		renew_after: me.device?.renew_after ?? null,
		device_id: device?.device_id ?? null,
		device_name: me.device?.device_name ?? null,
		client: me.device?.client ?? CLIENT,
		developer: { developer_id: me.developer_id, display_name: me.handle, handle: me.handle },
		cloud_api: cloudApi,
	};
}

// --- Process bridge ---

/** Absolute path of the system `node`, or null when it is not installed. */
export async function findNode(): Promise<string | null> {
	const out = await exec(process.platform === 'win32' ? 'where node' : 'command -v node');
	const first = out?.split(/\r?\n/).map((s) => s.trim()).find(Boolean);
	return first || null;
}

export interface SpecboxCliOptions {
	cloudApi: string;
	mcpUrl: string;
	/** Injected in tests. */
	nodeFinder?: () => Promise<string | null>;
	env?: NodeJS.ProcessEnv;
}

export class SpecboxCli {
	private nodePath: Promise<string | null> | undefined;

	constructor(private readonly extensionPath: string, private readonly options: SpecboxCliOptions) {}

	get cloudApi(): string {
		return this.options.cloudApi;
	}

	entry(): string {
		return path.join(this.extensionPath, 'specbox-cli', 'bin', 'specbox.mjs');
	}

	node(): Promise<string | null> {
		if (!this.nodePath) { this.nodePath = (this.options.nodeFinder ?? findNode)(); }
		return this.nodePath;
	}

	/**
	 * Run an internal command. Resolves to the parsed JSON answer, or null when
	 * Node is missing, the process fails to start or the answer is not JSON.
	 * Never rejects: callers treat null as "could not do it right now".
	 */
	async call<T>(command: string, input?: unknown, timeoutMs = 60_000): Promise<T | null> {
		const node = await this.node();
		if (!node) { return null; }
		return new Promise((resolve) => {
			let settled = false;
			const done = (value: T | null) => {
				if (!settled) {
					settled = true;
					resolve(value);
				}
			};
			let child: cp.ChildProcessWithoutNullStreams;
			try {
				child = cp.spawn(
					node,
					[this.entry(), command, '--server', this.options.mcpUrl, '--cloud', this.options.cloudApi],
					{ env: this.options.env ?? process.env, windowsHide: true },
				);
			} catch {
				done(null);
				return;
			}
			let stdout = '';
			child.stdout.on('data', (chunk) => { stdout += chunk; });
			child.stderr.on('data', () => { /* the CLI never writes secrets to stderr; ignored */ });
			const timer = setTimeout(() => {
				child.kill();
				done(null);
			}, timeoutMs);
			child.on('error', () => {
				clearTimeout(timer);
				done(null);
			});
			child.on('close', () => {
				clearTimeout(timer);
				done(parseCliJson<T>(stdout));
			});
			child.stdin.on('error', () => { /* process ended before reading */ });
			child.stdin.end(input === undefined ? '' : JSON.stringify(input));
		});
	}
}
