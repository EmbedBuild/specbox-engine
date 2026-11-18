/**
 * UC-12217 — spec-guard revisa la reserva con el tablero de verdad.
 *
 * spec-guard real contra un MCP falso en local (initialize + tools/call de get_uc_reservation) y
 * una credencial de dispositivo falsa (SPECBOX_HOME/bin/mcp-headers.mjs):
 * - reserva liberada → bloqueo que pide volver a llamar a start_uc (AC-01);
 * - reserva de otra persona → bloqueo que dice quién la tiene (AC-02);
 * - sin red → se usa la reserva guardada y la nota lo dice, una vez cada 10 minutos (AC-03);
 * - la llamada es a la tool con la identidad del dispositivo (AC-04).
 * Ejecutar: node --test tests/hooks/spec-guard-reservation.test.mjs
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { spawnSync } from 'node:child_process';
import { createServer } from 'node:http';
import { existsSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = resolve(fileURLToPath(import.meta.url), '../../..');
const SPEC_GUARD = join(repoRoot, '.claude/hooks/spec-guard.mjs');
const ME = 'jesusperezdeveloper';

/** Un MCP falso que contesta get_uc_reservation con `reservation` y apunta lo que le piden. */
function fakeMcp(reservation) {
  const calls = [];
  const server = createServer((req, res) => {
    let body = '';
    req.on('data', (c) => { body += c; });
    req.on('end', () => {
      const msg = JSON.parse(body || '{}');
      calls.push({ method: msg.method, params: msg.params, auth: req.headers.authorization });
      res.setHeader('content-type', 'application/json');
      res.setHeader('mcp-session-id', 's-1');
      if (msg.method === 'initialize') return res.end(JSON.stringify({ jsonrpc: '2.0', id: 1, result: {} }));
      if (msg.method === 'notifications/initialized') { res.statusCode = 202; return res.end(''); }
      const result = { success: true, project_id: msg.params.arguments.project_id, uc_id: msg.params.arguments.uc_id, reservation };
      return res.end(JSON.stringify({ jsonrpc: '2.0', id: 2, result: { structuredContent: result } }));
    });
  });
  return new Promise((ok) => server.listen(0, '127.0.0.1', () => ok({ server, calls, url: `http://127.0.0.1:${server.address().port}/mcp` })));
}

function project() {
  const dir = mkdtempSync(join(tmpdir(), 'spec-guard-res-'));
  spawnSync('git', ['init', '-q', '-b', 'feature/UC-12217-x'], { cwd: dir });
  mkdirSync(join(dir, '.claude'), { recursive: true });
  mkdirSync(join(dir, '.quality'), { recursive: true });
  writeFileSync(join(dir, '.claude/project-config.json'), JSON.stringify({ boardId: 'EmbedBuild/specbox-manager', backend_type: 'native' }));
  writeFileSync(join(dir, '.quality/active_uc.json'), JSON.stringify({
    uc_id: 'UC-12217', board_id: 'EmbedBuild/specbox-manager', feature: 'UC-12217',
    reservation: { uc_id: 'UC-12217', developer_id: ME, reserved_at: '2026-11-18T10:00:00+00:00', backend: 'native' },
  }));
  // Credencial de dispositivo falsa: el ayudante que instala la CLI de SpecBox.
  const home = join(dir, 'specbox-home');
  mkdirSync(join(home, 'bin'), { recursive: true });
  writeFileSync(join(home, 'bin/mcp-headers.mjs'), "export async function headersFor() { return { Authorization: 'Bearer token-de-prueba' }; }\n");
  return { dir, home, done: () => rmSync(dir, { recursive: true, force: true }) };
}

/** spec-guard tras escribir src/app.ts, sin bloquear el bucle de eventos (el MCP falso vive aquí). */
function write(p, url) {
  return new Promise((ok) => {
    const child = spawn(process.execPath, [SPEC_GUARD], {
      cwd: p.dir,
      env: { ...process.env, SPECBOX_HOME: p.home, SPECBOX_MCP_URL: url, SPECBOX_ENGINE_MCP_URL: '', SPECBOX_RESERVATION_CHECK: '' },
    });
    let out = '';
    child.stdout.on('data', (d) => { out += d; });
    child.stderr.on('data', (d) => { out += d; });
    child.on('close', (code) => ok({ code, out }));
    child.stdin.end(JSON.stringify({ hook_event_name: 'PostToolUse', tool_name: 'Write', tool_input: { file_path: join(p.dir, 'src/app.ts') } }));
  });
}

test('reserva liberada en el tablero: bloqueo que pide volver a llamar a start_uc (AC-01, AC-04)', async () => {
  const p = project();
  const mcp = await fakeMcp(null);
  try {
    const r = await write(p, mcp.url);
    assert.equal(r.code, 2);
    assert.match(r.out, /la reserva de la UC ya no es tuya/);
    assert.match(r.out, /Vuelve a llamar a start_uc/);
    const call = mcp.calls.find((c) => c.method === 'tools/call');
    assert.deepEqual(call.params, { name: 'get_uc_reservation', arguments: { uc_id: 'UC-12217', project_id: 'EmbedBuild/specbox-manager' } });
    assert.equal(call.auth, 'Bearer token-de-prueba'); // la identidad del dispositivo
  } finally {
    mcp.server.close();
    p.done();
  }
});

test('reserva de otra persona: el bloqueo dice quién la tiene (AC-02)', async () => {
  const p = project();
  const mcp = await fakeMcp({ uc_id: 'UC-12217', developer_id: 'ana-garcia', reserved_at: '2026-11-18T11:00:00+00:00', branch: '' });
  try {
    const r = await write(p, mcp.url);
    assert.equal(r.code, 2);
    assert.match(r.out, /Ahora la tiene 'ana-garcia'/);
  } finally {
    mcp.server.close();
    p.done();
  }
});

test('reserva confirmada: silencio, y no vuelve a preguntar en 60 s', async () => {
  const p = project();
  const mcp = await fakeMcp({ uc_id: 'UC-12217', developer_id: ME, reserved_at: '2026-11-18T10:00:00+00:00', branch: '' });
  try {
    const first = await write(p, mcp.url);
    assert.equal(first.code, 0);
    assert.equal(first.out, '');
    const calls = mcp.calls.filter((c) => c.method === 'tools/call').length;
    const second = await write(p, mcp.url);
    assert.equal(second.code, 0);
    assert.equal(mcp.calls.filter((c) => c.method === 'tools/call').length, calls); // caché
  } finally {
    mcp.server.close();
    p.done();
  }
});

test('sin red: usa la reserva guardada y la nota lo indica una vez cada 10 minutos (AC-03)', async () => {
  const p = project();
  try {
    const nowhere = 'http://127.0.0.1:9/mcp'; // nadie escucha
    const first = await write(p, nowhere);
    assert.equal(first.code, 0);
    assert.match(first.out, /reserva sin comprobar con el tablero/);
    assert.match(first.out, /Se usa la reserva guardada/);
    const second = await write(p, nowhere);
    assert.equal(second.code, 0);
    assert.equal(second.out, '');
    assert.ok(existsSync(join(p.dir, '.quality/reservation_check.json')));
  } finally {
    p.done();
  }
});
