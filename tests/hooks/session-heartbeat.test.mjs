/**
 * US-99 · UC-9901: el latido de la sesión al board.
 *
 * - AC-01: el latido sale al empezar, al cambiar de UC, fase o espera y como mucho cada dos
 *   minutos; pesa menos de 1 KB y solo lleva campos enumerados (nunca texto de la conversación).
 * - AC-02: al cerrar la sesión el latido dice que ha terminado.
 * - AC-03: el hook nunca bloquea ni habla; si el board no responde, el fallo se anota en local
 *   como mucho una vez por minuto.
 *
 * Ejecutar: node --test tests/hooks/session-heartbeat.test.mjs
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { INTERVALO_MS, esperaTras, faseActual, latido, tocaEnviar, ucActiva } from '../../.claude/hooks/lib/heartbeat.mjs';
import { llamarTool, mensajeDe } from '../../.claude/hooks/lib/mcp-client.mjs';
import { anotarFallo, enviarLatido } from '../../.claude/hooks/lib/heartbeat-send.mjs';

const repoRoot = resolve(fileURLToPath(import.meta.url), '../../..');
const hook = join(repoRoot, '.claude/hooks/session-heartbeat.mjs');
const SESION = '3f2c9a1e-7b44-4d2a-9c11-0a5b6e7d8f90';

// ── Qué dice el latido ─────────────────────────────────────────────────

test('la UC sale del marcador o, si no, de la rama feature/UC-…', () => {
  assert.equal(ucActiva({ marcador: { uc_id: 'UC-9901' }, rama: 'main' }), 'UC-9901');
  assert.equal(ucActiva({ rama: 'feature/UC-9803-detalle-proyecto-y-uc' }), 'UC-9803');
  assert.equal(ucActiva({ rama: 'feature/uc-4b-algo' }), 'UC-4b');
  assert.equal(ucActiva({ rama: 'main' }), null);
  assert.equal(ucActiva({ marcador: { uc_id: 'UC-9901: con texto' }, rama: 'main' }), null);
});

test('la fase sale del pipeline, del checkpoint reciente o de si hay UC', () => {
  assert.equal(faseActual({ pipeline: { current_phase: 'design_to_code' } }), 'design');
  assert.equal(faseActual({ pipeline: { current_phase: 'tests' } }), 'tests');
  assert.equal(faseActual({ checkpoint: { phase_name: 'UC-9803 ronda de corrección de diseño' }, checkpointEdadS: 60 }), 'design');
  assert.equal(faseActual({ checkpoint: { phase_name: 'Phase 6 (UC-9705 TestFlight, Play y CI local)' }, checkpointEdadS: 60 }), 'implement');
  assert.equal(faseActual({ checkpoint: { phase_name: 'plan de US-99' }, checkpointEdadS: 10 * 3600, uc: null }), 'idle');
  assert.equal(faseActual({ uc: 'UC-1' }), 'implement');
});

test('la espera: permiso, decisión o nada según el evento', () => {
  assert.equal(esperaTras('Notification', { notification_type: 'permission_prompt' }), 'permission');
  assert.equal(esperaTras('Notification', { message: 'Claude needs your permission to use Bash' }), 'permission');
  assert.equal(esperaTras('Notification', { notification_type: 'idle_prompt' }), 'decision');
  assert.equal(esperaTras('UserPromptSubmit', {}, 'permission'), 'none');
  assert.equal(esperaTras('PostToolUse', {}, 'permission'), 'none');
  assert.equal(esperaTras('Stop', {}, 'decision'), 'decision');
});

test('el latido solo lleva campos enumerados y pesa menos de 1 KB, aunque la notificación traiga texto', () => {
  const l = latido({
    evento: 'Notification',
    entrada: { session_id: SESION, message: 'Claude needs your permission to run: rm -rf secreto con datos del cliente '.repeat(40) },
    proyecto: 'EmbedBuild/specbox-manager',
    rama: 'feature/UC-9901-latido-de-sesion',
  });
  assert.deepEqual(Object.keys(l).sort(), ['ended', 'phase', 'project_id', 'session_id', 'uc_id', 'waiting']);
  assert.equal(l.waiting, 'permission');
  assert.ok(Buffer.byteLength(JSON.stringify(l)) < 1024);
  assert.ok(!JSON.stringify(l).includes('secreto'));
});

test('sin sesión o sin board native no hay latido', () => {
  assert.equal(latido({ evento: 'SessionStart', entrada: {}, proyecto: 'EmbedBuild/x' }), null);
  assert.equal(latido({ evento: 'SessionStart', entrada: { session_id: SESION }, proyecto: '' }), null);
});

test('se manda al empezar, al cerrar, al cambiar algo o a los dos minutos', () => {
  const base = latido({ evento: 'PostToolUse', entrada: { session_id: SESION }, proyecto: 'A/b', rama: 'feature/UC-1-x' });
  const t0 = 1_000_000;
  assert.equal(tocaEnviar(base, null, t0), true, 'primera vez');
  const enviado = { ...base, sent_at: t0 };
  assert.equal(tocaEnviar(base, enviado, t0 + 60_000), false, 'sin cambios y antes de dos minutos');
  assert.equal(tocaEnviar(base, enviado, t0 + INTERVALO_MS), true, 'a los dos minutos');
  assert.equal(tocaEnviar({ ...base, phase: 'tests' }, enviado, t0 + 1000), true, 'cambio de fase');
  assert.equal(tocaEnviar({ ...base, waiting: 'permission' }, enviado, t0 + 1000), true, 'empieza a esperar');
  assert.equal(tocaEnviar({ ...base, ended: true }, enviado, t0 + 1000), true, 'al cerrar');
  assert.equal(INTERVALO_MS, 120_000);
});

// ── El hook ────────────────────────────────────────────────────────────

function repo({ native = true } = {}) {
  const dir = mkdtempSync(join(tmpdir(), 'heartbeat-'));
  spawnSync('git', ['init', '-q', '-b', 'feature/UC-9901-latido'], { cwd: dir });
  mkdirSync(join(dir, '.claude'), { recursive: true });
  if (native) writeFileSync(join(dir, '.claude/project-config.json'), JSON.stringify({ boardId: 'EmbedBuild/demo', backend_type: 'native' }));
  return dir;
}

function correr(dir, entrada, env = {}) {
  const t0 = Date.now();
  const r = spawnSync(process.execPath, [hook], {
    cwd: dir,
    input: JSON.stringify(entrada),
    encoding: 'utf8',
    env: { ...process.env, SPECBOX_HEARTBEAT_DRY_RUN: join(dir, 'enviados.jsonl'), ...env },
  });
  return { ...r, ms: Date.now() - t0 };
}

const enviados = (dir) =>
  existsSync(join(dir, 'enviados.jsonl'))
    ? readFileSync(join(dir, 'enviados.jsonl'), 'utf8').trim().split('\n').filter(Boolean).map((l) => JSON.parse(l))
    : [];

test('el hook calla, sale con 0 y manda solo cuando toca; al cerrar dice que ha terminado', () => {
  const dir = repo();
  try {
    const a = correr(dir, { hook_event_name: 'SessionStart', session_id: SESION });
    assert.equal(a.status, 0);
    assert.equal(a.stdout, '');
    assert.equal(a.stderr, '');
    correr(dir, { hook_event_name: 'PostToolUse', session_id: SESION, tool_name: 'Read' });
    correr(dir, { hook_event_name: 'Notification', session_id: SESION, notification_type: 'permission_prompt' });
    correr(dir, { hook_event_name: 'SessionEnd', session_id: SESION, reason: 'exit' });
    const lista = enviados(dir);
    assert.deepEqual(lista.map((l) => [l.uc_id, l.waiting, l.ended]), [
      ['UC-9901', 'none', false],
      ['UC-9901', 'permission', false],
      ['UC-9901', 'none', true],
    ]);
    assert.equal(lista[0].project_id, 'EmbedBuild/demo');
    const ignorados = readFileSync(join(dir, '.quality/.gitignore'), 'utf8');
    for (const l of ['heartbeat_state.json', 'heartbeat_error.json', 'logs/heartbeat.log']) assert.ok(ignorados.includes(l), l);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test('sin board native, o apagado, no hace nada', () => {
  const dir = repo({ native: false });
  const otro = repo();
  try {
    correr(dir, { hook_event_name: 'SessionStart', session_id: SESION });
    assert.equal(enviados(dir).length, 0);
    correr(otro, { hook_event_name: 'SessionStart', session_id: SESION }, { SPECBOX_HEARTBEAT: 'off' });
    assert.equal(enviados(otro).length, 0);
  } finally {
    rmSync(dir, { recursive: true, force: true });
    rmSync(otro, { recursive: true, force: true });
  }
});

test('el hook no espera al envío: vuelve enseguida aunque el board no responda', () => {
  const dir = repo();
  try {
    // Sin DRY_RUN: lanza el envío de verdad contra un puerto cerrado y no lo espera.
    const r = correr(dir, { hook_event_name: 'SessionStart', session_id: SESION }, { SPECBOX_HEARTBEAT_DRY_RUN: '', SPECBOX_MCP_URL: 'http://127.0.0.1:9/mcp' });
    assert.equal(r.status, 0);
    assert.ok(r.ms < 1500, `tardó ${r.ms} ms`);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

// ── El envío ───────────────────────────────────────────────────────────

test('un fallo se anota como mucho una vez por minuto (AC-03)', () => {
  const dir = mkdtempSync(join(tmpdir(), 'heartbeat-log-'));
  try {
    assert.equal(anotarFallo(dir, 'el board no responde', 1_000_000), true);
    assert.equal(anotarFallo(dir, 'el board no responde', 1_030_000), false);
    assert.equal(anotarFallo(dir, 'el board no responde', 1_061_000), true);
    const lineas = readFileSync(join(dir, '.quality/logs/heartbeat.log'), 'utf8').trim().split('\n');
    assert.equal(lineas.length, 2);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test('enviarLatido no lanza: sin credencial o con el board caído, anota y devuelve false', async () => {
  const dir = mkdtempSync(join(tmpdir(), 'heartbeat-send-'));
  try {
    const l = { project_id: 'A/b', session_id: SESION, uc_id: null, phase: 'idle', waiting: 'none', ended: false };
    assert.equal(await enviarLatido({ raiz: dir, latido: l, cabeceras: {} }), false);
    const caido = async () => {
      throw new TypeError('fetch failed');
    };
    assert.equal(await enviarLatido({ raiz: dir, latido: l, cabeceras: { Authorization: 'Bearer x' }, fetchImpl: caido, ahora: () => Date.now() + 120_000 }), false);
    const registro = readFileSync(join(dir, '.quality/logs/heartbeat.log'), 'utf8');
    assert.ok(registro.includes('latido no enviado'));
    assert.ok(!registro.includes('Bearer'), 'la credencial nunca va al registro');
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

// ── El cliente MCP ─────────────────────────────────────────────────────

function servidorFalso(respuestaTool) {
  const llamadas = [];
  const fetchImpl = async (url, opts) => {
    const cuerpo = JSON.parse(opts.body);
    llamadas.push({ metodo: cuerpo.method, sesion: opts.headers['mcp-session-id'] ?? null, auth: opts.headers.Authorization });
    const cabeceras = new Map([['mcp-session-id', 'sesion-1'], ['content-type', 'text/event-stream']]);
    const res = (status, texto) => ({ status, headers: { get: (k) => cabeceras.get(k) ?? null }, text: async () => texto });
    if (cuerpo.method === 'initialize') return res(200, `event: message\ndata: ${JSON.stringify({ jsonrpc: '2.0', id: 1, result: { protocolVersion: '2025-06-18' } })}\n\n`);
    if (cuerpo.method === 'notifications/initialized') return res(202, '');
    return res(200, `data: ${JSON.stringify({ jsonrpc: '2.0', id: 2, result: { content: [{ type: 'text', text: JSON.stringify(respuestaTool) }] } })}\n\n`);
  };
  return { fetchImpl, llamadas };
}

test('el cliente MCP inicializa, llama a la tool con la sesión y lee la respuesta SSE', async () => {
  const { fetchImpl, llamadas } = servidorFalso({ success: true, state: 'live' });
  const r = await llamarTool({ url: 'https://mcp.test/mcp', cabeceras: { Authorization: 'Bearer t' }, nombre: 'report_session_heartbeat', args: {}, fetchImpl });
  assert.deepEqual(r, { success: true, state: 'live' });
  assert.deepEqual(llamadas.map((l) => [l.metodo, l.sesion]), [
    ['initialize', null],
    ['notifications/initialized', 'sesion-1'],
    ['tools/call', 'sesion-1'],
  ]);
  assert.ok(llamadas.every((l) => l.auth === 'Bearer t'));
  assert.equal(mensajeDe('{"id":1,"result":{}}', 'application/json', 1).id, 1);
});

test('el cliente MCP corta a los 3 s', async () => {
  const colgado = (_url, opts) => new Promise((_, rechazar) => opts.signal.addEventListener('abort', () => rechazar(Object.assign(new Error('x'), { name: 'AbortError' }))));
  await assert.rejects(llamarTool({ url: 'https://mcp.test/mcp', nombre: 'x', fetchImpl: colgado, topeMs: 50 }), /tope de 50 ms/);
});
