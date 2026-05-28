import * as vscode from 'vscode';
import { HealthResult } from './health';

// US-VSCODE-PREREQ-GATE — prerequisites gate.
//
// Splits cleanly into a pure core (evaluatePrerequisites / buildPrereqWarning,
// no vscode import needed at call time) and a thin vscode UI layer
// (showPrereqGate). The pure core is what tests import from out/prerequisites.js.

/** The subset of HealthResult the gate cares about. */
export interface PrereqInput {
	node: { ok: boolean };
	claudeCode: { ok: boolean };
	engram: { ok: boolean };
	mcpSpecbox: { configured: boolean };
	mcpEngram: { configured: boolean };
}

export interface PrereqVerdict {
	verdict: 'ready' | 'degraded';
	missing: string[];
}

/**
 * Classify the environment. A prerequisite is critical when its absence can make
 * SpecBox fail: Claude Code (the host), Engram (mandatory memory), Node.js (runs
 * hooks/scripts), and the two MCP servers being configured. GGA is optional and
 * never counts toward `degraded`.
 */
export function evaluatePrerequisites(input: PrereqInput): PrereqVerdict {
	const missing: string[] = [];
	if (!input.claudeCode.ok) { missing.push('Claude Code'); }
	if (!input.engram.ok) { missing.push('Engram'); }
	if (!input.node.ok) { missing.push('Node.js'); }
	if (!input.mcpSpecbox.configured) { missing.push('MCP SpecBox server'); }
	if (!input.mcpEngram.configured) { missing.push('MCP Engram server'); }
	return { verdict: missing.length > 0 ? 'degraded' : 'ready', missing };
}

/** Human-readable, action-oriented warning text for a degraded environment. */
export function buildPrereqWarning(missing: string[]): string {
	return (
		`SpecBox may not work correctly — missing prerequisites: ${missing.join(', ')}. ` +
		`Install the missing pieces or run the setup wizard to fix this.`
	);
}

// --- vscode UI layer ---

const GUIDE_URL = 'https://github.com/EmbedBuild/specbox-engine/tree/main/vscode-extension#readme';

/**
 * Show the prerequisites gate. Non-blocking by design.
 * - When `degraded`: a warning with actionable buttons.
 * - When `ready`: silent on startup; an info message when invoked on demand.
 */
export async function showPrereqGate(health: HealthResult, opts: { onStartup: boolean }): Promise<void> {
	const { verdict, missing } = evaluatePrerequisites(health);

	if (verdict === 'ready') {
		if (!opts.onStartup) {
			vscode.window.showInformationMessage(
				vscode.l10n.t('All prerequisites are installed. SpecBox is ready.')
			);
		}
		return;
	}

	const runWizard = vscode.l10n.t('Run Setup Wizard');
	const configureMcp = vscode.l10n.t('Configure MCP');
	const openGuide = vscode.l10n.t('Open Guide');

	const choice = await vscode.window.showWarningMessage(
		buildPrereqWarning(missing),
		runWizard,
		configureMcp,
		openGuide
	);

	if (choice === runWizard) {
		await vscode.commands.executeCommand('specbox.onboard');
	} else if (choice === configureMcp) {
		await vscode.commands.executeCommand('specbox.configureMcp');
	} else if (choice === openGuide) {
		await vscode.env.openExternal(vscode.Uri.parse(GUIDE_URL));
	}
}
