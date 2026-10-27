// UC-11003: pre-commit-lint no bloquea un commit por un fichero que la configuración de ESLint
// ignora. Con la configuración plana, ESLint avisa «File ignored» y --max-warnings=0 lo convertía en
// bloqueo; --no-warn-ignored solo existe con esa configuración. Un eslint simulado se comporta como
// los dos (9 con eslint.config.*, 8 con .eslintrc) para no instalar ESLint en la CI.
//   node --test tests/hooks/pre-commit-lint.test.mjs

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync, execSync } from 'node:child_process';
import { chmodSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const hook = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '.claude', 'hooks', 'pre-commit-lint.mjs');

// Ignored: anything under dist/. A file with «warn» inside has a lint warning.
const FAKE_ESLINT = `#!/usr/bin/env node
const fs = require('fs');
const args = process.argv.slice(2);
fs.writeFileSync('eslint-args.json', JSON.stringify(args));
const flat = ['js', 'mjs', 'cjs'].some((e) => fs.existsSync('eslint.config.' + e));
if (!flat && args.includes('--no-warn-ignored')) { console.error('Invalid option \\'--no-warn-ignored\\''); process.exit(2); }
let warnings = 0;
for (const f of args.filter((a) => !a.startsWith('--'))) {
  if (f.startsWith('dist/')) {
    if (flat && !args.includes('--no-warn-ignored')) { console.log(f + '\\n  0:0  warning  File ignored because of a matching ignore pattern'); warnings++; }
  } else if (fs.readFileSync(f, 'utf8').includes('warn')) { console.log(f + '\\n  1:1  warning  Unexpected console statement  no-console'); warnings++; }
}
if (warnings && args.includes('--max-warnings=0')) { console.log('ESLint found too many warnings (maximum: 0).'); process.exit(1); }
`;

function project({ flat, files }) {
  const dir = mkdtempSync(join(tmpdir(), 'pcl-'));
  execSync('git init -q', { cwd: dir });
  mkdirSync(join(dir, 'node_modules/.bin'), { recursive: true });
  writeFileSync(join(dir, 'node_modules/.bin/eslint'), FAKE_ESLINT);
  chmodSync(join(dir, 'node_modules/.bin/eslint'), 0o755);
  writeFileSync(join(dir, flat ? 'eslint.config.mjs' : '.eslintrc.json'), flat ? 'export default [{ ignores: ["dist/**"] }];\n' : '{"ignorePatterns": ["dist/"]}\n');
  for (const [path, content] of Object.entries(files)) {
    mkdirSync(join(dir, dirname(path)), { recursive: true });
    writeFileSync(join(dir, path), content);
  }
  execSync(`git add -f ${Object.keys(files).join(' ')}`, { cwd: dir });
  return dir;
}

function commit(dir) {
  const res = spawnSync(process.execPath, [hook], {
    cwd: dir,
    input: JSON.stringify({ hook_event_name: 'PreToolUse', tool_name: 'Bash', tool_input: { command: 'git commit -m prueba' }, cwd: dir }),
    encoding: 'utf8',
  });
  let args = null;
  try { args = JSON.parse(readFileSync(join(dir, 'eslint-args.json'), 'utf8')); } catch { /* eslint not run */ }
  return { code: res.status, stderr: res.stderr, args };
}

test('configuración plana: un fichero ignorado entra en el commit sin bloqueo', () => {
  const r = commit(project({ flat: true, files: { 'dist/bundle.js': 'export const a = 1;\n', 'src/ok.js': 'export const b = 2;\n' } }));
  assert.equal(r.code, 0, r.stderr);
  assert.ok(r.args.includes('--no-warn-ignored'));
});

test('configuración plana: un aviso en un fichero no ignorado sigue bloqueando', () => {
  const r = commit(project({ flat: true, files: { 'dist/bundle.js': 'x\n', 'src/mal.js': 'warn\n' } }));
  assert.equal(r.code, 2);
  assert.match(r.stderr, /LINT: el commit no pasa el linter del proyecto/);
  assert.match(r.stderr, /no-console/);
  assert.doesNotMatch(r.stderr, /File ignored/);
});

test('.eslintrc: el hook llama a eslint como en la 6.29.0, sin --no-warn-ignored', () => {
  const ok = commit(project({ flat: false, files: { 'src/ok.js': 'export const b = 2;\n' } }));
  assert.equal(ok.code, 0, ok.stderr);
  assert.deepEqual(ok.args, ['--max-warnings=0', 'src/ok.js']);

  const bad = commit(project({ flat: false, files: { 'src/mal.js': 'warn\n' } }));
  assert.equal(bad.code, 2);
  assert.match(bad.stderr, /no-console/);
});
