/**
 * Tests for version-consistency-check.mjs (v5.32.1).
 *
 * Builds synthetic mini-repos in /tmp with controlled file contents
 * and runs the script as a child process. Asserts exit codes and
 * the per-file diagnoses in stderr.
 */

import assert from 'node:assert/strict';
import { mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = resolve(fileURLToPath(import.meta.url), '../../..');
const scriptPath = join(repoRoot, '.quality/scripts/version-consistency-check.mjs');

function makeMiniRepo(version, overrides = {}) {
  const dir = join('/tmp', `vc-${Date.now()}-${Math.random().toString(36).slice(2)}`);
  mkdirSync(dir, { recursive: true });

  const files = {
    'ENGINE_VERSION.yaml': `version: ${version}\ncodename: "Test"\n`,
    'pyproject.toml': `[project]\nname = "x"\nversion = "${version}"\n`,
    'CLAUDE.md': `# SpecBox Engine v${version}\n\nbody\n\n## Engine Version\n\nCurrent: v${version} "Test"\n`,
    'CHANGELOG.md': `# Changelog\n\n## [${version}] - 2026-05-02 — "Test"\n\n- entry\n`,
    'README.md': `<p>v${version} — "Test"</p>\n\nbody\n\n# SpecBox Engine — English version\n\n> v${version} — "Test"\n`,
    ...overrides,
  };

  for (const [name, content] of Object.entries(files)) {
    writeFileSync(join(dir, name), content, 'utf-8');
  }
  return dir;
}

function runScript(cwd) {
  return spawnSync('node', [scriptPath], { cwd, encoding: 'utf-8' });
}

// ── Tests ─────────────────────────────────────────────────────────────

function testHappyPath() {
  const dir = makeMiniRepo('5.32.1');
  try {
    const r = runScript(dir);
    assert.equal(r.status, 0, `expected exit 0, got ${r.status}; stderr: ${r.stderr}`);
    assert.match(r.stderr, /OK — all 7 checks aligned on v5.32.1/);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

function testReadmeOutOfSync() {
  const dir = makeMiniRepo('5.32.1', {
    // README still on the old version while everything else is bumped.
    'README.md': '<p>v5.32.0 — "Old"</p>\n\n# SpecBox Engine — English version\n\n> v5.32.0 — "Old"\n',
  });
  try {
    const r = runScript(dir);
    assert.equal(r.status, 1);
    assert.match(r.stderr, /MISMATCH \(got 5\.32\.0\)\s+README\.md \(Spanish/);
    assert.match(r.stderr, /MISMATCH \(got 5\.32\.0\)\s+README\.md \(English/);
    assert.match(r.stderr, /2 file\(s\) out of sync/);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

function testChangelogMissingNewEntry() {
  const dir = makeMiniRepo('5.32.1', {
    // CHANGELOG never got the new entry — top entry is still old.
    'CHANGELOG.md': '# Changelog\n\n## [5.32.0] - 2026-05-02 — "Old"\n',
  });
  try {
    const r = runScript(dir);
    assert.equal(r.status, 1);
    assert.match(r.stderr, /MISMATCH \(got 5\.32\.0\)\s+CHANGELOG\.md/);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

function testClaudeMdHeaderForgotten() {
  const dir = makeMiniRepo('5.32.1', {
    'CLAUDE.md': '# SpecBox Engine v5.32.0\n\n## Engine Version\n\nCurrent: v5.32.1 "Test"\n',
  });
  try {
    const r = runScript(dir);
    assert.equal(r.status, 1);
    assert.match(r.stderr, /MISMATCH \(got 5\.32\.0\)\s+CLAUDE\.md \(header\)/);
    // The footer was bumped — that one should pass.
    assert.match(r.stderr, /OK\s+CLAUDE\.md \(Engine Version footer\)/);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

function testPyprojectMisaligned() {
  const dir = makeMiniRepo('5.32.1', {
    'pyproject.toml': '[project]\nname = "x"\nversion = "5.31.0"\n',
  });
  try {
    const r = runScript(dir);
    assert.equal(r.status, 1);
    assert.match(r.stderr, /MISMATCH \(got 5\.31\.0\)\s+pyproject\.toml/);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

function testCanonicalUnreadable() {
  const dir = makeMiniRepo('5.32.1', {
    'ENGINE_VERSION.yaml': '# missing version field\ncodename: "x"\n',
  });
  try {
    const r = runScript(dir);
    assert.equal(r.status, 1);
    assert.match(r.stderr, /FATAL — could not read version from ENGINE_VERSION\.yaml/);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

function testMissingFile() {
  const dir = makeMiniRepo('5.32.1');
  // Remove README to simulate a brand-new repo without the file.
  rmSync(join(dir, 'README.md'));
  try {
    const r = runScript(dir);
    assert.equal(r.status, 1);
    assert.match(r.stderr, /MISSING \(file not found\)\s+README\.md/);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

function testSeveralOutOfSync() {
  // Common reality: pyproject + CLAUDE header bumped, README + CHANGELOG forgotten.
  const dir = makeMiniRepo('5.32.1', {
    'CHANGELOG.md': '# Changelog\n\n## [5.32.0] - ... — "Old"\n',
    'README.md': '<p>v5.32.0 — "Old"</p>\n\n# SpecBox Engine — English version\n\n> v5.32.0 — "Old"\n',
  });
  try {
    const r = runScript(dir);
    assert.equal(r.status, 1);
    assert.match(r.stderr, /3 file\(s\) out of sync/);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

// ── Runner ────────────────────────────────────────────────────────────

const tests = [
  testHappyPath,
  testReadmeOutOfSync,
  testChangelogMissingNewEntry,
  testClaudeMdHeaderForgotten,
  testPyprojectMisaligned,
  testCanonicalUnreadable,
  testMissingFile,
  testSeveralOutOfSync,
];

let failed = 0;
for (const t of tests) {
  try {
    t();
    console.log(`  ok ${t.name}`);
  } catch (err) {
    failed++;
    console.error(`  FAIL ${t.name}: ${err.message}`);
  }
}

if (failed > 0) {
  console.error(`\n${failed} of ${tests.length} tests failed`);
  process.exit(1);
}
console.log(`\n${tests.length} tests passed`);
