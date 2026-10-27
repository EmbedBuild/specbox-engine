/**
 * UC-11201 — what "SpecBox: Update project hooks" shows, without vscode (tests).
 *
 * The bundled CLI compares the project's .claude/hooks with the hooks this
 * extension carries (`_hooks_status`) and updates them without overwriting the
 * ones changed locally (`_hooks_update`): those keep their content and the new
 * version is written next to them as `<hook>.mjs.new`.
 */

export type HookStateName = 'current' | 'updatable' | 'modified' | 'missing' | 'retired';

export interface HooksStatus {
	ok: boolean;
	reason?: string;
	version: string;
	installed_version: string | null;
	hooks: Array<{ path: string; state: HookStateName }>;
	settings_missing: Array<{ event: string; matcher: string | null; command: string }>;
	differs: boolean;
}

export interface HooksUpdate {
	ok: boolean;
	reason?: string;
	version: string;
	written: string[];
	kept: Array<{ path: string; new: string }>;
	retired: string[];
	settings_added: number;
	settings_backup: string | null;
}

export type Translate = (message: string, ...args: Array<string | number>) => string;

/** One line per hook that differs from the published one, and the settings to add (AC-01). */
export function describeStatus(status: HooksStatus, t: Translate): string[] {
	const label: Record<HookStateName, string> = {
		current: t('up to date'),
		updatable: t('will be updated'),
		modified: t('changed locally: left as is'),
		missing: t('missing: will be installed'),
		retired: t('no longer published: not deleted'),
	};
	const lines = status.hooks.filter((h) => h.state !== 'current').map((h) => `${h.path} — ${label[h.state]}`);
	if (status.settings_missing.length) {
		lines.push(t('.claude/settings.json: {0} hook registrations will be added', status.settings_missing.length));
	}
	return lines;
}

/** The hooks changed locally: the user picks which ones to replace (AC-02). */
export function modifiedHooks(status: HooksStatus): string[] {
	return status.hooks.filter((h) => h.state === 'modified').map((h) => h.path);
}

export function summarizeUpdate(result: HooksUpdate, t: Translate): string {
	const parts = [t('Project hooks updated to SpecBox {0}: {1} written.', result.version, result.written.length)];
	if (result.kept.length) {
		parts.push(t('Kept your version of {0}; the new one is next to it as .new.', result.kept.map((k) => k.path).join(', ')));
	}
	if (result.settings_added) {
		parts.push(t('{0} hook registrations added to .claude/settings.json.', result.settings_added));
	}
	return parts.join(' ');
}
