#!/usr/bin/env node
// UC-3904 — bundle the `specbox` CLI (packages/specbox-cli) inside the
// extension so it can reuse the very same code `specbox login` runs (secure
// store, headers helper, Claude Code configuration). Runs before every
// compile, so the VSIX always carries the CLI of the same commit. The copy is
// generated (see .gitignore): edit packages/specbox-cli, never specbox-cli/.
import { cpSync, existsSync, rmSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const source = join(here, '..', 'packages', 'specbox-cli');
const target = join(here, 'specbox-cli');

if (!existsSync(join(source, 'bin', 'specbox.mjs'))) {
	console.error(`copy-cli: ${source} not found — the extension needs packages/specbox-cli`);
	process.exit(1);
}
rmSync(target, { recursive: true, force: true });
for (const entry of ['bin', 'lib', 'package.json', 'README.md']) {
	cpSync(join(source, entry), join(target, entry), { recursive: true });
}
console.log(`copy-cli: bundled ${source} → ${target}`);
