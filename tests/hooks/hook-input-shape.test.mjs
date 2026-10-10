/**
 * UC-9301 (US-93): los hooks leen la entrada que manda Claude Code.
 *
 * Claude Code pasa los argumentos de la herramienta en `tool_input` (`command` en Bash, `file_path`
 * con ruta absoluta en Write y Edit). no-bypass-guard, uc-lifecycle-guard y spec-guard los leían del
 * nivel superior, el formato de sus pruebas de humo, así que con la entrada real no veían nada aunque
 * se dispararan. Estas pruebas usan la entrada real; el formato antiguo sigue funcionando.
 *
 * Ejecutar: node --test tests/hooks/hook-input-shape.test.mjs
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = resolve(fileURLToPath(import.meta.url), '../../..');
const hook = (name) => join(repoRoot, '.claude/hooks', `${name}.mjs`);

function run(name, payload, cwd = repoRoot) {
  return spawnSync(process.execPath, [hook(name)], { cwd, input: JSON.stringify(payload), encoding: 'utf8' });
}

/** Proyecto spec-driven en main, sin UC activa. */
function specDrivenOnMain() {
  const dir = mkdtempSync(join(tmpdir(), 'hook-input-'));
  const git = (...a) => spawnSync('git', a, { cwd: dir, encoding: 'utf8' });
  git('init', '-q', '-b', 'main');
  git('config', 'user.email', 't@t');
  git('config', 'user.name', 't');
  mkdirSync(join(dir, '.claude'), { recursive: true });
  writeFileSync(join(dir, '.claude/project-config.json'), JSON.stringify({ boardId: 'EmbedBuild/demo', backend_type: 'native' }));
  writeFileSync(join(dir, 'README.md'), 'x\n');
  git('add', '-A');
  git('commit', '-qm', 'base');
  return { dir, done: () => rmSync(dir, { recursive: true, force: true }) };
}

test('no-bypass-guard ve el comando en tool_input', () => {
  for (const command of ['git commit --no-verify -m x', 'git push --force origin rama', 'git reset --hard HEAD~1']) {
    const res = run('no-bypass-guard', { hook_event_name: 'PreToolUse', tool_name: 'Bash', tool_input: { command } });
    assert.equal(res.status, 2, command);
    assert.match(res.stderr, /GUARDIA DE CALIDAD/, command);
  }
  const ok = run('no-bypass-guard', { tool_name: 'Bash', tool_input: { command: 'git push origin rama' } });
  assert.equal(ok.status, 0);
});

test('spec-guard ve la ruta absoluta en tool_input', () => {
  const p = specDrivenOnMain();
  try {
    const res = run('spec-guard', { hook_event_name: 'PostToolUse', tool_name: 'Write', tool_input: { file_path: join(p.dir, 'src', 'app.ts'), content: 'x' } }, p.dir);
    assert.equal(res.status, 2, 'código en main: el agente recibe el motivo');
    assert.match(res.stderr, /SPEC GUARD/);
    const docs = run('spec-guard', { tool_name: 'Write', tool_input: { file_path: join(p.dir, 'docs', 'nota.md') } }, p.dir);
    assert.equal(docs.status, 0);
  } finally {
    p.done();
  }
});

test('uc-lifecycle-guard ve el comando en tool_input', () => {
  // Con el comando leído, en una rama de trabajo de un proyecto spec-driven revisa la UC; sin él,
  // salía antes de mirar nada. Aquí basta con comprobar que deja de ignorar un git push real.
  const p = specDrivenOnMain();
  try {
    spawnSync('git', ['checkout', '-qb', 'feature/UC-1'], { cwd: p.dir });
    mkdirSync(join(p.dir, '.quality'), { recursive: true });
    writeFileSync(join(p.dir, '.quality/active_uc.json'), JSON.stringify({ uc_id: 'UC-1', feature: 'demo' }));
    const res = run('uc-lifecycle-guard', { hook_event_name: 'PostToolUse', tool_name: 'Bash', tool_input: { command: 'git push origin feature/UC-1' } }, p.dir);
    assert.equal(res.status, 0, 'avisa, no bloquea');
    assert.match(JSON.parse(res.stdout).hookSpecificOutput.additionalContext, /UC LIFECYCLE/, 'con el comando real, revisa la UC y avisa al agente');
  } finally {
    p.done();
  }
});

test('el formato antiguo de las pruebas de humo sigue funcionando', () => {
  const res = run('no-bypass-guard', { command: 'git push --force origin rama' });
  assert.equal(res.status, 2);
});
