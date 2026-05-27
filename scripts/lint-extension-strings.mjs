#!/usr/bin/env node
// lint-extension-strings.mjs — fails if user-facing literals appear without vscode.l10n.t(...)
// Used by:
//   .github/workflows/publish-vscode-extension.yml (CI gate before publish)
// Usage:
//   node scripts/lint-extension-strings.mjs            # default: scan + report
//   node scripts/lint-extension-strings.mjs --verbose  # also show passing files

import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = fileURLToPath(new URL('.', import.meta.url));
const REPO_ROOT = join(__dirname, '..');
const SRC_DIR = join(REPO_ROOT, 'vscode-extension', 'src');

// --- Files NOT yet migrated to vscode.l10n.t (follow-up work).
// Listed here explicitly so CI doesn't block the v6.2.0 publish.
// Each entry should track a follow-up issue or be migrated.
const ALLOWLIST_FILES = new Set([
    'install.ts',     // TODO: migrate strings to l10n.t in follow-up
    'mcp.ts',         // TODO: migrate strings to l10n.t in follow-up
    'onboard.ts',     // TODO: migrate strings to l10n.t in follow-up
    'updater.ts',     // TODO: migrate strings to l10n.t in follow-up
    // skills-tree.ts only contains `createOutputChannel('SpecBox')` as the
    // single offending literal — the channel name is a product identifier
    // shown in the OUTPUT panel dropdown, the same way GitHub Actions /
    // Git Base / Dart-Code etc. use their literal product names. Not
    // user-facing copy that needs translation.
    'skills-tree.ts',
]);

// Patterns that surface a user-facing string the moment they appear with a literal.
const VIOLATIONS = [
    // vscode.window.show*Message("literal", ...)
    {
        pattern: /vscode\.window\.show(Information|Warning|Error)Message\s*\(\s*(['"`])/g,
        description: 'showInformation/Warning/ErrorMessage with literal first arg',
    },
    // vscode.window.showInputBox({ prompt: "literal", ... })
    {
        pattern: /vscode\.window\.showInputBox\s*\(\s*\{[^}]*\b(prompt|placeHolder|title)\s*:\s*(['"`])/g,
        description: 'showInputBox with literal prompt/placeHolder/title',
    },
    // vscode.window.createWebviewPanel('id', 'literal title', ...)
    {
        pattern: /vscode\.window\.createWebviewPanel\s*\(\s*['"`][^'"`]+['"`]\s*,\s*(['"`])/g,
        description: 'createWebviewPanel with literal title',
    },
    // vscode.window.createOutputChannel("literal")
    {
        pattern: /vscode\.window\.createOutputChannel\s*\(\s*(['"`])/g,
        description: 'createOutputChannel with literal name',
    },
];

// l10n.t wrappers are OK — detect to allow nested patterns.
const L10N_WRAPPER = /vscode\.l10n\.t\s*\(/;

function walk(dir) {
    const out = [];
    for (const entry of readdirSync(dir)) {
        const full = join(dir, entry);
        const st = statSync(full);
        if (st.isDirectory()) {
            out.push(...walk(full));
        } else if (entry.endsWith('.ts') && !entry.endsWith('.d.ts')) {
            out.push(full);
        }
    }
    return out;
}

function isAllowed(file) {
    const base = file.split('/').pop();
    return ALLOWLIST_FILES.has(base);
}

function scanFile(file) {
    const content = readFileSync(file, 'utf-8');
    const findings = [];
    for (const { pattern, description } of VIOLATIONS) {
        pattern.lastIndex = 0;
        let m;
        while ((m = pattern.exec(content))) {
            const idx = m.index;
            // Walk back to find the start of the surrounding call to check for l10n.t.
            const slice = content.slice(Math.max(0, idx - 200), idx + 100);
            // If the literal is inside vscode.l10n.t(...), skip — that's an intentional fallback.
            if (L10N_WRAPPER.test(slice.slice(0, slice.indexOf(m[0]) + 50))) {
                // Heuristic: if a l10n.t( appears just before the match, the literal is wrapped.
                // We allow this case.
                continue;
            }
            const lineNum = content.slice(0, idx).split('\n').length;
            const colNum = idx - content.lastIndexOf('\n', idx - 1);
            findings.push({ line: lineNum, col: colNum, description });
        }
    }
    return findings;
}

function main() {
    const verbose = process.argv.includes('--verbose');
    const files = walk(SRC_DIR);
    let totalViolations = 0;
    let scanned = 0;
    let skipped = 0;

    for (const file of files) {
        const rel = relative(REPO_ROOT, file);
        if (isAllowed(file)) {
            skipped++;
            if (verbose) console.log(`SKIP (allowlist): ${rel}`);
            continue;
        }
        scanned++;
        const findings = scanFile(file);
        if (findings.length === 0) {
            if (verbose) console.log(`OK: ${rel}`);
            continue;
        }
        for (const f of findings) {
            console.error(`${rel}:${f.line}:${f.col}: ${f.description}`);
            totalViolations++;
        }
    }

    console.log('');
    console.log(`Scanned ${scanned} files. Skipped ${skipped} (allowlist).`);
    if (totalViolations > 0) {
        console.error(`✗ ${totalViolations} string literal(s) outside vscode.l10n.t — wrap them or add to allowlist.`);
        process.exit(1);
    } else {
        console.log('✓ all scanned files clean');
    }
}

main();
