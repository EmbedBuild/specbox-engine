#!/usr/bin/env node
/**
 * mcp-client-io.test.mjs — UC-621 tests.
 *
 * Run:  node .claude/hooks/lib/mcp-client-io.test.mjs
 *
 * Uses Node's built-in test runner (node:test) — zero external deps.
 * Each test creates an isolated temp git repo so the helpers can resolve
 * a real toplevel without touching the engine repo itself.
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execSync } from 'node:child_process';
import {
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  writeFileSync,
  existsSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import {
  resolveProjectRoot,
  readContentBundle,
  writeContentBundle,
} from './mcp-client-io.mjs';

// ── helpers ──────────────────────────────────────────────────────────

function makeTempRepo() {
  const dir = mkdtempSync(join(tmpdir(), 'mcp-client-io-'));
  execSync('git init -q', { cwd: dir });
  return dir;
}

function withTempRepo(fn) {
  const repo = makeTempRepo();
  try {
    return fn(repo);
  } finally {
    rmSync(repo, { recursive: true, force: true });
  }
}

// ── resolveProjectRoot ───────────────────────────────────────────────

test('resolveProjectRoot returns git toplevel of CWD', () => {
  withTempRepo((repo) => {
    const inner = join(repo, 'a/b/c');
    mkdirSync(inner, { recursive: true });
    const result = resolveProjectRoot({ cwd: inner });
    // On macOS the actual toplevel may be a /private/var/... resolved path
    // of the symlinked /var/... — accept either as long as both point to repo.
    assert.ok(
      result === repo || result.endsWith(repo.replace(/^\/var\//, '/private/var/')),
      `expected toplevel for ${repo}, got ${result}`,
    );
  });
});

test('resolveProjectRoot throws when CWD is not in a git repo', () => {
  const notARepo = mkdtempSync(join(tmpdir(), 'mcp-no-git-'));
  try {
    assert.throws(
      () => resolveProjectRoot({ cwd: notARepo }),
      /not inside a git repository/,
    );
  } finally {
    rmSync(notARepo, { recursive: true, force: true });
  }
});

// ── readContentBundle ────────────────────────────────────────────────

test('readContentBundle reads existing files and reports missing ones as null', () => {
  withTempRepo((repo) => {
    writeFileSync(join(repo, 'a.md'), 'A content');
    mkdirSync(join(repo, 'sub'));
    writeFileSync(join(repo, 'sub/b.md'), 'B content');
    const bundle = readContentBundle(['a.md', 'sub/b.md', 'missing.md'], { root: repo });
    assert.equal(bundle['a.md'], 'A content');
    assert.equal(bundle['sub/b.md'], 'B content');
    assert.equal(bundle['missing.md'], null);
  });
});

test('readContentBundle returns empty bundle for empty array', () => {
  withTempRepo((repo) => {
    const bundle = readContentBundle([], { root: repo });
    assert.deepEqual(bundle, {});
  });
});

test('readContentBundle rejects absolute paths', () => {
  withTempRepo((repo) => {
    assert.throws(
      () => readContentBundle(['/etc/passwd'], { root: repo }),
      /refusing to read absolute path/,
    );
  });
});

test('readContentBundle rejects path traversal escapes', () => {
  withTempRepo((repo) => {
    assert.throws(
      () => readContentBundle(['../../etc/passwd'], { root: repo }),
      /escapes the project root/,
    );
  });
});

test('readContentBundle rejects non-array input', () => {
  assert.throws(
    () => readContentBundle('a.md'),
    /paths must be an array/,
  );
});

test('readContentBundle rejects empty string in array', () => {
  withTempRepo((repo) => {
    assert.throws(
      () => readContentBundle([''], { root: repo }),
      /non-empty string/,
    );
  });
});

// ── writeContentBundle ───────────────────────────────────────────────

test('writeContentBundle writes new files and creates parent dirs', () => {
  withTempRepo((repo) => {
    const { written, skipped } = writeContentBundle(
      {
        'doc/foo.md': 'foo content',
        'doc/nested/bar.md': 'bar content',
      },
      { root: repo },
    );
    assert.deepEqual(written.sort(), ['doc/foo.md', 'doc/nested/bar.md']);
    assert.deepEqual(skipped, []);
    assert.equal(readFileSync(join(repo, 'doc/foo.md'), 'utf-8'), 'foo content');
    assert.equal(readFileSync(join(repo, 'doc/nested/bar.md'), 'utf-8'), 'bar content');
  });
});

test('writeContentBundle skips null/undefined values', () => {
  withTempRepo((repo) => {
    const { written, skipped } = writeContentBundle(
      { 'a.md': 'real', 'b.md': null, 'c.md': undefined },
      { root: repo },
    );
    assert.deepEqual(written, ['a.md']);
    assert.deepEqual(skipped.sort(), ['b.md', 'c.md']);
    assert.ok(!existsSync(join(repo, 'b.md')));
    assert.ok(!existsSync(join(repo, 'c.md')));
  });
});

test('writeContentBundle overwrites existing files', () => {
  withTempRepo((repo) => {
    writeFileSync(join(repo, 'x.md'), 'old');
    writeContentBundle({ 'x.md': 'new' }, { root: repo });
    assert.equal(readFileSync(join(repo, 'x.md'), 'utf-8'), 'new');
  });
});

test('writeContentBundle rejects absolute paths', () => {
  withTempRepo((repo) => {
    assert.throws(
      () => writeContentBundle({ '/tmp/escape.md': 'x' }, { root: repo }),
      /refusing to write absolute path/,
    );
  });
});

test('writeContentBundle rejects path traversal escapes', () => {
  withTempRepo((repo) => {
    assert.throws(
      () => writeContentBundle({ '../escape.md': 'x' }, { root: repo }),
      /escapes the project root/,
    );
  });
});

test('writeContentBundle rejects non-string values', () => {
  withTempRepo((repo) => {
    assert.throws(
      () => writeContentBundle({ 'x.md': 42 }, { root: repo }),
      /must be a string or null/,
    );
  });
});

test('writeContentBundle rejects non-object input', () => {
  assert.throws(
    () => writeContentBundle('not an object'),
    /bundle must be an object/,
  );
});
