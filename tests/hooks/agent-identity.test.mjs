/**
 * UC-12402 — el contexto de Claude Code que llama queda en la llamada (hook agent-identity).
 *
 * - start_uc y record_review_verdict reciben `client_session_id`, `client_agent_id` y
 *   `client_agent_type` de la entrada del hook; lo que mande el modelo se sustituye.
 * - Otras tools, una entrada sin sesión o FreeForm con el MCP remoto (lo hace freeform-fragment): calla.
 * Ejecutar: node --test tests/hooks/agent-identity.test.mjs
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { identityFields, withIdentity } from '../../.claude/hooks/lib/agent-identity.mjs';

const repoRoot = resolve(fileURLToPath(import.meta.url), '../../..');
const HOOK = join(repoRoot, '.claude/hooks/agent-identity.mjs');

function project(settings = { specbox: { backend_type: 'native' } }) {
  const dir = mkdtempSync(join(tmpdir(), 'agent-identity-'));
  spawnSync('git', ['init', '-q'], { cwd: dir });
  mkdirSync(join(dir, '.claude'), { recursive: true });
  writeFileSync(join(dir, '.claude/settings.local.json'), JSON.stringify(settings));
  return dir;
}

function call(dir, tool, input, extra = {}, env = {}) {
  const payload = { hook_event_name: 'PreToolUse', tool_name: `mcp__SpecBox-MCP__${tool}`, tool_input: input, cwd: dir, ...extra };
  const r = spawnSync(process.execPath, [HOOK], { cwd: dir, input: JSON.stringify(payload), encoding: 'utf8', env: { ...process.env, ...env } });
  let out = null;
  try { out = r.stdout ? JSON.parse(r.stdout) : null; } catch { /* nada */ }
  return { code: r.status, stderr: r.stderr, out };
}

test('start_uc y record_review_verdict llevan la sesión y el agente de la entrada del hook', () => {
  const dir = project();
  try {
    const r = call(dir, 'record_review_verdict', { board_id: 'b', uc_id: 'UC-1', verdict: 'accepted', client_agent_id: 'inventado' },
      { session_id: 'sess-1', agent_id: 'agent-9', agent_type: 'general-purpose' });
    assert.equal(r.code, 0, r.stderr);
    assert.deepEqual(r.out.hookSpecificOutput.updatedInput, {
      board_id: 'b', uc_id: 'UC-1', verdict: 'accepted',
      client_session_id: 'sess-1', client_agent_id: 'agent-9', client_agent_type: 'general-purpose',
    });
    const main = call(dir, 'start_uc', { board_id: 'b', uc_id: 'UC-1', client_agent_id: 'otro' }, { session_id: 'sess-1' });
    assert.deepEqual(main.out.hookSpecificOutput.updatedInput, { board_id: 'b', uc_id: 'UC-1', client_session_id: 'sess-1' });
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test('calla con otras tools, sin sesión y en FreeForm con el MCP remoto', () => {
  const dir = project();
  const ff = project({ specbox: { backend_type: 'freeform' } });
  try {
    for (const r of [
      call(dir, 'mark_ac', { board_id: 'b' }, { session_id: 's' }),
      call(dir, 'start_uc', { board_id: 'b' }, {}),
      call(ff, 'start_uc', { board_id: 'b' }, { session_id: 's' }, { SPECBOX_ENGINE_MCP_URL: 'https://mcp.example.test/mcp' }),
    ]) {
      assert.equal(r.code, 0, r.stderr);
      assert.equal(r.out, null);
    }
  } finally {
    rmSync(dir, { recursive: true, force: true });
    rmSync(ff, { recursive: true, force: true });
  }
});

test('solo identificadores cortos: un valor raro no pasa', () => {
  assert.deepEqual(identityFields({ session_id: 'a b', agent_id: 'x'.repeat(200), agent_type: 'Explore' }), { client_agent_type: 'Explore' });
  assert.deepEqual(withIdentity({ uc_id: 'UC-1', client_session_id: 'del modelo' }, {}), { uc_id: 'UC-1' });
});
