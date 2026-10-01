import * as vscode from 'vscode';
import { HealthResult } from './health';
import { howToConnectUrl } from './constants';

/**
 * UC-3904 AC-06 — who this computer is connected as: the person, the device,
 * when its token expires and that it renews itself.
 */
export interface StatusIdentity {
	handle: string;
	deviceName?: string | null;
	expiresAt?: string | null;
	/** Device tokens held by the extension / `specbox login` renew themselves. */
	renews: boolean;
}

function formatDate(iso: string, language: string | undefined): string {
	try {
		return new Date(iso).toLocaleDateString(language || undefined, { day: 'numeric', month: 'long', year: 'numeric' });
	} catch {
		return iso.slice(0, 10);
	}
}

/** Tooltip lines for the connected identity. Pure apart from l10n (stubbed in tests). */
export function identityTooltipLines(identity: StatusIdentity, language?: string): string[] {
	const lines = [vscode.l10n.t('Connected as @{0}', identity.handle)];
	if (identity.deviceName) {
		lines.push(vscode.l10n.t('Device: {0}', identity.deviceName));
	}
	if (identity.expiresAt) {
		const when = formatDate(identity.expiresAt, language);
		lines.push(
			identity.renews
				? vscode.l10n.t('Token expires on {0} — it renews itself', when)
				: vscode.l10n.t('Token expires on {0}', when)
		);
	} else {
		lines.push(vscode.l10n.t('Token without expiry (issued before devices existed)'));
	}
	return lines;
}

export class StatusBarManager {
	readonly item: vscode.StatusBarItem;
	private health: HealthResult | null = null;
	private identity: StatusIdentity | null = null;

	constructor() {
		this.item = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 50);
		this.item.command = 'specbox.showStatus';
		this.item.text = `$(loading~spin) SpecBox · ${vscode.l10n.t('checking')}`;
		this.item.tooltip = vscode.l10n.t('SpecBox Engine — checking…');
		this.item.show();
	}

	update(health: HealthResult): void {
		this.health = health;
		this.render();
	}

	/** UC-3904 AC-06 — null when this computer is not connected with an account. */
	setIdentity(identity: StatusIdentity | null): void {
		this.identity = identity;
		this.render();
	}

	private render(): void {
		const health = this.health;
		const who = this.identity ? ` · @${this.identity.handle}` : '';
		const t = vscode.l10n.t;
		const lines: string[] = [];

		// UC-4903 — la palabra del estado siempre visible; los iconos, los nativos de VSCode (única
		// opción de la barra de estado). Hecho se dice con la marca de terminal del sistema: [x].
		if (!health) {
			this.item.text = `$(loading~spin) SpecBox · ${t('checking')}${who}`;
			lines.push(t('SpecBox Engine — checking…'));
		} else if (!health.engineInstalled) {
			this.item.text = `$(warning) SpecBox · ${t('not installed')}${who}`;
			this.item.command = 'specbox.onboard';
			lines.push(`[ ] ${t('SpecBox Engine — not installed. Click to run setup.')}`);
		} else {
			const issues: string[] = [];
			if (!health.engram.ok) { issues.push(t('Engram missing')); }
			if (!health.mcpSpecbox.configured) { issues.push(t('MCP not configured')); }
			if (!health.mcpEngram.configured) { issues.push(t('Engram MCP not configured')); }
			this.item.command = 'specbox.showStatus';
			if (issues.length > 0) {
				this.item.text = `$(alert) SpecBox v${health.engineVersion} · ${t('{0} pending', String(issues.length))}${who}`;
				lines.push(`SpecBox Engine v${health.engineVersion}`, ...issues.map((i) => `[ ] ${i}`));
			} else {
				this.item.text = `[x] SpecBox v${health.engineVersion} · ${t('ready')}${who}`;
				lines.push(`[x] ${t('SpecBox Engine — all systems operational')}`);
			}
		}

		if (this.identity) {
			lines.push('', ...identityTooltipLines(this.identity, vscode.env.language));
		} else {
			lines.push('', vscode.l10n.t('Not connected with an account'));
		}
		const tooltip = new vscode.MarkdownString(lines.join('  \n'));
		tooltip.appendMarkdown(`  \n\n[${vscode.l10n.t('How SpecBox connects')}](${howToConnectUrl(vscode.env.language)})`);
		this.item.tooltip = tooltip;
	}

	dispose(): void {
		this.item.dispose();
	}
}
