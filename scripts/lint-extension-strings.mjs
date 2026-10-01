#!/usr/bin/env node
// lint-extension-strings.mjs — fails if user-facing literals appear without vscode.l10n.t(...)
// Used by:
//   .github/workflows/publish-vscode-extension.yml (CI gate before publish)
//   vscode-extension/tests/l10n.test.mjs (npm test — US-57/UC-5702)
// Usage:
//   node scripts/lint-extension-strings.mjs            # default: scan + report
//   node scripts/lint-extension-strings.mjs --verbose  # also show passing files
//
// A literal that is a product name, not copy (the `SpecBox` output channel), is
// marked on its line with `l10n-lint:ignore`.

import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = fileURLToPath(new URL('.', import.meta.url));
const REPO_ROOT = join(__dirname, '..');
const SRC_DIR = join(REPO_ROOT, 'vscode-extension', 'src');

// Files not migrated to vscode.l10n.t yet. Empty since US-57/UC-5702 (install.ts,
// mcp.ts, onboard.ts and updater.ts were migrated; skills-tree.ts uses the inline mark).
const ALLOWLIST_FILES = new Set([]);

const IGNORE_MARK = 'l10n-lint:ignore';

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
    // vscode.window.withProgress({ title: "literal", ... })  — US-57/UC-5702
    {
        pattern: /vscode\.window\.withProgress\s*\(\s*\{[^}]*\btitle\s*:\s*(['"`])/g,
        description: 'withProgress with literal title',
    },
    // progress.report({ message: "literal" })
    {
        pattern: /\bprogress\.report\s*\(\s*\{[^}]*\bmessage\s*:\s*(['"`])/g,
        description: 'progress.report with literal message',
    },
    // vscode.window.showOpenDialog({ openLabel: "literal", title: "literal" })
    {
        pattern: /vscode\.window\.show(Open|Save)Dialog\s*\(\s*\{[^}]*\b(openLabel|saveLabel|title)\s*:\s*(['"`])/g,
        description: 'showOpenDialog/showSaveDialog with literal label or title',
    },
    // vscode.window.createTerminal("literal") / setStatusBarMessage("literal")
    {
        pattern: /vscode\.window\.(createTerminal|setStatusBarMessage)\s*\(\s*(['"`])/g,
        description: 'createTerminal/setStatusBarMessage with literal text',
    },
];

// Every pattern ends right at the opening quote of the literal, so a text wrapped in
// vscode.l10n.t(...) never matches. (Until UC-5702 any l10n.t( in the 200 characters
// before a match excused it, which hid literals next to translated lines.)

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
            // The line where the literal itself starts (the match may span lines).
            const end = idx + m[0].length;
            const eol = content.indexOf('\n', end);
            const line = content.slice(content.lastIndexOf('\n', end - 1) + 1, eol === -1 ? content.length : eol);
            if (line.includes(IGNORE_MARK)) {
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
