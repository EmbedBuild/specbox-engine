/**
 * UC-12216 — con el MCP remoto, la UC activa queda marcada en el proyecto.
 *
 * start_uc devuelve `active_uc_marker`; el hook uc-state-marker lo escribe en .quality/active_uc.json.
 * complete_uc y release_uc lo borran si es de esa UC. Con el marcador, spec-guard deja de avisar
 * «código sin UC activa». Ejecutar: node --test tests/hooks/uc-state-marker.test.mjs
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { clearMarker, isError, markerFrom, topObject } from '../../.claude/hooks/lib/uc-state.mjs';

const repoRoot = resolve(fileURLToPath(import.meta.url), '../../..');
const HOOK = join(repoRoot, '.claude/hooks/uc-state-marker.mjs');
const SPEC_GUARD = join(repoRoot, '.claude/hooks/spec-guard.mjs');

const MARKER = {
  uc_id: 'UC-12216',
  board_id: 'EmbedBuild/specbox-manager',
  feature: 'UC-12216',
  us_id: 'US-122',
  started_at: '2026-11-18T10:00:00+00:00',
  reservation: { uc_id: 'UC-12216', developer_id: 'jesusperezdeveloper', reserved_at: '2026-11-18T10:00:00+00:00', backend: 'native' },
};

/** Lo que devuelve el MCP remoto, como contenido de texto de MCP. */
const remote = (body) => [{ type: 'text', text: JSON.stringify(body) }];

function project() {
  const dir = mkdtempSync(join(tmpdir(), 'uc-state-marker-'));
  spawnSync('git', ['init', '-q', '-b', 'feature/UC-12216-x'], { cwd: dir });
  mkdirSync(join(dir, '.claude'), { recursive: true });
  writeFileSync(join(dir, '.claude/project-config.json'), JSON.stringify({ boardId: 'EmbedBuild/specbox-manager', backend_type: 'native' }));
  return {
    dir,
    marker: () => (existsSync(join(dir, '.quality/active_uc.json')) ? JSON.parse(readFileSync(join(dir, '.quality/active_uc.json'), 'utf-8')) : null),
    done: () => rmSync(dir, { recursive: true, force: true }),
  };
}

function hook(p, tool, input, response) {
  const payload = { hook_event_name: 'PostToolUse', tool_name: `mcp__SpecBox-MCP__${tool}`, tool_input: input, tool_response: response, cwd: p.dir };
  const res = spawnSync(process.execPath, [HOOK], { cwd: p.dir, input: JSON.stringify(payload), encoding: 'utf8' });
  return { code: res.status, out: res.stdout, err: res.stderr };
}

test('start_uc con el MCP remoto deja el marcador con la UC, la historia y la reserva (AC-01)', () => {
  const p = project();
  try {
    const r = hook(p, 'start_uc', { board_id: 'EmbedBuild/specbox-manager', uc_id: 'UC-12216' },
      remote({ uc_id: 'UC-12216', status: 'in_progress', acceptance_criteria: [], active_uc_marker: MARKER }));
    assert.equal(r.code, 0);
    assert.equal(r.out, ''); // no escribe al agente
    assert.deepEqual(p.marker(), MARKER);
  } finally {
    p.done();
  }
});

test('complete_uc y release_uc borran el marcador de esa UC, no el de otra (AC-02)', () => {
  const p = project();
  try {
    hook(p, 'start_uc', { uc_id: 'UC-12216' }, remote({ active_uc_marker: MARKER }));
    hook(p, 'complete_uc', { uc_id: 'UC-99999' }, remote({ uc_id: 'UC-99999', completed_at: 'x' }));
    assert.equal(p.marker()?.uc_id, 'UC-12216'); // completar otra UC no lo toca
    hook(p, 'complete_uc', { uc_id: 'UC-12216' }, remote({ uc_id: 'UC-12216', completed_at: 'x', us_all_done: false }));
    assert.equal(p.marker(), null);

    hook(p, 'start_uc', { uc_id: 'UC-12216' }, remote({ active_uc_marker: MARKER }));
    hook(p, 'release_uc', { uc_id: 'UC-12216' }, { structuredContent: { success: true, uc_id: 'UC-12216' } });
    assert.equal(p.marker(), null);
  } finally {
    p.done();
  }
});

test('un error de la tool no escribe ni borra nada', () => {
  const p = project();
  try {
    hook(p, 'start_uc', { uc_id: 'UC-12216' }, remote({ error: 'UC-12216 ya está reservada', code: 'ALREADY_RESERVED' }));
    assert.equal(p.marker(), null);
    hook(p, 'start_uc', { uc_id: 'UC-12216' }, remote({ active_uc_marker: MARKER }));
    hook(p, 'complete_uc', { uc_id: 'UC-12216' }, remote({ error: 'Backend credentials not configured' }));
    assert.equal(p.marker()?.uc_id, 'UC-12216');
    hook(p, 'release_uc', { uc_id: 'UC-12216' }, { structuredContent: { success: false, code: 'NOT_OWNER' } });
    assert.equal(p.marker()?.uc_id, 'UC-12216');
  } finally {
    p.done();
  }
});

test('con el marcador escrito, spec-guard deja de avisar «código sin UC activa» (AC-03)', () => {
  const p = project();
  try {
    const write = (file) => spawnSync(process.execPath, [SPEC_GUARD], {
      cwd: p.dir,
      input: JSON.stringify({ hook_event_name: 'PostToolUse', tool_name: 'Write', tool_input: { file_path: join(p.dir, file) } }),
      encoding: 'utf8',
      env: { ...process.env, SPECBOX_ENGINE_MCP_URL: '', DEV_ENGINE_MCP_URL: '' },
    });
    const sin = write('src/app.ts');
    assert.match(`${sin.stdout}${sin.stderr}`, /código sin UC activa/);

    hook(p, 'start_uc', { uc_id: 'UC-12216' }, remote({ active_uc_marker: MARKER }));
    const con = write('src/app.ts');
    assert.equal(con.status, 0);
    assert.doesNotMatch(`${con.stdout}${con.stderr}`, /sin UC activa/);
  } finally {
    p.done();
  }
});

test('las piezas puras leen cualquier forma de respuesta del MCP (AC-04)', () => {
  assert.deepEqual(topObject({ structuredContent: { a: 1 } }), { a: 1 });
  assert.deepEqual(topObject(remote({ a: 2 })), { a: 2 });
  assert.deepEqual(topObject({ content: [{ type: 'text', text: '{"a":3}' }] }), { a: 3 });
  assert.equal(isError({ isError: true, content: [{ type: 'text', text: 'boom' }] }), true);
  assert.equal(isError(remote({ uc_id: 'UC-1', acceptance_criteria: [{ verdict: { error: 'anidado' } }] })), false);
  assert.equal(markerFrom(remote({ active_uc_marker: { uc_id: 'no-es-una-uc' } })), null);
  assert.equal(markerFrom(remote({ active_uc_marker: null })), null);
  const dir = mkdtempSync(join(tmpdir(), 'uc-state-'));
  try {
    assert.equal(clearMarker(dir, 'UC-1'), false); // no había nada
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
