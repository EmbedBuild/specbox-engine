/**
 * UC-9301 (US-93): las condiciones `if` de los hooks casan con lo que vigilan.
 *
 * El campo `if` de un hook es una regla de permisos de Claude Code, no una expresión regular: en
 * Bash, `*` es un comodín sobre el comando entero; en Write y Edit, la ruta es un glob de gitignore
 * relativo al proyecto. Desde la v5.19.0 el engine las escribía como regex (`Bash(.*git commit.*)`,
 * `Write(src/.*)`) y, en una sesión real de Claude Code 2.1.288, ninguna se disparaba
 * (doc/research/hooks-que-no-saltaban/).
 *
 * AC-01: ninguna condición del engine ni de la plantilla de proyectos vuelve a escribirse como regex.
 * Además, cada hook casa con las acciones de la sesión real que lo disparaban y no con las parecidas
 * que no debían; el emparejador de abajo reproduce la semántica comprobada en esa sesión.
 *
 * Ejecutar: node --test tests/hooks/settings-if-syntax.test.mjs
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = resolve(fileURLToPath(import.meta.url), '../../..');
const SETTINGS = ['.claude/settings.json', 'templates/settings.json.template'];

/** Cada condición registrada: { file, event, matcher, hook, rule }. */
function conditions(path) {
  const settings = JSON.parse(readFileSync(join(repoRoot, path), 'utf8'));
  const out = [];
  for (const [event, groups] of Object.entries(settings.hooks ?? {})) {
    for (const group of groups) {
      for (const h of group.hooks ?? []) {
        if (h.if === undefined) continue;
        const hook = h.command?.match(/\.claude\/hooks\/([a-z0-9-]+)\.mjs/)?.[1];
        out.push({ file: path, event, matcher: group.matcher, hook, rule: h.if });
      }
    }
  }
  return out;
}

const escape = (s) => s.replace(/[.+?^${}()|[\]\\]/g, '\\$&');

/** Bash: `*` vale por cualquier secuencia, el resto es literal y casa el comando entero. */
function bashMatches(pattern, command) {
  return new RegExp(`^${pattern.split('*').map(escape).join('.*')}$`, 's').test(command);
}

/** Write/Edit: glob de gitignore relativo al proyecto (`**` cruza carpetas, `*` no). */
function pathMatches(pattern, relPath) {
  const re = pattern
    .split('**')
    .map((part) => part.split('*').map(escape).join('[^/]*'))
    .join('.*');
  return new RegExp(`^${re}$`).test(relPath);
}

function fires(rule, tool, value) {
  const m = rule.match(/^(\w+)\((.+)\)$/);
  if (!m || m[1] !== tool) return false;
  return tool === 'Bash' ? bashMatches(m[2], value) : pathMatches(m[2], value);
}

// Las acciones de la sesión real (doc/research/hooks-que-no-saltaban/sesion-real/pasos.txt).
const COMMIT = ['git commit -m uno', 'git commit --allow-empty --no-verify -m dos'];
const PUSH = ['git push origin HEAD:main', 'git push --force origin HEAD:main', 'git push -f origin HEAD:main'];
const OTHER = ['git add -A', 'git log --oneline -1', 'echo commit push'];
const EXPECTED = {
  'no-bypass-guard': {
    Bash: {
      yes: ['git commit --allow-empty --no-verify -m dos', 'git push --force origin HEAD:main', 'git push -f origin HEAD:main', 'git reset --hard HEAD'],
      no: ['git commit -m uno', 'git push origin HEAD:main', 'git reset --soft HEAD~1', ...OTHER],
    },
  },
  'commit-spec-guard': { Bash: { yes: COMMIT, no: [...PUSH, ...OTHER] } },
  'pre-commit-lint': { Bash: { yes: COMMIT, no: [...PUSH, ...OTHER] } },
  'e2e-gate': { Bash: { yes: COMMIT, no: [...PUSH, ...OTHER] } },
  'checkpoint-freshness-guard': { Bash: { yes: COMMIT, no: [...PUSH, ...OTHER] } },
  'app-docs-sync-guard': { Bash: { yes: COMMIT, no: [...PUSH, ...OTHER] } },
  'uc-lifecycle-guard': { Bash: { yes: PUSH, no: [...COMMIT, ...OTHER] } },
  'design-system-gate': { Bash: { yes: ['gh pr create --help', 'gh pr create --title x --body y'], no: ['gh pr list', ...PUSH, ...OTHER] } },
  'spec-guard': {
    Write: { yes: ['src/app.ts', 'lib/util.dart', 'src/features/a/b.tsx'], no: ['docs/nota.md', 'README.md', 'test/src.ts'] },
    Edit: { yes: ['src/app.ts', 'lib/util.dart'], no: ['docs/nota.md'] },
  },
};

for (const path of SETTINGS) {
  test(`${path}: ninguna condición está escrita como expresión regular`, () => {
    const all = conditions(path);
    assert.ok(all.length > 0, 'hay condiciones que comprobar');
    for (const c of all) {
      assert.match(c.rule, /^(Bash|Write|Edit|Read)\(.+\)$/, `${c.hook}: «${c.rule}» no es una regla de permisos`);
      assert.ok(!c.rule.includes('.*'), `${c.hook}: «${c.rule}» usa «.*» de regex; en una regla es «*»`);
      assert.ok(!/[\\^$|+?]|\(\?/.test(c.rule.slice(c.rule.indexOf('(') + 1, -1)), `${c.hook}: «${c.rule}» lleva sintaxis de regex`);
      if (/^\w+$/.test(c.matcher)) assert.equal(c.rule.split('(')[0], c.matcher, `${c.hook}: la regla no es de la herramienta de su grupo`);
    }
  });

  test(`${path}: cada hook se dispara con lo que vigila y no con lo parecido`, () => {
    const all = conditions(path);
    for (const [hook, tools] of Object.entries(EXPECTED)) {
      for (const [tool, { yes, no }] of Object.entries(tools)) {
        const rules = all.filter((c) => c.hook === hook && c.rule.startsWith(`${tool}(`)).map((c) => c.rule);
        assert.ok(rules.length > 0, `${hook} no tiene condición de ${tool}`);
        for (const v of yes) assert.ok(rules.some((r) => fires(r, tool, v)), `${hook} (${rules.join(', ')}) no se dispara con «${v}»`);
        for (const v of no) assert.ok(!rules.some((r) => fires(r, tool, v)), `${hook} (${rules.join(', ')}) se dispara con «${v}»`);
      }
    }
  });
}

test('el emparejador reproduce lo que pasó en la sesión real con las condiciones antiguas', () => {
  // Ninguna de las antiguas se disparó con su propia acción (sesion-real/disparos-antiguas.tsv vacío).
  assert.equal(fires('Bash(.*git commit.*)', 'Bash', 'git commit -m uno'), false);
  assert.equal(fires('Bash(.*reset --hard.*)', 'Bash', 'git reset --hard HEAD'), false);
  assert.equal(fires('Write(src/.*)', 'Write', 'src/app.ts'), false);
  // Y las nuevas, sí (sesion-real/disparos-nuevas.tsv).
  assert.equal(fires('Bash(*git commit*)', 'Bash', 'git commit -m uno'), true);
  assert.equal(fires('Write(src/**)', 'Write', 'src/app.ts'), true);
});
