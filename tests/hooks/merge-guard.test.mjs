/**
 * UC-12401 — lo que se fusiona está demostrado (medida closing_evidence, hook merge-guard).
 *
 * merge-guard real sobre un proyecto FreeForm con su doc/tracking/items.json:
 * - AC-03: una UC con una prueba de aceptación que falla (su criterio marcado con passed: false) no
 *   llega a fusionarse en «block», y el mensaje dice qué criterio falla y por qué.
 * - AC-06: en «warn» avisa y deja fusionar; una UC empezada antes de que la medida bloqueara avisa.
 * - Sin UC activa, con la medida apagada o con todo demostrado, calla.
 *
 * UC-12402 (medida independent_review):
 * - AC-01/AC-03: sin el visto bueno de otro contexto la fusión no sigue en «block»; fuera de
 *   «agresivo» hace falta la persona (en FreeForm, que no tiene panel, basta el evaluador).
 * - AC-04: en «warn» avisa de que falta el veredicto independiente y deja fusionar.
 * Ejecutar: node --test tests/hooks/merge-guard.test.mjs
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { closingEvidence, freeformCriteria, startedBeforeBlock } from '../../.claude/hooks/lib/closing-evidence.mjs';
import { independentReview } from '../../.claude/hooks/lib/independent-review.mjs';

const repoRoot = resolve(fileURLToPath(import.meta.url), '../../..');
const HOOK = join(repoRoot, '.claude/hooks/merge-guard.mjs');
const BLOCK_SINCE = '2026-11-18T10:00:00+00:00';
const PASS = { type: 'test', label: 'cobra', passed: true };

const UC = { id: 'uc701', name: 'UC-701: Cobrar', state: 'review', labels: ['UC'], meta: { uc_id: 'UC-701' } };
const ac = (n, state, evidence) => ({
  id: `ac${n}`,
  name: `[AC-0${n}] Criterio ${n}`,
  state,
  labels: ['AC'],
  parent_id: 'uc701',
  meta: { ac_id: `AC-0${n}`, ...(evidence ? { evidence, verdict: { passed: state === 'done' } } : {}) },
});

function project({ mode = 'block', review = 'off', level = '', items, marker = { uc_id: 'UC-701', started_at: '2026-11-19T09:00:00+00:00' } }) {
  const dir = mkdtempSync(join(tmpdir(), 'merge-guard-'));
  spawnSync('git', ['init', '-q', '-b', 'feature/UC-701-x'], { cwd: dir });
  const files = {
    '.claude/settings.local.json': { specbox: { backend_type: 'freeform', ...(level ? { autopilot: { level } } : {}) } },
    'doc/tracking/policy.json': {
      schema: 1, origin: 'existing', skips: [],
      measures: {
        closing_evidence: { mode, ...(mode === 'block' ? { block_since: BLOCK_SINCE } : {}) },
        independent_review: { mode: review, ...(review === 'block' ? { block_since: BLOCK_SINCE } : {}) },
      },
    },
    'doc/tracking/items.json': items,
    ...(marker ? { '.quality/active_uc.json': marker } : {}),
  };
  for (const [rel, content] of Object.entries(files)) {
    mkdirSync(dirname(join(dir, rel)), { recursive: true });
    writeFileSync(join(dir, rel), JSON.stringify(content));
  }
  return dir;
}

function merge(dir, command = 'gh pr merge 12 --squash --delete-branch') {
  const r = spawnSync(process.execPath, [HOOK], {
    cwd: dir,
    input: JSON.stringify({ hook_event_name: 'PreToolUse', tool_name: 'Bash', tool_input: { command }, cwd: dir }),
    encoding: 'utf8',
    env: { ...process.env, SPECBOX_ENFORCEMENT_POLICY: 'off' },
  });
  let note = '';
  try { note = JSON.parse(r.stdout || '{}').hookSpecificOutput?.additionalContext || ''; } catch { /* sin nota */ }
  return { code: r.status, stderr: r.stderr, note };
}

test('AC-03: un criterio con la prueba que falla detiene la fusión en «block» y dice cuál', () => {
  const dir = project({ items: [UC, ac(1, 'done', [PASS]), ac(2, 'backlog', [{ ...PASS, passed: false }])] });
  try {
    const r = merge(dir);
    assert.equal(r.code, 2);
    assert.match(r.stderr, /closing_evidence/);
    assert.match(r.stderr, /UC-701: 1 de 2 criterios sin demostrar: AC-02 \(sin marcar\)/);
    assert.match(r.stderr, /mark_ac/);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test('un criterio hecho sin recibo que pase también detiene la fusión', () => {
  const dir = project({ items: [UC, ac(1, 'done', [{ ...PASS, passed: false }]), ac(2, 'done', [])] });
  try {
    const r = merge(dir);
    assert.equal(r.code, 2);
    assert.match(r.stderr, /AC-01 \(con evidencia que falla\), AC-02 \(sin evidencia\)/);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test('AC-06: en «warn» avisa y deja fusionar', () => {
  const dir = project({ mode: 'warn', items: [UC, ac(1, 'backlog')] });
  try {
    const r = merge(dir);
    assert.equal(r.code, 0);
    assert.match(r.note, /«warn»: la fusión sigue/);
    assert.match(r.note, /AC-01 \(sin marcar\)/);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test('AC-06: una UC empezada antes de que la medida bloqueara avisa y no se detiene', () => {
  const dir = project({ items: [UC, ac(1, 'backlog')], marker: { uc_id: 'UC-701', started_at: '2026-11-17T09:00:00+00:00' } });
  try {
    const r = merge(dir);
    assert.equal(r.code, 0);
    assert.match(r.note, /anterior a la regla closing_evidence/);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test('todo demostrado, sin UC activa o con la medida apagada: calla', () => {
  for (const opts of [
    { items: [UC, ac(1, 'done', [PASS])] },
    { items: [UC, ac(1, 'backlog')], marker: null },
    { mode: 'off', items: [UC, ac(1, 'backlog')] },
  ]) {
    const dir = project(opts);
    try {
      const r = merge(dir);
      assert.equal(r.code, 0);
      assert.equal(r.note, '');
      assert.equal(r.stderr, '');
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  }
});

test('otros comandos no le importan', () => {
  const dir = project({ items: [UC, ac(1, 'backlog')] });
  try {
    const r = merge(dir, 'gh pr view 12');
    assert.equal(r.code, 0);
    assert.equal(r.stderr, '');
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test('los criterios de FreeForm: evidencia desconocida si el criterio no la guarda', () => {
  const acs = freeformCriteria([UC, ac(1, 'done'), ac(2, 'done', [PASS])], 'UC-701');
  assert.deepEqual(acs, [
    { ac_id: 'AC-01', done: true, evidence: null },
    { ac_id: 'AC-02', done: true, evidence: [PASS] },
  ]);
  assert.equal(closingEvidence(acs).ok, true);
  assert.equal(freeformCriteria([UC], 'UC-999'), null);
  assert.equal(startedBeforeBlock('2026-11-17T00:00:00Z', BLOCK_SINCE), true);
  assert.equal(startedBeforeBlock(undefined, BLOCK_SINCE), false);
});

// ── UC-12402: independent_review ─────────────────────────────────────

const ACCEPTED = (independent, at = '2026-11-19T10:00:00Z') => ({ verdict: 'accepted', independent, at, by_kind: 'agent' });
const ucWith = (verdicts) => ({ ...UC, meta: { ...UC.meta, review_verdicts: verdicts } });

test('AC-01/AC-04: sin veredicto independiente, «block» detiene la fusión y «warn» avisa', () => {
  for (const [review, code, re] of [['block', 2, null], ['warn', 0, /«warn»: la fusión sigue/]]) {
    const dir = project({ mode: 'off', review, level: 'agresivo', items: [ucWith([ACCEPTED(false)]), ac(1, 'done', [PASS])] });
    try {
      const r = merge(dir);
      assert.equal(r.code, code, review);
      const text = review === 'block' ? r.stderr : r.note;
      assert.match(text, /independent_review/);
      assert.match(text, /contexto distinto del que implementó/);
      if (re) assert.match(text, re);
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  }
});

test('AC-01: un evaluador independiente que acepta deja fusionar; una devolución posterior no', () => {
  const ok = project({ mode: 'off', review: 'block', level: 'agresivo', items: [ucWith([ACCEPTED(true)]), ac(1, 'done', [PASS])] });
  const back = project({
    mode: 'off', review: 'block', level: 'agresivo',
    items: [ucWith([ACCEPTED(true, '2026-11-19T10:00:00Z'), { verdict: 'returned', reason: 'falta el caso vacío', independent: true, at: '2026-11-19T11:00:00Z' }]), ac(1, 'done', [PASS])],
  });
  try {
    assert.equal(merge(ok).code, 0);
    const r = merge(back);
    assert.equal(r.code, 2);
    assert.match(r.stderr, /La UC fue devuelta: falta el caso vacío/);
  } finally {
    rmSync(ok, { recursive: true, force: true });
    rmSync(back, { recursive: true, force: true });
  }
});

test('AC-03: fuera de «agresivo» hace falta una persona (native); FreeForm, sin panel, acepta el evaluador', () => {
  assert.equal(independentReview({ verdicts: [ACCEPTED(true)], level: 'equilibrado', backendType: 'native' }).reason_code, 'no_person_acceptance');
  assert.equal(independentReview({ humanAcceptance: { by: 'Ana' }, verdicts: [], level: 'equilibrado', backendType: 'native' }).ok, true);
  assert.equal(independentReview({ verdicts: [ACCEPTED(true)], level: 'agresivo', backendType: 'native' }).ok, true);
  assert.equal(independentReview({ verdicts: [ACCEPTED(true)], level: 'equilibrado', backendType: 'freeform' }).ok, true);
  const dir = project({ mode: 'off', review: 'block', level: 'equilibrado', items: [ucWith([ACCEPTED(true)]), ac(1, 'done', [PASS])] });
  try {
    assert.equal(merge(dir).code, 0);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
