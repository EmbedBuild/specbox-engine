/**
 * UC-12206 — uc-lifecycle-guard deja de avisar en falso.
 *
 * Recorrido con los hooks reales y respuestas del MCP remoto: start_uc → mark_ac_batch → move_uc
 * pasan por uc-state-marker, que deja lo que el guard mira; el push de la rama de la UC queda en
 * silencio. Con criterios sin marcar o la UC fuera de revisión, el aviso dice qué falta.
 * Ejecutar: node --test tests/hooks/uc-lifecycle-guard.test.mjs
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = resolve(fileURLToPath(import.meta.url), '../../..');
const MARKER_HOOK = join(repoRoot, '.claude/hooks/uc-state-marker.mjs');
const GUARD = join(repoRoot, '.claude/hooks/uc-lifecycle-guard.mjs');

const remote = (body) => [{ type: 'text', text: JSON.stringify(body) }];
const START = remote({
  uc_id: 'UC-12206',
  status: 'in_progress',
  acceptance_criteria: [{ id: 'AC-01' }, { id: 'AC-02' }, { id: 'AC-03' }],
  active_uc_marker: { uc_id: 'UC-12206', board_id: 'EmbedBuild/specbox-manager', feature: 'UC-12206', us_id: 'US-122' },
});

function project(branch = 'feature/UC-12206-x') {
  const dir = mkdtempSync(join(tmpdir(), 'uc-lifecycle-'));
  spawnSync('git', ['init', '-q', '-b', branch], { cwd: dir });
  mkdirSync(join(dir, '.claude'), { recursive: true });
  writeFileSync(join(dir, '.claude/project-config.json'), JSON.stringify({ boardId: 'EmbedBuild/specbox-manager', backend_type: 'native' }));
  return { dir, done: () => rmSync(dir, { recursive: true, force: true }) };
}

function tool(p, name, input, response) {
  const payload = { hook_event_name: 'PostToolUse', tool_name: `mcp__SpecBox-MCP__${name}`, tool_input: input, tool_response: response, cwd: p.dir };
  return spawnSync(process.execPath, [MARKER_HOOK], { cwd: p.dir, input: JSON.stringify(payload), encoding: 'utf8' });
}

function push(p) {
  const payload = { hook_event_name: 'PostToolUse', tool_name: 'Bash', tool_input: { command: 'git push -u origin feature/UC-12206-x' }, cwd: p.dir };
  const res = spawnSync(process.execPath, [GUARD], { cwd: p.dir, input: JSON.stringify(payload), encoding: 'utf8' });
  return `${res.stdout}${res.stderr}`;
}

const batch = (results) => remote({ uc_id: 'UC-12206', total: results.length, details: results.map(([ac_id, passed]) => ({ ac_id, passed })) });

test('tras marcar los criterios y mover la UC a revisión, el push no avisa (AC-01)', () => {
  const p = project();
  try {
    tool(p, 'start_uc', { uc_id: 'UC-12206' }, START);
    tool(p, 'mark_ac_batch', { uc_id: 'UC-12206' }, batch([['AC-01', true], ['AC-02', true], ['AC-03', true]]));
    tool(p, 'move_uc', { uc_id: 'UC-12206', target: 'review' }, remote({ uc_id: 'UC-12206', new_status: 'review' }));
    assert.equal(push(p), '');
  } finally {
    p.done();
  }
});

test('con la UC en curso o criterios sin marcar, el aviso dice qué falta (AC-02)', () => {
  const p = project();
  try {
    tool(p, 'start_uc', { uc_id: 'UC-12206' }, START);
    let out = push(p);
    assert.match(out, /Criterios sin marcar: no consta ningún mark_ac_batch/);
    assert.match(out, /Faltan AC-01, AC-02, AC-03/);
    assert.match(out, /UC fuera de revisión: UC-12206/);

    // Dos lotes: los criterios se suman; el que falta se nombra.
    tool(p, 'mark_ac_batch', { uc_id: 'UC-12206' }, batch([['AC-01', true]]));
    tool(p, 'mark_ac_batch', { uc_id: 'UC-12206' }, batch([['AC-02', true]]));
    tool(p, 'move_uc', { uc_id: 'UC-12206', target: 'review' }, remote({ new_status: 'review' }));
    out = push(p);
    assert.match(out, /Criterios sin marcar como cumplidos: AC-03\./);
    assert.doesNotMatch(out, /fuera de revisión/);

    // Un criterio marcado como no cumplido también se nombra.
    tool(p, 'mark_ac_batch', { uc_id: 'UC-12206' }, batch([['AC-03', false]]));
    assert.match(push(p), /AC-03/);
    tool(p, 'mark_ac_batch', { uc_id: 'UC-12206' }, batch([['AC-03', true]]));
    assert.equal(push(p), '');

    // Volver a empezar la UC la saca de revisión.
    tool(p, 'start_uc', { uc_id: 'UC-12206' }, START);
    assert.match(push(p), /UC fuera de revisión/);
  } finally {
    p.done();
  }
});

test('una respuesta de error del MCP no cuenta como marcado ni como movido (AC-03)', () => {
  const p = project();
  try {
    tool(p, 'start_uc', { uc_id: 'UC-12206' }, START);
    tool(p, 'mark_ac_batch', { uc_id: 'UC-12206' }, remote({ error: 'Backend credentials not configured' }));
    tool(p, 'move_uc', { uc_id: 'UC-12206', target: 'review' }, remote({ error: 'Backend credentials not configured' }));
    const out = push(p);
    assert.match(out, /Criterios sin marcar/);
    assert.match(out, /UC fuera de revisión/);
  } finally {
    p.done();
  }
});

test('UC-12701: una rama fix/ de /fix recibe el mismo aviso; otra rama no', () => {
  for (const [branch, warns] of [['fix/UC-12206-total-a-cero', true], ['chore/limpieza', false]]) {
    const p = project(branch);
    try {
      tool(p, 'start_uc', { uc_id: 'UC-12206' }, START);
      const out = push(p);
      if (warns) assert.match(out, /Criterios sin marcar/, branch);
      else assert.equal(out, '', branch);
    } finally {
      p.done();
    }
  }
});
