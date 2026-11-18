/**
 * UC-12211 — el PRD cambia en la misma PR que el código (medida spec_in_pr).
 *
 * prd-sync-guard real con un `gh` falso en el PATH (responde `gh pr view … --json files,body`).
 * - AC-01: una PR que no toca el PRD se detiene en «block» y el mensaje dice el PRD esperado;
 *   en un satélite vale una PR del orquestador enlazada desde la descripción.
 * - AC-02: una UC marcada «sin PRD» con motivo pasa.
 * - AC-04: en «warn» avisa y deja fusionar; una UC anterior a la regla no se detiene.
 * Ejecutar: node --test tests/hooks/prd-sync-guard.test.mjs
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { chmodSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { locatePrd } from '../../.claude/hooks/lib/prd-locate.mjs';

const repoRoot = resolve(fileURLToPath(import.meta.url), '../../..');
const HOOK = join(repoRoot, '.claude/hooks/prd-sync-guard.mjs');
const PRD = '# PRD\n\n## US-07: Pagos\n\nTexto.\n';

function write(dir, files) {
  for (const [rel, content] of Object.entries(files)) {
    mkdirSync(dirname(join(dir, rel)), { recursive: true });
    writeFileSync(join(dir, rel), typeof content === 'string' ? content : JSON.stringify(content));
  }
}

function repo(dir, files = {}, remote = '') {
  mkdirSync(dir, { recursive: true });
  spawnSync('git', ['init', '-q', '-b', 'feature/UC-701-x'], { cwd: dir });
  if (remote) spawnSync('git', ['remote', 'add', 'origin', remote], { cwd: dir });
  write(dir, files);
  return dir;
}

/** Un `gh` falso: `gh pr view <sel> [-R repo] --json files,body` responde lo que diga PRS[sel o repo#sel]. */
function fakeGh(base, prs) {
  const bin = join(base, 'bin');
  mkdirSync(bin, { recursive: true });
  writeFileSync(join(base, 'prs.json'), JSON.stringify(prs));
  writeFileSync(join(bin, 'gh'), `#!/usr/bin/env node
const prs = JSON.parse(require('fs').readFileSync(${JSON.stringify(join(base, 'prs.json'))}, 'utf8'));
const a = process.argv.slice(2);
if (a[0] !== 'pr' || a[1] !== 'view') process.exit(1);
const r = a.indexOf('-R');
const repo = r >= 0 ? a[r + 1] : '';
const sel = a[2] && !a[2].startsWith('-') ? a[2] : 'current';
const key = repo ? repo + '#' + sel : sel;
if (!(key in prs)) process.exit(1);
process.stdout.write(JSON.stringify(prs[key]));
`);
  chmodSync(join(bin, 'gh'), 0o755);
  return bin;
}

function merge(dir, bin, command = 'gh pr merge 12 --squash') {
  const r = spawnSync(process.execPath, [HOOK], {
    cwd: dir,
    input: JSON.stringify({ hook_event_name: 'PreToolUse', tool_name: 'Bash', tool_input: { command }, cwd: dir }),
    encoding: 'utf8',
    env: { ...process.env, PATH: `${bin}:${process.env.PATH}`, SPECBOX_ENFORCEMENT_POLICY: 'off' },
  });
  let note = '';
  try { note = JSON.parse(r.stdout || '{}').hookSpecificOutput?.additionalContext || ''; } catch { /* sin nota */ }
  return { code: r.status, stderr: r.stderr, note };
}

const policy = (mode, extra = {}) => ({ schema: 1, origin: 'new', measures: { spec_in_pr: { mode, ...extra } }, skips: [] });
const MARKER = { uc_id: 'UC-701', us_id: 'US-07', feature: 'UC-701' };
const FREEFORM = { specbox: { backend_type: 'freeform' } };

test('una PR que no toca el PRD se detiene en «block» y dice el PRD esperado (AC-01)', () => {
  const base = mkdtempSync(join(tmpdir(), 'prd-guard-'));
  try {
    const dir = repo(join(base, 'p'), {
      '.claude/settings.local.json': FREEFORM, 'doc/tracking/policy.json': policy('block'),
      'doc/prd/pagos/prd.md': PRD, '.quality/active_uc.json': MARKER,
    });
    const bin = fakeGh(base, { 12: { files: [{ path: 'src/pagos.ts' }], body: '' } });
    const r = merge(dir, bin);
    assert.equal(r.code, 2);
    assert.match(r.stderr, /medida spec_in_pr/);
    assert.match(r.stderr, /doc\/prd\/pagos\/prd\.md/);
    assert.match(r.stderr, /no_prd_reason/);
    // Queda el bloqueo en el registro del tablero FreeForm.
    assert.match(readFileSync(join(dir, 'doc/tracking/enforcement_events.jsonl'), 'utf8'), /"outcome":"blocked"/);

    const bin2 = fakeGh(join(base, 'b2'), { 12: { files: [{ path: 'src/pagos.ts' }, { path: 'doc/prd/pagos/prd.md' }], body: '' } });
    const ok = merge(dir, bin2);
    assert.equal(ok.code, 0);
    assert.equal(ok.note, '');
    assert.match(readFileSync(join(dir, 'doc/tracking/enforcement_events.jsonl'), 'utf8'), /"outcome":"passed"/);
  } finally {
    rmSync(base, { recursive: true, force: true });
  }
});

test('en un satélite vale una PR del orquestador enlazada que toca el PRD (AC-01)', () => {
  const base = mkdtempSync(join(tmpdir(), 'prd-guard-'));
  try {
    const orq = repo(join(base, 'manager'), { 'doc/prd/pagos/prd.md': PRD }, 'git@github.com:Acme/manager.git');
    const sat = repo(join(orq, 'repositorios', 'engine'), {
      '.claude/settings.local.json': { specbox: { backend_type: 'freeform' }, multirepo: { enabled: true, role: 'satellite', orchestrator: '../..' } },
      'doc/tracking/policy.json': policy('block'),
      '.quality/active_uc.json': MARKER,
    });
    const sin = fakeGh(join(base, 'g1'), { 12: { files: [{ path: 'src/x.ts' }], body: 'Sin enlace' } });
    const r = merge(sat, sin);
    assert.equal(r.code, 2);
    assert.match(r.stderr, /\.\.\/\.\.\/doc\/prd\/pagos\/prd\.md/);
    assert.match(r.stderr, /PR del orquestador/);
    const con = fakeGh(join(base, 'g2'), {
      12: { files: [{ path: 'src/x.ts' }], body: 'PRD en https://github.com/Acme/manager/pull/40' },
      'Acme/manager#40': { files: [{ path: 'doc/prd/pagos/prd.md' }], body: '' },
    });
    assert.equal(merge(sat, con).code, 0);
  } finally {
    rmSync(base, { recursive: true, force: true });
  }
});

test('una UC marcada «sin PRD» con motivo pasa (AC-02)', () => {
  const base = mkdtempSync(join(tmpdir(), 'prd-guard-'));
  try {
    const dir = repo(join(base, 'p'), {
      '.claude/settings.local.json': FREEFORM, 'doc/tracking/policy.json': policy('block'),
      '.quality/active_uc.json': { ...MARKER, no_prd_reason: 'Arreglo de una línea en la CI, sin cambio de comportamiento' },
    });
    const bin = fakeGh(base, { 12: { files: [{ path: 'scripts/ci.sh' }], body: '' } });
    assert.equal(merge(dir, bin).code, 0);
  } finally {
    rmSync(base, { recursive: true, force: true });
  }
});

test('en «warn» avisa y deja fusionar; una UC anterior a la regla no se detiene (AC-04)', () => {
  const base = mkdtempSync(join(tmpdir(), 'prd-guard-'));
  try {
    const bin = fakeGh(base, { 12: { files: [{ path: 'src/x.ts' }], body: '' } });
    const warn = repo(join(base, 'w'), { '.claude/settings.local.json': FREEFORM, 'doc/prd/pagos/prd.md': PRD, '.quality/active_uc.json': MARKER });
    const r = merge(warn, bin);
    assert.equal(r.code, 0);
    assert.match(r.note, /spec_in_pr en «warn»: la fusión sigue/);
    const vieja = repo(join(base, 'v'), {
      '.claude/settings.local.json': FREEFORM, 'doc/tracking/policy.json': policy('block'),
      'doc/prd/pagos/prd.md': PRD, '.quality/active_uc.json': { ...MARKER, predates_rule: ['spec_in_pr'] },
    });
    assert.equal(merge(vieja, bin).code, 0);
    // Sin gh (o sin respuesta) no se detiene nada; otra orden de gh no le importa.
    assert.equal(merge(warn, join(base, 'no-existe'), 'gh pr merge 12').code, 0);
    assert.equal(merge(warn, bin, 'gh pr view 12').code, 0);
  } finally {
    rmSync(base, { recursive: true, force: true });
  }
});

test('locatePrd sigue el orden de find_prd_path', () => {
  const base = mkdtempSync(join(tmpdir(), 'prd-locate-'));
  try {
    write(base, { 'doc/prd/pagos/prd.md': PRD, 'doc/prd/otro/prd.md': '# Otro\nUS-09\n' });
    assert.equal(locatePrd({ root: base, feature: 'UC-701', usId: 'US-07' }), 'doc/prd/pagos/prd.md');
    assert.equal(locatePrd({ root: base, feature: 'otro', usId: 'US-07' }), 'doc/prd/otro/prd.md');
    assert.equal(locatePrd({ root: base, usId: 'US-99' }), null);
    write(base, { 'doc/prds/us_07_prd.md': '# PRD' });
    assert.equal(locatePrd({ root: base, usId: 'US-07' }), 'doc/prds/us_07_prd.md');
  } finally {
    rmSync(base, { recursive: true, force: true });
  }
});
