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
  readTrackingBundle,
  writeTrackingBundle,
  TRACKING_ITEMS_PATH,
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

// ── FreeForm tracking helpers (UC-661) ───────────────────────────────

test('readTrackingBundle reads doc/tracking/items.json as a string', () => {
  withTempRepo((repo) => {
    mkdirSync(join(repo, 'doc/tracking'), { recursive: true });
    const items = '[{"id":"item-1","name":"US-01: Demo","labels":["US"]}]';
    writeFileSync(join(repo, TRACKING_ITEMS_PATH), items);
    const content = readTrackingBundle({ root: repo });
    assert.equal(content, items);
    assert.equal(JSON.parse(content)[0].id, 'item-1');
  });
});

test('readTrackingBundle returns "[]" when items.json is absent (uninitialised board)', () => {
  withTempRepo((repo) => {
    const content = readTrackingBundle({ root: repo });
    assert.equal(content, '[]');
    assert.deepEqual(JSON.parse(content), []);
  });
});

test('writeTrackingBundle persists the mutated items.json string', () => {
  withTempRepo((repo) => {
    const mutated = '[{"id":"item-2","name":"UC-001: X","labels":["UC"]}]';
    const { written, skipped } = writeTrackingBundle(mutated, { root: repo });
    assert.deepEqual(written, [TRACKING_ITEMS_PATH]);
    assert.deepEqual(skipped, []);
    assert.equal(readFileSync(join(repo, TRACKING_ITEMS_PATH), 'utf-8'), mutated);
  });
});

test('read → write → read round-trips the tracking content', () => {
  withTempRepo((repo) => {
    mkdirSync(join(repo, 'doc/tracking'), { recursive: true });
    writeFileSync(join(repo, TRACKING_ITEMS_PATH), '[]');
    // Simulate a content-passing mutation: read, mutate the string, write back.
    const before = readTrackingBundle({ root: repo });
    const board = JSON.parse(before);
    board.push({ id: 'item-3', name: 'UC-002: Added', labels: ['UC'] });
    writeTrackingBundle(JSON.stringify(board), { root: repo });
    const after = JSON.parse(readTrackingBundle({ root: repo }));
    assert.equal(after.length, 1);
    assert.equal(after[0].id, 'item-3');
  });
});

test('writeTrackingBundle rejects non-string content', () => {
  withTempRepo((repo) => {
    assert.throws(
      () => writeTrackingBundle({ not: 'a string' }, { root: repo }),
      /itemsContent must be a string/,
    );
  });
});

test('readTrackingBundle honours the path-traversal guard via a non-repo root', () => {
  // resolveProjectRoot would throw outside a git repo — exercising the
  // inherited guard chain. Here we just confirm the helper delegates to it.
  const notARepo = mkdtempSync(join(tmpdir(), 'mcp-tracking-no-git-'));
  try {
    assert.throws(
      () => readTrackingBundle({ cwd: notARepo }),
      /not inside a git repository/,
    );
  } finally {
    rmSync(notARepo, { recursive: true, force: true });
  }
});
