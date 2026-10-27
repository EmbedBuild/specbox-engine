// UC-11101: freeform-path-guard decide si el MCP es remoto por la configuración de Claude Code,
// no solo por SPECBOX_ENGINE_MCP_URL (que solo escribe la extensión de VSCode).
//   node --test tests/hooks/freeform-path-guard.test.mjs

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync, execSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, existsSync, realpathSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const hook = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '.claude', 'hooks', 'freeform-path-guard.mjs');

const HTTP = { type: 'http', url: 'https://mcp.specbox.build/mcp' };
const BRIDGE = { command: 'npx', args: ['mcp-remote', 'https://mcp.specbox.build/mcp'] };
const LOCAL = { command: 'uv', args: ['run', 'python', '-m', 'server.server'] };

/** A git project and a HOME of its own; `claude` is ~/.claude.json, `mcp` the project .mcp.json. */
function setup({ claude = null, mcp = null } = {}) {
  const base = realpathSync(mkdtempSync(join(tmpdir(), 'ffguard-')));
  const home = join(base, 'home');
  const project = join(base, 'project');
  mkdirSync(home, { recursive: true });
  mkdirSync(project, { recursive: true });
  execSync('git init -q', { cwd: project });
  if (claude) writeFileSync(join(home, '.claude.json'), JSON.stringify(typeof claude === 'function' ? claude(project) : claude));
  if (mcp) writeFileSync(join(project, '.mcp.json'), JSON.stringify({ mcpServers: { 'SpecBox-MCP': mcp } }));
  return { home, project };
}

function setAuthToken({ home, project }, input = { api_key: 'freeform', token: '', backend_type: 'freeform', root_path: join(project, 'doc/tracking') }) {
  const env = { ...process.env, HOME: home };
  delete env.SPECBOX_ENGINE_MCP_URL;
  const res = spawnSync(process.execPath, [hook], {
    cwd: project,
    input: JSON.stringify({ hook_event_name: 'PreToolUse', tool_name: 'mcp__SpecBox-MCP__set_auth_token', tool_input: input, cwd: project }),
    encoding: 'utf8',
    env,
  });
  assert.equal(res.status, 0, res.stderr);
  const out = res.stdout.trim() ? JSON.parse(res.stdout).hookSpecificOutput.updatedInput : null;
  const logPath = join(project, '.quality/logs/freeform-path-rewrites.jsonl');
  const log = existsSync(logPath) ? readFileSync(logPath, 'utf8').trim().split('\n').map((l) => JSON.parse(l)) : [];
  return { input: out, log };
}

test('remoto por http en la configuración de usuario: set_auth_token sale sin root_path', () => {
  const { input, log } = setAuthToken(setup({ claude: { mcpServers: { 'SpecBox-MCP': HTTP } } }));
  assert.equal('root_path' in input, false);
  assert.equal(input.backend_type, 'freeform');
  assert.deepEqual(log.map((l) => [l.reason, l.to]), [['remote_content_only', null]]);
});

test('remoto por mcp-remote en el .mcp.json del proyecto: tampoco añade ruta', () => {
  const { input, log } = setAuthToken(setup({ mcp: BRIDGE }), { api_key: 'freeform', token: '', backend_type: 'freeform' });
  assert.equal('root_path' in input, false);
  assert.equal(log.filter((l) => l.to).length, 0, 'cero root_path añadidos');
});

test('remoto en la configuración local del proyecto (projects[<raíz>] de ~/.claude.json)', () => {
  const ctx = setup({ claude: (project) => ({ projects: { [project]: { mcpServers: { 'SpecBox-MCP': HTTP } } } }) });
  assert.equal('root_path' in setAuthToken(ctx).input, false);
});

test('MCP local: el guardián añade la ruta absoluta del tablero', () => {
  const ctx = setup({ mcp: LOCAL });
  const { input, log } = setAuthToken(ctx, { api_key: 'freeform', token: '', backend_type: 'freeform', root_path: 'doc/tracking' });
  assert.equal(input.root_path, join(ctx.project, 'doc/tracking'));
  assert.equal(log[0].is_remote_mcp, false);
});

test('la configuración local manda sobre la de usuario, como en Claude Code', () => {
  const ctx = setup({ claude: (project) => ({ mcpServers: { 'SpecBox-MCP': HTTP }, projects: { [project]: { mcpServers: { 'SpecBox-MCP': LOCAL } } } }) });
  const { input } = setAuthToken(ctx, { api_key: 'freeform', token: '', backend_type: 'freeform', root_path: 'doc/tracking' });
  assert.equal(input.root_path, join(ctx.project, 'doc/tracking'));
});

test('sin configuración ni variable: se comporta como MCP local (lo de siempre)', () => {
  const ctx = setup();
  const { input } = setAuthToken(ctx, { api_key: 'freeform', token: '', backend_type: 'freeform' });
  assert.equal(input.root_path, join(ctx.project, 'doc/tracking'));
});
