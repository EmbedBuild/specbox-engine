// US-89 (UC-8903) — when the extension asks /api/whoami who the user is.
//
// It used to ask every 60 seconds per window, night and day: with a handful of
// windows open that was most of the requests the SpecBox database received.
// Now it asks:
//   - right away on activation, sign-in, sign-out and token renewal;
//   - when the window regains focus, if at least 5 minutes went by;
//   - in the background, 30 minutes after the last time it asked (for any reason).
// So a revoked or expired token shows in the status bar at most 30 minutes
// later, or as soon as the window regains focus, and a window left alone asks
// at most 16 times in 8 hours.
//
// Pure (no `vscode`): the clock is injectable so tests can move time.

export const IDENTITY_BACKGROUND_EVERY_MS = 30 * 60_000;
export const IDENTITY_FOCUS_MIN_GAP_MS = 5 * 60_000;

export interface IdentityClock {
	now(): number;
	setTimeout(fn: () => void, ms: number): unknown;
	clearTimeout(handle: unknown): void;
}

const realClock: IdentityClock = {
	now: () => Date.now(),
	setTimeout: (fn, ms) => setTimeout(fn, ms),
	clearTimeout: (handle) => clearTimeout(handle as NodeJS.Timeout),
};

export class IdentityRefresher {
	private last: number | undefined;
	private timer: unknown;
	private disposed = false;

	constructor(
		private readonly refresh: () => Promise<void>,
		private readonly clock: IdentityClock = realClock,
	) {}

	/** Activation, sign-in, sign-out, renewal: ask now. */
	refreshNow(): Promise<void> {
		if (this.disposed) { return Promise.resolve(); }
		this.last = this.clock.now();
		this.schedule();
		return this.refresh();
	}

	/** The window regained focus: ask only if the last time was 5 minutes ago or more. */
	onFocus(): void {
		if (this.last !== undefined && this.clock.now() - this.last < IDENTITY_FOCUS_MIN_GAP_MS) { return; }
		this.refreshNow().catch(() => { /* the status bar keeps its last state */ });
	}

	dispose(): void {
		this.disposed = true;
		if (this.timer !== undefined) { this.clock.clearTimeout(this.timer); this.timer = undefined; }
	}

	private schedule(): void {
		if (this.timer !== undefined) { this.clock.clearTimeout(this.timer); }
		this.timer = this.clock.setTimeout(() => {
			this.timer = undefined;
			this.refreshNow().catch(() => { /* the status bar keeps its last state */ });
		}, IDENTITY_BACKGROUND_EVERY_MS);
	}
}
