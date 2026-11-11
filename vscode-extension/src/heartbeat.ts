/**
 * US-118 (UC-11802) — the daily anonymous heartbeat.
 *
 * The activation (UC-11801) says that an install exists; the heartbeat says that
 * it is still used. Once per natural UTC day each install sends one `heartbeat`
 * event, with the same anonymous id as its activation, to the public RPC
 * `ingest_site_event`. The database keeps at most one per install and day
 * (UC-11803), so a repeated send is harmless. With those events the SuperAdmin
 * page «Adopción» counts the active installs at 7 and 30 days, how many keep
 * using SpecBox, which version they run and whether they use FreeForm or Cloud.
 *
 * What is sent (AC-02): extension version, OS platform, VS Code version and the
 * tracking backend of the open workspace (freeform, native, trello, plane or
 * none). Never paths, project or repository names, emails or tokens.
 *
 * Privacy (AC-03): with VS Code telemetry disabled nothing is sent.
 *
 * Resilience (AC-04): fire-and-forget. A failure is logged to the console only,
 * the day is not marked, and the next start — or the next periodic check while
 * VS Code stays open — tries again.
 */

import * as vscode from 'vscode';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { SUPABASE_URL, SUPABASE_ANON_KEY } from './constants';
import { FunnelState, HttpPostClient, RPC_PATH, getInstallId, postActivation } from './activation';

const HEARTBEAT_DAY_KEY = 'specbox.funnel.heartbeatDay';
/** While VS Code stays open, how often to check whether today's heartbeat is still due. */
export const HEARTBEAT_CHECK_INTERVAL_MS = 6 * 60 * 60 * 1000;

export type TrackingBackend = 'freeform' | 'native' | 'trello' | 'plane' | 'none';

const BACKENDS: readonly TrackingBackend[] = ['freeform', 'native', 'trello', 'plane'];

/** Pure: a backend name as the heartbeat reports it; anything else is "none". */
export function normalizeBackend(raw: unknown): TrackingBackend {
	const value = typeof raw === 'string' ? raw.trim().toLowerCase() : '';
	return (BACKENDS as readonly string[]).includes(value) ? (value as TrackingBackend) : 'none';
}

type ReadFile = (file: string) => string;

function readJson(file: string, readFile: ReadFile): Record<string, unknown> | undefined {
	try {
		const parsed = JSON.parse(readFile(file));
		return parsed && typeof parsed === 'object' ? (parsed as Record<string, unknown>) : undefined;
	} catch {
		return undefined;
	}
}

/**
 * The tracking backend of a workspace folder, the way the engine detects it
 * (detect_project_backend): `specbox.backend_type` in `.claude/settings.local.json`
 * or `.claude/settings.json`; else a FreeForm board on disk (`doc/tracking/items.json`);
 * else a legacy Trello or Plane config; else "none" (no SpecBox project open).
 * Only the backend name leaves this function — never a path or a project name.
 */
export function readWorkspaceBackend(
	folder: string | undefined,
	readFile: ReadFile = (file) => fs.readFileSync(file, 'utf8'),
	exists: (file: string) => boolean = (file) => fs.existsSync(file),
): TrackingBackend {
	if (!folder) { return 'none'; }
	const settings = [
		readJson(path.join(folder, '.claude', 'settings.local.json'), readFile),
		readJson(path.join(folder, '.claude', 'settings.json'), readFile),
	];
	for (const s of settings) {
		const specbox = s?.specbox as Record<string, unknown> | undefined;
		const backend = normalizeBackend(specbox?.backend_type);
		if (backend !== 'none') { return backend; }
	}
	if (exists(path.join(folder, 'doc', 'tracking', 'items.json'))) { return 'freeform'; }
	for (const s of settings) {
		const trello = s?.trello as Record<string, unknown> | undefined;
		if (typeof trello?.boardId === 'string' && trello.boardId) { return 'trello'; }
		const plane = s?.plane as Record<string, unknown> | undefined;
		if (typeof plane?.projectId === 'string' && plane.projectId) { return 'plane'; }
	}
	return 'none';
}

/** Pure: the natural UTC day of a date, `YYYY-MM-DD`. */
export function utcDay(now: Date): string {
	return now.toISOString().slice(0, 10);
}

export interface HeartbeatPayload {
	p_anon_id: string;
	p_event_type: 'heartbeat';
	p_page: null;
	p_ref_id: null;
	p_lang: null;
	p_meta: {
		ext_version: string;
		platform: string;
		vscode_version: string;
		backend: TrackingBackend;
	};
}

/** Pure: the RPC body of a heartbeat (AC-02: only these four fields in `meta`). */
export function buildHeartbeatPayload(ctx: {
	installId: string;
	extVersion: string;
	platform: string;
	vscodeVersion: string;
	backend: TrackingBackend;
}): HeartbeatPayload {
	return {
		p_anon_id: ctx.installId,
		p_event_type: 'heartbeat',
		p_page: null,
		p_ref_id: null,
		p_lang: null,
		p_meta: {
			ext_version: ctx.extVersion,
			platform: ctx.platform,
			vscode_version: ctx.vscodeVersion,
			backend: ctx.backend,
		},
	};
}

export interface EmitHeartbeatDeps {
	state: FunnelState;
	telemetryEnabled: () => boolean;
	backend: () => TrackingBackend;
	extVersion: string;
	platform: string;
	vscodeVersion: string;
	now?: () => Date;
	httpClient?: HttpPostClient;
	log?: (msg: string, detail?: unknown) => void;
}

export type HeartbeatOutcome = 'sent' | 'already_today' | 'opted_out' | 'no_install' | 'busy' | 'failed';

let heartbeatInFlight = false;

/** Send today's heartbeat if it is due. Never throws. */
export async function emitHeartbeat(deps: EmitHeartbeatDeps): Promise<HeartbeatOutcome> {
	const log = deps.log ?? ((msg: string, detail?: unknown) => console.warn(msg, detail ?? ''));
	try {
		if (!deps.telemetryEnabled()) { return 'opted_out'; }
		// The heartbeat reuses the activation's id: until the activation chose one there is nothing to send.
		const installId = getInstallId(deps.state);
		if (!installId) { return 'no_install'; }
		const day = utcDay((deps.now ?? (() => new Date()))());
		if (deps.state.get<string>(HEARTBEAT_DAY_KEY) === day) { return 'already_today'; }
		if (heartbeatInFlight) { return 'busy'; }
		heartbeatInFlight = true;
		try {
			const payload = buildHeartbeatPayload({
				installId,
				extVersion: deps.extVersion,
				platform: deps.platform,
				vscodeVersion: deps.vscodeVersion,
				backend: deps.backend(),
			});
			const result = await postActivation(`${SUPABASE_URL}${RPC_PATH}`, SUPABASE_ANON_KEY, payload, deps.httpClient);
			if (result.ok) {
				await deps.state.update(HEARTBEAT_DAY_KEY, day);
				return 'sent';
			}
			log('[specbox] heartbeat failed (will retry on the next start or check):', result.status ?? result.error);
			return 'failed';
		} finally {
			heartbeatInFlight = false;
		}
	} catch (err) {
		log('[specbox] heartbeat unexpected failure:', err);
		return 'failed';
	}
}

/** Test hook: reset the in-memory guard between tests. */
export function _resetHeartbeatGuardForTests(): void {
	heartbeatInFlight = false;
}

/**
 * Send today's heartbeat now (if due) and keep checking every few hours while VS
 * Code stays open, so a window that is never closed still reports each day.
 * Fire-and-forget: never awaited by the activation.
 */
export function startHeartbeat(context: vscode.ExtensionContext): void {
	const deps = (): EmitHeartbeatDeps => ({
		state: context.globalState,
		telemetryEnabled: () => vscode.env.isTelemetryEnabled !== false,
		backend: () => readWorkspaceBackend(vscode.workspace.workspaceFolders?.[0]?.uri.fsPath),
		extVersion: String(context.extension.packageJSON.version ?? 'unknown'),
		platform: process.platform,
		vscodeVersion: vscode.version,
	});
	void emitHeartbeat(deps());
	const timer = setInterval(() => { void emitHeartbeat(deps()); }, HEARTBEAT_CHECK_INTERVAL_MS);
	context.subscriptions.push({ dispose: () => clearInterval(timer) });
}
