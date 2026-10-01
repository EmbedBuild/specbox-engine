import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import {
	CLAUDE_DIR, CLAUDE_SKILLS_DIR, CLAUDE_HOOKS_DIR,
	CLAUDE_SETTINGS, CLAUDE_JSON, KNOWN_SKILLS, REQUIRED_NODE_VERSION
} from './constants';
import { exec, commandExists } from './util';
import { brandBlock, escapeHtml, lucideIcon, pageTheme, renderPage, type PageTheme } from './design';

export interface HealthResult {
	engineInstalled: boolean;
	engineVersion: string | null;
	enginePath: string | null;
	node: { ok: boolean; version: string | null };
	claudeCode: { ok: boolean; version: string | null };
	engram: { ok: boolean; version: string | null };
	skills: { installed: string[]; missing: string[] };
	hooks: { ok: boolean; count: number };
	settings: { ok: boolean };
	mcpSpecbox: { configured: boolean };
	mcpEngram: { configured: boolean };
	gga: { ok: boolean; version: string | null };
}

export class HealthChecker {

	async run(): Promise<HealthResult> {
		const enginePath = await this.findEnginePath();
		const engineVersion = enginePath ? this.readEngineVersion(enginePath) : null;

		const [node, claudeCode, engram, gga] = await Promise.all([
			this.checkNode(),
			this.checkClaudeCode(),
			this.checkEngram(),
			this.checkGga(),
		]);

		const skills = this.checkSkills();
		const hooks = this.checkHooks();
		const settings = this.checkSettings();
		const mcpSpecbox = this.checkMcpConfigured('specbox-engine');
		const mcpEngram = this.checkMcpConfigured('engram');

		return {
			engineInstalled: !!enginePath && skills.missing.length === 0,
			engineVersion,
			enginePath,
			node, claudeCode, engram,
			skills, hooks, settings,
			mcpSpecbox, mcpEngram, gga,
		};
	}

	/** UC-4903 — el diagnóstico como página del sistema «Tinta», con el tema de VSCode. */
	showReport(r: HealthResult): void {
		const panel = vscode.window.createWebviewPanel(
			'specbox.health', vscode.l10n.t('SpecBox Health Check'), vscode.ViewColumn.One
		);
		const render = () => { panel.webview.html = renderHealthReport(r); };
		render();
		// Sigue al tema de VSCode mientras el panel esté abierto.
		const sub = vscode.window.onDidChangeActiveColorTheme?.(render);
		panel.onDidDispose(() => sub?.dispose());
	}

	// --- Private checks ---

	private async findEnginePath(): Promise<string | null> {
		// 1. User config
		const configured = vscode.workspace.getConfiguration('specbox').get<string>('enginePath');
		if (configured && fs.existsSync(path.join(configured, 'ENGINE_VERSION.yaml'))) {
			return configured;
		}
		// 2. Workspace root (if inside the engine repo)
		for (const folder of vscode.workspace.workspaceFolders ?? []) {
			const candidate = folder.uri.fsPath;
			if (fs.existsSync(path.join(candidate, 'ENGINE_VERSION.yaml'))) {
				return candidate;
			}
		}
		// 3. Common locations
		const home = os.homedir();
		for (const rel of ['specbox-engine', 'Desktop/specbox-engine', 'dev/specbox-engine', 'projects/specbox-engine']) {
			const p = path.join(home, rel);
			if (fs.existsSync(path.join(p, 'ENGINE_VERSION.yaml'))) {
				return p;
			}
		}
		return null;
	}

	private readEngineVersion(enginePath: string): string | null {
		try {
			const content = fs.readFileSync(path.join(enginePath, 'ENGINE_VERSION.yaml'), 'utf-8');
			const m = content.match(/^version:\s*(.+)/m);
			return m?.[1]?.trim() ?? null;
		} catch { return null; }
	}

	private async checkNode(): Promise<{ ok: boolean; version: string | null }> {
		const v = await exec('node --version');
		if (!v) { return { ok: false, version: null }; }
		const match = v.match(/(\d+)/);
		const major = match ? Number(match[1]) : 0;
		return { ok: major >= REQUIRED_NODE_VERSION, version: v };
	}

	private async checkClaudeCode(): Promise<{ ok: boolean; version: string | null }> {
		const v = await exec('claude --version');
		return { ok: v !== null, version: v };
	}

	private async checkEngram(): Promise<{ ok: boolean; version: string | null }> {
		const v = await exec('engram --version');
		return { ok: v !== null, version: v };
	}

	private async checkGga(): Promise<{ ok: boolean; version: string | null }> {
		const v = await exec('gga --version');
		return { ok: v !== null, version: v };
	}

	private checkSkills(): { installed: string[]; missing: string[] } {
		// Detect actually installed skills from disk. ./install.ts uses
		// symlinkOrCopy(), so many entries under ~/.claude/skills/ are
		// symlinks to the engine repo — Dirent.isDirectory() returns false
		// for symlinks even when their target is a directory. We accept both
		// real directories and symlinks whose final target has a SKILL.md.
		const onDisk = new Set<string>();
		if (fs.existsSync(CLAUDE_SKILLS_DIR)) {
			try {
				for (const entry of fs.readdirSync(CLAUDE_SKILLS_DIR, { withFileTypes: true })) {
					if (!entry.isDirectory() && !entry.isSymbolicLink()) { continue; }
					const skillMdPath = path.join(CLAUDE_SKILLS_DIR, entry.name, 'SKILL.md');
					if (fs.existsSync(skillMdPath)) {
						onDisk.add(entry.name);
					}
				}
			} catch { /* swallow — report empty */ }
		}

		// "missing" is the canonical engine list minus what's on disk;
		// "installed" is everything actually present, including skills from
		// other sources (so the count in the sidebar reflects reality).
		const installed = [...onDisk].sort();
		const missing = KNOWN_SKILLS.filter(s => !onDisk.has(s));
		return { installed, missing };
	}

	private checkHooks(): { ok: boolean; count: number } {
		if (!fs.existsSync(CLAUDE_HOOKS_DIR)) { return { ok: false, count: 0 }; }
		const files = fs.readdirSync(CLAUDE_HOOKS_DIR).filter(f => f.endsWith('.mjs'));
		return { ok: files.length >= 10, count: files.length };
	}

	private checkSettings(): { ok: boolean } {
		return { ok: fs.existsSync(CLAUDE_SETTINGS) };
	}

	private checkMcpConfigured(serverName: string): { configured: boolean } {
		// Aliases: the server may be registered under different names
		const aliases: Record<string, string[]> = {
			'specbox-engine': ['specbox-engine', 'SpecBox-MCP', 'specbox-mcp', 'specbox'],
			'engram': ['engram', 'plugin:engram:engram'],
		};
		const names = aliases[serverName] ?? [serverName];

		// 0. UC-3904 — where Claude Code really keeps MCP servers: ~/.claude.json
		//    (user scope, and local scope per project).
		try {
			const data = JSON.parse(fs.readFileSync(CLAUDE_JSON, 'utf-8'));
			const scopes = [data?.mcpServers, ...Object.values(data?.projects ?? {}).map((p) => (p as { mcpServers?: unknown })?.mcpServers)];
			for (const servers of scopes) {
				if (servers && typeof servers === 'object' && names.some((name) => (servers as Record<string, unknown>)[name])) {
					return { configured: true };
				}
			}
		} catch { /* no ~/.claude.json */ }

		// 1. Check MCP server configs in JSON files
		for (const file of [
			path.join(CLAUDE_DIR, 'settings.local.json'),
			CLAUDE_SETTINGS,
		]) {
			try {
				const data = JSON.parse(fs.readFileSync(file, 'utf-8'));
				// Check mcpServers key
				if (data?.mcpServers) {
					for (const name of names) {
						if (data.mcpServers[name]) { return { configured: true }; }
					}
				}
				// Check permissions for mcp__<name>__* pattern (Claude Code stores allowed MCP tools here)
				const allow = data?.permissions?.allow as string[] | undefined;
				if (allow) {
					for (const name of names) {
						if (allow.some((p: string) => p.startsWith(`mcp__${name}__`))) {
							return { configured: true };
						}
					}
				}
				// Check enabledPlugins (Engram plugin format)
				if (data?.enabledPlugins) {
					for (const name of names) {
						for (const key of Object.keys(data.enabledPlugins)) {
							if (key.includes(name) && data.enabledPlugins[key]) {
								return { configured: true };
							}
						}
					}
				}
			} catch { /* ignore */ }
		}
		// 2. Check workspace .vscode/mcp.json
		for (const folder of vscode.workspace.workspaceFolders ?? []) {
			try {
				const mcpFile = path.join(folder.uri.fsPath, '.vscode', 'mcp.json');
				const data = JSON.parse(fs.readFileSync(mcpFile, 'utf-8'));
				for (const name of names) {
					if (data?.servers?.[name]) { return { configured: true }; }
				}
			} catch { /* ignore */ }
		}
		return { configured: false };
	}
}

/** Estado de una fila del diagnóstico: hecho, pendiente u opcional sin instalar. */
export type HealthRowState = 'done' | 'pending' | 'optional';

export interface HealthRow {
	component: string;
	state: HealthRowState;
	detail: string;
}

/** Filas del diagnóstico. Pura salvo l10n (stub en las pruebas). */
export function healthRows(r: HealthResult): HealthRow[] {
	const t = vscode.l10n.t;
	const row = (component: string, ok: boolean, detailOk: string, detailMissing: string, optional = false): HealthRow => ({
		component,
		state: ok ? 'done' : optional ? 'optional' : 'pending',
		detail: ok ? detailOk : detailMissing,
	});
	return [
		row(t('Engine'), r.engineInstalled, `v${r.engineVersion}`, t('Not installed')),
		row(t('Engine Path'), !!r.enginePath, r.enginePath ?? '', t('Not found')),
		row('Node.js', r.node.ok, r.node.version ?? '', t('Missing (need {0}+)', REQUIRED_NODE_VERSION)),
		row('Claude Code', r.claudeCode.ok, r.claudeCode.version ?? '', t('Missing')),
		row('Engram', r.engram.ok, r.engram.version ?? '', t('Not installed')),
		row('GGA', r.gga.ok, r.gga.version ?? '', t('Not installed (optional)'), true),
		row('Skills', r.skills.missing.length === 0,
			`${r.skills.installed.length}/${r.skills.installed.length + r.skills.missing.length}`,
			`${r.skills.installed.length}/${r.skills.installed.length + r.skills.missing.length}`),
		row('Hooks', r.hooks.ok, `${r.hooks.count} ${t('installed')}`, t('Missing')),
		row(t('Settings'), r.settings.ok, t('OK'), t('Missing')),
		row('MCP SpecBox', r.mcpSpecbox.configured, t('Configured'), t('Not configured')),
		row('MCP Engram', r.mcpEngram.configured, t('Configured'), t('Not configured')),
	];
}

/**
 * La palabra del estado, siempre visible, con la marca de terminal del sistema: `[x]` hecho,
 * `[ ]` pendiente. El color solo acompaña a la palabra.
 */
export function stateLabel(state: HealthRowState): string {
	const t = vscode.l10n.t;
	if (state === 'done') { return `[x] ${t('Ready')}`; }
	if (state === 'optional') { return `[ ] ${t('Optional')}`; }
	return `[ ] ${t('Pending')}`;
}

const HEALTH_CSS = `
main { max-width: 960px; padding: var(--space-6); }
.summary { display: flex; align-items: center; gap: var(--space-2); margin: var(--space-2) 0 var(--space-6); }
.summary.done { color: var(--status-done-text); }
.summary.pending { color: var(--attention-text); }
table { width: 100%; border-collapse: collapse; background: var(--paper-100); border: var(--stroke-hair) solid var(--line-100); border-radius: var(--radius-lg); }
th, td { height: var(--density-row); padding: 0 var(--space-3); text-align: left; border-top: var(--stroke-hair) solid var(--line-100); }
th { border-top: none; border-bottom: var(--stroke-hair) solid var(--line-200); color: var(--ink-700); }
.state { white-space: nowrap; font-family: var(--font-mono); }
.state.done { color: var(--status-done-text); }
.state.pending { color: var(--attention-text); }
.state.optional { color: var(--ink-700); }
.detail { color: var(--ink-700); overflow-wrap: anywhere; }
.missing { margin-top: var(--space-4); color: var(--ink-700); }
`;

/** La página del diagnóstico con los tokens del sistema y el tema de VSCode (oscuro por defecto). */
export function renderHealthReport(r: HealthResult, theme: PageTheme = pageTheme()): string {
	const t = vscode.l10n.t;
	const rows = healthRows(r);
	const pending = rows.filter((x) => x.state === 'pending').length;
	const summary = pending === 0
		? `<p class="summary done label">${lucideIcon('circle-check', { label: t('Ready') })}<span>[x] ${escapeHtml(t('All systems operational'))}</span></p>`
		: `<p class="summary pending label">${lucideIcon('circle-alert', { label: t('Pending') })}<span>${escapeHtml(t('{0} pending', String(pending)))}</span></p>`;
	const body = rows.map((x) => `<tr><td class="body-md">${escapeHtml(x.component)}</td>`
		+ `<td class="state ${x.state} data-md">${escapeHtml(stateLabel(x.state))}</td>`
		+ `<td class="detail data-md">${escapeHtml(x.detail)}</td></tr>`).join('');
	const missing = r.skills.missing.length > 0
		? `<p class="missing body-md">${escapeHtml(t('Missing skills:'))} <span class="data-md">${escapeHtml(r.skills.missing.join(', '))}</span></p>`
		: '';
	return renderPage({
		title: t('SpecBox Health Check'),
		theme,
		css: HEALTH_CSS,
		body: `<main>${brandBlock(theme)}<h1 class="display-lg">${escapeHtml(t('SpecBox Engine — Health Check'))}</h1>${summary}
<table><thead><tr><th class="label">${escapeHtml(t('Component'))}</th><th class="label">${escapeHtml(t('Status'))}</th><th class="label">${escapeHtml(t('Detail'))}</th></tr></thead>
<tbody>${body}</tbody></table>${missing}</main>`,
	});
}
