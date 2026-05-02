#!/usr/bin/env node
/**
 * version-consistency-check.mjs (v5.32.1)
 *
 * Reads the canonical version from ENGINE_VERSION.yaml and verifies it
 * appears in all the files that /release is expected to bump:
 *
 *   1. pyproject.toml          (field: version = "X.Y.Z")
 *   2. CLAUDE.md header        (# SpecBox Engine vX.Y.Z)
 *   3. CLAUDE.md Engine Version footer (Current: vX.Y.Z)
 *   4. CHANGELOG.md            (## [X.Y.Z] - ... at the very top)
 *   5. README.md ES subtitle   (v X.Y.Z — "...")
 *   6. README.md EN subtitle   (v X.Y.Z — "...")
 *
 * Exit codes:
 *   0  — all checks passed
 *   1  — at least one file out of sync; per-file diagnosis on stderr
 *
 * Zero deps. No node_modules. Safe to run from any project that uses
 * this same release protocol.
 */

import { existsSync, readFileSync } from 'node:fs';

const ROOT = process.cwd();

const targets = [
  {
    path: 'ENGINE_VERSION.yaml',
    label: 'ENGINE_VERSION.yaml (canonical)',
    required: true,
    extract: (content) => {
      const m = content.match(/^version:\s*['"]?([^'"\n]+)['"]?/m);
      return m ? m[1].trim() : null;
    },
  },
  {
    path: 'pyproject.toml',
    label: 'pyproject.toml',
    required: true,
    extract: (content) => {
      const m = content.match(/^version\s*=\s*"([^"]+)"/m);
      return m ? m[1].trim() : null;
    },
  },
  {
    path: 'CLAUDE.md',
    label: 'CLAUDE.md (header)',
    required: true,
    extract: (content) => {
      // First H1 line: "# SpecBox Engine vX.Y.Z"
      const m = content.match(/^#\s+SpecBox Engine\s+v?([0-9]+\.[0-9]+\.[0-9]+)/m);
      return m ? m[1].trim() : null;
    },
  },
  {
    path: 'CLAUDE.md',
    label: 'CLAUDE.md (Engine Version footer)',
    required: true,
    extract: (content) => {
      // "Current: vX.Y.Z ..." line
      const m = content.match(/^Current:\s*v?([0-9]+\.[0-9]+\.[0-9]+)/m);
      return m ? m[1].trim() : null;
    },
  },
  {
    path: 'CHANGELOG.md',
    label: 'CHANGELOG.md (top entry)',
    required: true,
    extract: (content) => {
      // First "## [X.Y.Z] - ..." after the header.
      const m = content.match(/^##\s+\[([0-9]+\.[0-9]+\.[0-9]+)\]\s+-/m);
      return m ? m[1].trim() : null;
    },
  },
  {
    path: 'README.md',
    label: 'README.md (Spanish subtitle)',
    required: true,
    extract: (content) => {
      // "v5.32.1 — ..." appears in the first 30 lines (intro block).
      const head = content.split('\n').slice(0, 30).join('\n');
      const m = head.match(/v\s*([0-9]+\.[0-9]+\.[0-9]+)\s*—/);
      return m ? m[1].trim() : null;
    },
  },
  {
    path: 'README.md',
    label: 'README.md (English subtitle)',
    required: true,
    extract: (content) => {
      // Find the H1 of the English block ("# SpecBox Engine — English version"),
      // not the in-text "English version below" link near the top.
      const m = content.match(/^#\s+SpecBox Engine\s*[—-]\s*English version/m);
      if (!m) return null;
      const tail = content.slice(m.index, m.index + 1500);
      const v = tail.match(/v\s*([0-9]+\.[0-9]+\.[0-9]+)\s*[—-]/);
      return v ? v[1].trim() : null;
    },
  },
];

// ── Run ───────────────────────────────────────────────────────────────

const results = [];
let canonical = null;

for (const target of targets) {
  const fullPath = `${ROOT}/${target.path}`;
  if (!existsSync(fullPath)) {
    results.push({ ...target, found: null, error: 'file not found' });
    continue;
  }
  const content = readFileSync(fullPath, 'utf-8');
  const found = target.extract(content);
  results.push({ ...target, found, error: found ? null : 'pattern not matched' });
  if (target.label.includes('canonical') && found) {
    canonical = found;
  }
}

if (!canonical) {
  console.error('[version-consistency-check] FATAL — could not read version from ENGINE_VERSION.yaml');
  process.exit(1);
}

let mismatches = 0;
for (const r of results) {
  const status =
    r.error
      ? `MISSING (${r.error})`
      : r.found === canonical
        ? 'OK'
        : `MISMATCH (got ${r.found})`;
  if (status !== 'OK') mismatches++;
  // Log everything to stderr for the SKILL or CI to capture; keep stdout
  // clean for machine consumers.
  console.error(`  ${status.padEnd(28)} ${r.label}`);
}

if (mismatches > 0) {
  console.error(`\n[version-consistency-check] FAIL — ${mismatches} file(s) out of sync with canonical v${canonical}`);
  process.exit(1);
}
console.error(`\n[version-consistency-check] OK — all ${results.length} checks aligned on v${canonical}`);
process.exit(0);
