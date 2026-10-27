// UC-11002: los scripts de las skills funcionan ejecutados por su enlace. Con la extensión,
// ~/.claude/skills son enlaces al clon de ~/.specbox/specbox-engine; un script que comparaba
// import.meta.url con la ruta del enlace creía que lo estaban importando y salía con 0 sin hacer nada.
//   node --test tests/design-review/scripts-by-link.test.mjs

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, rmSync, symlinkSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const skills = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '.claude', 'skills');

const SCRIPTS = [
  'design-review/scripts/verify.mjs',
  'design-review/scripts/verify-flutter.mjs',
  'design-review/scripts/canvas.mjs',
  'design-review/scripts/flutter-rules.mjs',
  'visual-setup/scripts/ds-artifact.mjs',
];

function run(path) {
  const res = spawnSync(process.execPath, [path], { encoding: 'utf8', timeout: 30_000 });
  return { code: res.status, out: `${res.stdout}${res.stderr}` };
}

test('sin argumentos, cada script dice cómo se usa también por su enlace, igual que por su ruta real', () => {
  const home = mkdtempSync(join(tmpdir(), 'skills-link-'));
  const link = join(home, 'skills');
  symlinkSync(skills, link, 'dir');
  try {
    for (const script of SCRIPTS) {
      const real = run(join(skills, script));
      const linked = run(join(link, script));
      const name = script.split('/').pop();
      assert.equal(real.code, 1, `${script} por su ruta real: ${real.out}`);
      assert.match(real.out, new RegExp(`^Uso: node ${name.replace('.', '\\.')}`), script);
      assert.equal(linked.code, real.code, `${script} por el enlace sale con ${linked.code}: ${linked.out || '(sin salida)'}`);
      assert.equal(linked.out, real.out, `${script} por el enlace`);
    }
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});
