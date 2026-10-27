// UC-11007: /handoff valida el handoff en cualquier proyecto. El validador viaja con la skill
// (~/.claude/skills/handoff/scripts/); antes estaba en .quality/scripts/ del engine, que ningún
// proyecto recibe, y el Paso 4 acababa en un error de Node. Se ejecuta el bloque del Paso 4 tal cual
// está escrito en SKILL.md.
//   node --test tests/hooks/handoff-validate.test.mjs

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execSync, spawnSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, readFileSync, symlinkSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const skill = readFileSync(join(repoRoot, '.claude/skills/handoff/SKILL.md'), 'utf8');
const paso4 = skill.slice(skill.indexOf('### Paso 4'));
const block = paso4.match(/```bash\n([\s\S]*?)```/)[1];

function project() {
  const dir = mkdtempSync(join(tmpdir(), 'handoff-validate-'));
  execSync('git init -q && git -c user.email=t@t -c user.name=t commit -q --allow-empty -m init', { cwd: dir });
  const script = `import(${JSON.stringify(join(repoRoot, '.claude/hooks/lib/handoff-builder.mjs'))}).then((m) => m.writeHandoff({ next_concrete_step: 'seguir' }, { trigger: 'manual' }))`;
  execSync(`${JSON.stringify(process.execPath)} --input-type=module -e ${JSON.stringify(script)}`, { cwd: dir });
  return dir;
}

function runPaso4(cwd, home) {
  const res = spawnSync('bash', ['-c', block], { cwd, encoding: 'utf8', env: { ...process.env, HOME: home } });
  return { code: res.status, out: `${res.stdout}${res.stderr}` };
}

test('el Paso 4 usa el validador que viaja con la skill, no uno de .quality/scripts del proyecto', () => {
  assert.match(block, /\.claude\/skills\/handoff\/scripts\/validate-handoff\.mjs/);
  assert.doesNotMatch(block, /node \.quality\/scripts\/validate-handoff/);
});

test('con SpecBox instalado (skills enlazadas como las deja la extensión) valida el handoff del proyecto', () => {
  const home = mkdtempSync(join(tmpdir(), 'home-'));
  mkdirSync(join(home, '.claude'));
  symlinkSync(join(repoRoot, '.claude/skills'), join(home, '.claude/skills'), 'dir');
  const r = runPaso4(project(), home);
  assert.equal(r.code, 0, r.out);
  assert.match(r.out, /\[VALID\] \.quality\/handoff\.md/);
});

test('sin el validador, dice cómo conseguirlo en vez de un error de Node', () => {
  const home = mkdtempSync(join(tmpdir(), 'home-vacio-'));
  const r = runPaso4(project(), home);
  assert.equal(r.code, 0);
  assert.match(r.out, /Falta el validador del handoff/);
  assert.match(r.out, /SpecBox: Install Engine/);
  assert.doesNotMatch(r.out, /Cannot find module|node:internal/);
});
