import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import {
	CLAUDE_DIR, CLAUDE_SKILLS_DIR, CLAUDE_HOOKS_DIR,
	CLAUDE_SETTINGS, CORE_SKILLS, REQUIRED_NODE_VERSION, REQUIRED_PYTHON_VERSION
} from './constants';
import { exec, commandExists } from './util';

export interface HealthResult {
	engineInstalled: boolean;
	engineVersion: string | null;
	enginePath: string | null;
	node: { ok: boolean; version: string | null };
	python: { ok: boolean; version: string | null };
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

		const [node, python, claudeCode, engram, gga] = await Promise.all([
			this.checkNode(),
			this.checkPython(),
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
			node, python, claudeCode, engram,
			skills, hooks, settings,
			mcpSpecbox, mcpEngram, gga,
		};
	}

	showReport(r: HealthResult): void {
		const lines: string[] = [
			'# SpecBox Engine — Health Check',
			'',
			`| Component | Status |`,
			`|-----------|--------|`,
			`| Engine | ${r.engineInstalled ? `v${r.engineVersion}` : 'Not installed'} |`,
			`| Engine Path | ${r.enginePath ?? 'Not found'} |`,
			`| Node.js | ${r.node.ok ? r.node.version : `Missing (need ${REQUIRED_NODE_VERSION}+)`} |`,
			`| Python | ${r.python.ok ? r.python.version : `Missing (need ${REQUIRED_PYTHON_VERSION}+)`} |`,
			`| Claude Code | ${r.claudeCode.ok ? r.claudeCode.version : 'Missing'} |`,
			`| Engram | ${r.engram.ok ? r.engram.version : 'Not installed'} |`,
			`| GGA | ${r.gga.ok ? r.gga.version : 'Not installed (optional)'} |`,
			`| Skills | ${r.skills.installed.length}/${r.skills.installed.length + r.skills.missing.length} |`,
			`| Hooks | ${r.hooks.ok ? `${r.hooks.count} installed` : 'Missing'} |`,
			`| Settings | ${r.settings.ok ? 'OK' : 'Missing'} |`,
			`| MCP SpecBox | ${r.mcpSpecbox.configured ? 'Configured' : 'Not configured'} |`,
			`| MCP Engram | ${r.mcpEngram.configured ? 'Configured' : 'Not configured'} |`,
		];

		if (r.skills.missing.length > 0) {
			lines.push('', `**Missing skills:** ${r.skills.missing.join(', ')}`);
		}

		const panel = vscode.window.createWebviewPanel(
			'specbox.health', 'SpecBox Health Check', vscode.ViewColumn.One
		);
		panel.webview.html = this.markdownToHtml(lines.join('\n'));
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

	private async checkPython(): Promise<{ ok: boolean; version: string | null }> {
		// Try python3 first, then python
		let v = await exec('python3 --version');
		if (!v) { v = await exec('python --version'); }
		if (!v) { return { ok: false, version: null }; }
		const match = v.match(/(\d+)\.(\d+)/);
		if (!match) { return { ok: false, version: v }; }
		const major = Number(match[1]);
		const minor = Number(match[2]);
		const ok = major >= 3 && minor >= 12;
		return { ok, version: v.replace('Python ', '').trim() };
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
		const installed: string[] = [];
		const missing: string[] = [];
		for (const skill of CORE_SKILLS) {
			const skillPath = path.join(CLAUDE_SKILLS_DIR, skill);
			if (fs.existsSync(path.join(skillPath, 'SKILL.md'))) {
				installed.push(skill);
			} else {
				missing.push(skill);
			}
		}
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

	private markdownToHtml(md: string): string {
		const lines = md.split('\n');
		const htmlParts: string[] = [];
		let i = 0;

		while (i < lines.length) {
			const line = lines[i];

			// Heading
			if (line.startsWith('# ')) {
				htmlParts.push(`<h1>${this.escapeHtml(line.slice(2))}</h1>`);
				i++;
				continue;
			}

			// Table block: collect consecutive lines starting with |
			if (line.startsWith('|')) {
				const tableLines: string[] = [];
				while (i < lines.length && lines[i].startsWith('|')) {
					tableLines.push(lines[i]);
					i++;
				}
				htmlParts.push(this.parseTable(tableLines));
				continue;
			}

			// Empty line → break
			if (line.trim() === '') {
				htmlParts.push('<br/>');
			} else {
				htmlParts.push(`<p>${this.escapeHtml(line)}</p>`);
			}
			i++;
		}

		return `<!DOCTYPE html><html><head><style>
			body { font-family: var(--vscode-font-family); padding: 20px; color: var(--vscode-foreground); }
			table { border-collapse: collapse; width: 100%; margin: 16px 0; }
			th, td { padding: 8px 12px; text-align: left; border: 1px solid var(--vscode-panel-border); }
			th { background: var(--vscode-editor-background); font-weight: bold; }
			h1 { border-bottom: 1px solid var(--vscode-panel-border); padding-bottom: 8px; }
			p { margin: 4px 0; }
		</style></head><body>${htmlParts.join('\n')}</body></html>`;
	}

	private parseTable(lines: string[]): string {
		if (lines.length < 2) { return ''; }

		const splitRow = (row: string): string[] => {
			// Split by | but handle escaped pipes and empty cells
			return row.split('|').slice(1, -1).map(c => c.trim());
		};

		const headers = splitRow(lines[0]);
		// Skip separator line (line[1] is |---|---|)
		const dataStart = lines.length > 1 && /^[|\s-:]+$/.test(lines[1]) ? 2 : 1;

		const headerHtml = headers.map(h => `<th>${this.escapeHtml(h)}</th>`).join('');
		const rowsHtml = lines.slice(dataStart).map(row => {
			const cells = splitRow(row);
			// Pad cells to match header count
			while (cells.length < headers.length) { cells.push(''); }
			return `<tr>${cells.map(c => `<td>${this.escapeHtml(c)}</td>`).join('')}</tr>`;
		}).join('');

		return `<table><thead><tr>${headerHtml}</tr></thead><tbody>${rowsHtml}</tbody></table>`;
	}

	private escapeHtml(text: string): string {
		return text
			.replace(/&/g, '&amp;')
			.replace(/</g, '&lt;')
			.replace(/>/g, '&gt;')
			.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
	}
}
