/**
 * UC-9302 (US-93): cada hook avisa o bloquea por un canal que llega.
 *
 * AC-04: ningún hook registrado del engine termina con un código que ni bloquea ni llega al agente.
 * Comprobado en sesiones reales de Claude Code 2.1.288 (doc/research/hooks-que-no-saltaban/):
 *   - exit 2 + stderr → bloquea (PreToolUse) o el agente recibe el motivo (PostToolUse);
 *   - exit 0 + JSON (additionalContext, o una decisión con updatedInput) → llega al agente;
 *   - exit 1, o exit 0 con texto por stdout o stderr → no llega a nadie. Prohibido.
 *
 * Para cada hook registrado: un escenario real que lo hace hablar, con la entrada que manda Claude
 * Code (tool_input). Un hook nuevo sin escenario ni exención hace fallar la prueba.
 *
 * Ejecutar: node --test tests/hooks/hook-channels.test.mjs
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = resolve(fileURLToPath(import.meta.url), '../../..');
const hooksDir = join(repoRoot, '.claude/hooks');

/** Hooks registrados que no se comunican con el agente por esta vía, con su motivo. */
const EXEMPT = {
  'session-start': 'SessionStart: su stdout se añade al contexto por diseño de Claude Code',
  'on-session-end': 'Stop: solo escribe telemetría en .quality/logs',
  'read-tracker': 'PostToolUse de Read: solo anota la lectura, en silencio',
};

function registered() {
  const s = JSON.parse(readFileSync(join(repoRoot, '.claude/settings.json'), 'utf8'));
  const names = new Set();
  for (const groups of Object.values(s.hooks)) for (const g of groups) for (const h of g.hooks) {
    const n = h.command.match(/hooks\/([a-z0-9-]+)\.mjs/)?.[1];
    if (n) names.add(n);
  }
  return [...names].sort();
}

/** Un repo git temporal con lo que pida el escenario. */
function repo({ branch = 'feature/UC-1', specDriven = true, activeUC = false, files = {} } = {}) {
  const dir = mkdtempSync(join(tmpdir(), 'hook-channel-'));
  const git = (...a) => spawnSync('git', a, { cwd: dir, encoding: 'utf8' });
  git('init', '-q', '-b', branch);
  git('config', 'user.email', 't@t');
  git('config', 'user.name', 't');
  const write = (rel, content) => {
    mkdirSync(dirname(join(dir, rel)), { recursive: true });
    writeFileSync(join(dir, rel), content);
  };
  write('README.md', 'x\n');
  if (specDriven) write('.claude/project-config.json', JSON.stringify({ boardId: 'EmbedBuild/demo', backend_type: 'native' }));
  git('add', '-A');
  git('commit', '-qm', 'base');
  if (activeUC) write('.quality/active_uc.json', JSON.stringify({ uc_id: 'UC-1', feature: 'demo' }));
  for (const [rel, content] of Object.entries(files)) write(rel, content);
  return { dir, git, write, done: () => rmSync(dir, { recursive: true, force: true }) };
}

function run(hook, dir, event, tool, toolInput, env = {}) {
  const payload = { hook_event_name: event, tool_name: tool, tool_input: toolInput, cwd: dir };
  const res = spawnSync(process.execPath, [join(hooksDir, `${hook}.mjs`)], {
    cwd: dir, input: JSON.stringify(payload), encoding: 'utf8', timeout: 60000, env: { ...process.env, ...env },
  });
  return { code: res.status, stdout: res.stdout || '', stderr: res.stderr || '' };
}

/** El hook habló por un canal que llega: bloqueo con motivo, o JSON para el agente. */
function assertReaches(r, label, expect) {
  assert.notEqual(r.code, 1, `${label}: exit 1 no bloquea ni llega al agente`);
  assert.ok([0, 2].includes(r.code), `${label}: código ${r.code}`);
  if (r.code === 2) {
    assert.ok(r.stderr.trim(), `${label}: bloquea sin decir por qué (stderr vacío)`);
  } else {
    assert.equal(r.stderr.trim(), '', `${label}: stderr con exit 0 no lo ve nadie`);
    if (r.stdout.trim()) {
      const out = JSON.parse(r.stdout);
      assert.ok(out.hookSpecificOutput, `${label}: stdout que no es una salida para el agente`);
    }
  }
  if (expect === 'block') assert.equal(r.code, 2, `${label}: tenía que bloquear`);
  if (expect === 'note') assert.match(JSON.parse(r.stdout).hookSpecificOutput.additionalContext, /\S/, `${label}: tenía que dejar una nota`);
}

/** Escenarios que hacen hablar a cada hook: [nombre, expectativa, función que devuelve el resultado]. */
const SCENARIOS = {
  'no-bypass-guard': [
    ['reset --hard', 'block', (p) => run('no-bypass-guard', p.dir, 'PreToolUse', 'Bash', { command: 'git reset --hard HEAD' })],
    ['--force-with-lease', 'silent', (p) => run('no-bypass-guard', p.dir, 'PreToolUse', 'Bash', { command: 'git push --force-with-lease origin x' })],
  ],
  'commit-spec-guard': [
    ['commit en main', 'block', () => { const p = repo({ branch: 'main' }); try { return run('commit-spec-guard', p.dir, 'PreToolUse', 'Bash', { command: 'git commit -m x' }); } finally { p.done(); } }],
    ['sin UC activa', 'note', (p) => run('commit-spec-guard', p.dir, 'PreToolUse', 'Bash', { command: 'git commit -m x' })],
  ],
  'pre-commit-lint': [
    ['un .py que no pasa ruff', 'block', (p) => {
      p.write('malo.py', 'import os\nx = 1\n');
      return run('pre-commit-lint', p.dir, 'PreToolUse', 'Bash', { command: 'git add malo.py && git commit -m x' });
    }, () => spawnSync('ruff', ['--version']).status === 0],
  ],
  'e2e-gate': [
    ['evidencia sin results.json', 'block', (p) => {
      p.write('.quality/evidence/demo/acceptance/shot.png', 'x');
      p.git('add', '-f', '.quality/evidence/demo/acceptance/shot.png');
      return run('e2e-gate', p.dir, 'PreToolUse', 'Bash', { command: 'git commit -m x' });
    }],
  ],
  'app-docs-sync-guard': [
    ['deriva en modo aviso', 'note', (p) => { driftDocs(p); return run('app-docs-sync-guard', p.dir, 'PreToolUse', 'Bash', { command: 'git commit -m x' }); }],
    ['deriva con block_on_drift', 'block', (p) => {
      driftDocs(p);
      p.write('.claude/settings.local.json', JSON.stringify({ specbox: { app_docs_sync: { block_on_drift: true } } }));
      return run('app-docs-sync-guard', p.dir, 'PreToolUse', 'Bash', { command: 'git commit -m x' });
    }],
  ],
  'checkpoint-freshness-guard': [
    ['UC activa sin checkpoint', 'note', () => { const p = repo({ activeUC: true }); try { return run('checkpoint-freshness-guard', p.dir, 'PostToolUse', 'Bash', { command: 'git commit -m x' }); } finally { p.done(); } }],
  ],
  'uc-lifecycle-guard': [
    ['push sin pasar a revisión', 'note', () => { const p = repo({ activeUC: true }); try { return run('uc-lifecycle-guard', p.dir, 'PostToolUse', 'Bash', { command: 'git push origin feature/UC-1' }); } finally { p.done(); } }],
  ],
  'spec-guard': [
    ['código en main', 'block', () => { const p = repo({ branch: 'main' }); try { return run('spec-guard', p.dir, 'PostToolUse', 'Write', { file_path: join(p.dir, 'src/app.ts') }); } finally { p.done(); } }],
    ['código sin UC', 'note', (p) => run('spec-guard', p.dir, 'PostToolUse', 'Write', { file_path: join(p.dir, 'src/app.ts') })],
  ],
  'design-gate': [
    ['página sin diseño', 'block', (p) => { p.write('app/propuestas/page.tsx', 'export default null\n'); return run('design-gate', p.dir, 'PostToolUse', 'Write', { file_path: join(p.dir, 'app/propuestas/page.tsx') }); }],
  ],
  'design-system-gate': [
    ['brecha de diseño en modo aviso', 'note', (p) => {
      copyFileSync(join(repoRoot, 'tests/fixtures/design_system/tinta.design-system.tokens.json'), join(mkdirP(p.dir, 'src/styles/tokens'), 'design-system.tokens.json'));
      p.git('add', '-A');
      p.git('commit', '-qm', 'tokens');
      p.write('src/Promo.tsx', "export const P = () => <div style={{ color: '#FF0000' }}>x</div>;\n");
      return run('design-system-gate', p.dir, 'PreToolUse', 'Bash', { command: 'gh pr create --title x --body y' });
    }],
  ],
  'design-review-gate': [
    ['«Block» en modo bloqueante', 'block', (p) => {
      p.write('doc/design/propuestas/listado.verify.md', '# Verificación\n\n**Veredicto: Block · Total: 20/40**\n\n## Tres problemas prioritarios\n1. Desborda a 390.\n');
      p.write('.claude/settings.local.json', JSON.stringify({ specbox: { design_review: { mode: 'block' } } }));
      return run('design-review-gate', p.dir, 'PreToolUse', 'mcp__SpecBox-MCP__move_uc', { uc_id: 'UC-1', target: 'review' });
    }],
  ],
  'quality-first-guard': [
    ['editar sin leer', 'block', (p) => run('quality-first-guard', p.dir, 'PreToolUse', 'Edit', { file_path: join(p.dir, 'README.md') })],
    ['crear un fichero nuevo', 'silent', (p) => run('quality-first-guard', p.dir, 'PreToolUse', 'Write', { file_path: join(p.dir, 'nuevo.ts') })],
  ],
  'healing-budget-guard': [
    ['8 reparaciones', 'block', () => {
      const p = repo({ activeUC: true, files: { '.quality/evidence/demo/healing.jsonl': '{}\n'.repeat(8) } });
      try { return run('healing-budget-guard', p.dir, 'PreToolUse', 'Write', { file_path: join(p.dir, 'src/app.ts') }); } finally { p.done(); }
    }],
  ],
  'pipeline-phase-guard': [
    ['código de feature antes del design-to-code', 'block', () => {
      const p = repo({ activeUC: true, files: { '.quality/evidence/demo/pipeline_state.json': JSON.stringify({ completed_phases: [] }) } });
      try { return run('pipeline-phase-guard', p.dir, 'PreToolUse', 'Write', { file_path: 'lib/domain/propuesta.dart' }); } finally { p.done(); }
    }],
  ],
  'stripe-safety-guard': [
    ['clave live escrita en el código', 'block', (p) => run('stripe-safety-guard', p.dir, 'PreToolUse', 'Write', { file_path: 'src/billing/stripe.ts', content: `const k = 'sk_live_${'a'.repeat(24)}';\n` })],
  ],
  'pre-read-budget-guard': [
    ['lectura de más del 5 % de la ventana', 'note', (p) => { p.write('grande.txt', 'x'.repeat(240_000)); return run('pre-read-budget-guard', p.dir, 'PreToolUse', 'Read', { file_path: join(p.dir, 'grande.txt') }); }],
  ],
  'context-budget-guard': [
    ['encargo por encima del presupuesto', 'note', (p) => run('context-budget-guard', p.dir, 'PreToolUse', 'Task', { prompt: 'x'.repeat(80_000) })],
  ],
  'file-ownership-guard': [
    ['escritura fuera de lo que le toca', 'note', (p) => {
      mkdirP(p.dir, '.claude/skills/implement');
      copyFileSync(join(repoRoot, '.claude/skills/implement/file-ownership.md'), join(p.dir, '.claude/skills/implement/file-ownership.md'));
      p.write('.quality/active_agent.json', JSON.stringify({ agent: 'AG-01', feature_slug: 'demo', phase: 'feature', started_at: 'now' }));
      return run('file-ownership-guard', p.dir, 'PreToolUse', 'Write', { file_path: 'test/foo.dart' });
    }],
  ],
  'pre-prd-discovery-check': [
    ['sin discovery en modo aviso', 'note', (p) => { p.write('.claude/settings.local.json', JSON.stringify({ specbox: { discovery: { gate_mode: 'warn' } } })); return run('pre-prd-discovery-check', p.dir, 'PreToolUse', 'Skill', { command: '/prd nueva_feature' }); }],
    ['sin discovery en modo bloqueante', 'block', (p) => { p.write('.claude/settings.local.json', JSON.stringify({ specbox: { discovery: { gate_mode: 'block' } } })); return run('pre-prd-discovery-check', p.dir, 'PreToolUse', 'Skill', { command: '/prd nueva_feature' }); }],
  ],
  'freeform-path-guard': [
    ['ruta relativa de FreeForm', 'decision', (p) => run('freeform-path-guard', p.dir, 'PreToolUse', 'mcp__SpecBox-MCP__set_auth_token', { backend_type: 'freeform', root_path: 'doc/tracking', api_key: 'freeform', token: '' })],
  ],
};

function mkdirP(base, rel) {
  mkdirSync(join(base, rel), { recursive: true });
  return join(base, rel);
}

/** doc/app con una firma registrada que no coincide: deriva. */
function driftDocs(p) {
  p.write('doc/app/app_prd.md', '<!-- @specbox:zone start kind="manual" id="vision" -->\nVisión\n<!-- @specbox:zone end -->\n');
  p.write('.quality/app_docs_sync.lock', JSON.stringify({ signatures: { app_prd: 'abcd'.repeat(16) } }));
}

test('cada hook registrado tiene escenario o exención con motivo', () => {
  for (const name of registered()) {
    assert.ok(SCENARIOS[name] || EXEMPT[name], `el hook ${name} no tiene escenario en este test ni exención`);
  }
});

test('ningún hook registrado sale con 1 ni escribe avisos por stdout en texto', () => {
  for (const name of registered()) {
    if (EXEMPT[name]) continue;
    const src = readFileSync(join(hooksDir, `${name}.mjs`), 'utf8');
    assert.doesNotMatch(src, /process\.exit\(1\)/, `${name}: exit 1 no bloquea`);
    assert.doesNotMatch(src, /console\.log\(|printWarning\(|printInfo\(|printBlock\(/, `${name}: texto por stdout que nadie ve`);
  }
});

for (const [hook, cases] of Object.entries(SCENARIOS)) {
  for (const [label, expect, scenario, available = () => true] of cases) {
    test(`${hook}: ${label}`, { skip: available() ? false : 'falta la herramienta que usa' }, () => {
      const p = repo();
      try {
        const r = scenario(p);
        if (expect === 'silent') {
          assert.equal(r.code, 0, `${hook}: ${label}`);
          assert.equal(`${r.stdout}${r.stderr}`.trim(), '', `${hook}: ${label} no tenía que decir nada`);
        } else if (expect === 'decision') {
          assert.equal(r.code, 0);
          assert.ok(JSON.parse(r.stdout).hookSpecificOutput, `${hook}: ${label}`);
        } else {
          assertReaches(r, `${hook}: ${label}`, expect);
        }
      } finally {
        p.done();
      }
    });
  }
}

test('el bloqueo de los guardias usa la entrada real (tool_input) y no solo el formato antiguo', () => {
  assert.ok(existsSync(join(hooksDir, 'lib/utils.mjs')));
  for (const name of ['quality-first-guard', 'healing-budget-guard', 'pipeline-phase-guard', 'read-tracker', 'no-bypass-guard', 'spec-guard', 'uc-lifecycle-guard']) {
    const src = readFileSync(join(hooksDir, `${name}.mjs`), 'utf8');
    assert.match(src, /readHookInput|tool_input/, `${name} no lee tool_input`);
  }
});
