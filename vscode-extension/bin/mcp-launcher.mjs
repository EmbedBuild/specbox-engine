#!/usr/bin/env node
// SpecBox MCP launcher — UC-646.
//
// Wraps the underlying MCP server command so the SpecBox native token is
// resolved from the spawn-time environment rather than persisted in the
// Claude Code settings.json on disk. The Claude Code extension is responsible
// for setting SPECBOX_NATIVE_MCP_TOKEN in the env of the spawned process
// using vscode SecretStorage at spawn time (see vscode-extension/src/mcp.ts).
//
// Invocation: node mcp-launcher.mjs '<json-encoded inner>' [...passthrough]
// where inner = { command: string, args?: string[] }.

import { spawn } from 'node:child_process';

const rawInner = process.argv[2] ?? '{}';
let inner;
try {
	inner = JSON.parse(rawInner);
} catch {
	process.stderr.write(`[mcp-launcher] invalid inner JSON: ${rawInner}\n`);
	process.exit(2);
}

if (!inner.command) {
	process.stderr.write('[mcp-launcher] missing inner.command\n');
	process.exit(2);
}

const env = { ...process.env };
// The launcher trusts the parent (Claude Code) to inject the token in env.
// If the token is absent, the MCP server itself returns UNAUTHENTICATED on
// every native tool call (UC-648) — no need to short-circuit here.

const child = spawn(inner.command, inner.args ?? [], {
	stdio: 'inherit',
	env,
});

child.on('exit', (code, signal) => {
	if (signal) {
		process.kill(process.pid, signal);
	} else {
		process.exit(code ?? 0);
	}
});

const forward = (sig) => () => { try { child.kill(sig); } catch { /* ignore */ } };
process.on('SIGINT', forward('SIGINT'));
process.on('SIGTERM', forward('SIGTERM'));
