/**
 * US-124 · UC-12403: el coste real de cada UC en tokens, del uso que informa Claude Code.
 *
 * - AC-01: el hook suma `message.usage` de la transcripción (cada respuesta una vez, solo lo nuevo
 *   y solo desde que empezó la UC) y lo manda a la UC activa; también la de cada subagente.
 * - AC-03: si el formato no se reconoce, no manda nada (la UC queda «estimado»).
 * - AC-04: lo que sale son identificadores y cifras, nunca texto de la conversación.
 * El hook nunca bloquea ni habla.
 *
 * Ejecutar: node --test tests/hooks/uc-usage.test.mjs
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { appendFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { CAMPOS, informe, leerDesde, rutaCursor, sumarUso, transcriptDe } from '../../.claude/hooks/lib/uc-usage.mjs';
import { enviarUso } from '../../.claude/hooks/lib/uc-usage-send.mjs';

const repoRoot = resolve(fileURLToPath(import.meta.url), '../../..');
const hook = join(repoRoot, '.claude/hooks/uc-usage.mjs');
const SESION = '3f2c9a1e-7b44-4d2a-9c11-0a5b6e7d8f90';
const SECRETO = 'texto privado de la conversación con datos del cliente';

const uso = (input, output, cacheW = 0, cacheR = 0) => ({
  input_tokens: input,
  output_tokens: output,
  cache_creation_input_tokens: cacheW,
  cache_read_input_tokens: cacheR,
});
const linea = (id, u, extra = {}) =>
  JSON.stringify({
    type: 'assistant',
    timestamp: '2026-11-19T10:00:00.000Z',
    message: { id, role: 'assistant', content: [{ type: 'text', text: SECRETO }], usage: u },
    ...extra,
  });

// ── La suma ────────────────────────────────────────────────────────────

test('AC-01 · cada respuesta cuenta una vez, con su último uso; las ya contadas no vuelven', () => {
  const lineas = [
    linea('msg_1', uso(10, 1)),
    linea('msg_1', uso(10, 40, 5, 100)), // la misma respuesta en otra línea, con el uso final
    linea('msg_2', uso(3, 7)),
    JSON.stringify({ type: 'user', message: { role: 'user', content: SECRETO } }),
    'no es json',
    '',
  ];
  const r = sumarUso(lineas);
  assert.deepEqual(
    { ...Object.fromEntries(CAMPOS.map((c) => [c, r[c]])), messages: r.messages },
    { input_tokens: 13, output_tokens: 47, cache_creation_input_tokens: 5, cache_read_input_tokens: 100, messages: 2 },
  );
  assert.deepEqual(r.ids, ['msg_1', 'msg_2']);
  const otra = sumarUso([linea('msg_2', uso(3, 7)), linea('msg_3', uso(1, 1))], ['msg_1', 'msg_2']);
  assert.equal(otra.messages, 1);
  assert.equal(otra.input_tokens, 1);
});

test('AC-01 · en la transcripción principal no cuentan las líneas de subagentes ni lo anterior a la UC', () => {
  const lineas = [
    linea('msg_side', uso(50, 50), { isSidechain: true }),
    linea('msg_viejo', uso(80, 80), { timestamp: '2026-11-19T09:00:00.000Z' }),
    linea('msg_nuevo', uso(2, 3)),
  ];
  const r = sumarUso(lineas, [], { principal: true, desde: '2026-11-19T09:30:00.000+00:00' });
  assert.deepEqual(r.ids, ['msg_nuevo']);
  assert.equal(r.input_tokens + r.output_tokens, 5);
  // En la de un subagente sí cuentan sus propias líneas.
  assert.equal(sumarUso(lineas.slice(0, 1)).messages, 1);
});

test('AC-03 · un formato que no se reconoce no da ninguna cifra', () => {
  const r = sumarUso([JSON.stringify({ type: 'assistant', message: { content: SECRETO, tokens: 10 } }), JSON.stringify({ usage: uso(1, 1) })]);
  assert.equal(r.messages, 0);
  assert.equal(r.input_tokens + r.output_tokens, 0);
});

test('AC-04 · el informe solo lleva identificadores y cifras', () => {
  const r = sumarUso([linea('msg_1', uso(10, 20, 3, 4))]);
  const datos = informe({ proyecto: 'EmbedBuild/demo', uc: 'UC-12403', sesion: SESION, agente: '', uso: r });
  assert.deepEqual(Object.keys(datos).sort(), [
    'agent_id', 'cache_creation_input_tokens', 'cache_read_input_tokens', 'input_tokens', 'messages', 'output_tokens',
    'project_id', 'session_id', 'uc_id',
  ]);
  assert.ok(!JSON.stringify(datos).includes('privado'));
  for (const c of [...CAMPOS, 'messages']) assert.equal(typeof datos[c], 'number');
});

test('la transcripción: la de la sesión, o la del subagente (dada o en <sesión>/subagents/)', () => {
  assert.deepEqual(transcriptDe({ transcript_path: '/t/s.jsonl', session_id: SESION }), { ruta: '/t/s.jsonl', agente: '', principal: true });
  assert.deepEqual(transcriptDe({ transcript_path: '/t/s.jsonl', session_id: SESION, agent_id: 'a1b2', agent_transcript_path: '/t/a.jsonl' }), {
    ruta: '/t/a.jsonl', agente: 'a1b2', principal: false,
  });
  assert.equal(transcriptDe({ transcript_path: '/t/s.jsonl', session_id: SESION, agent_id: 'a1b2' }).ruta, join('/t', SESION, 'subagents', 'agent-a1b2.jsonl'));
  assert.equal(transcriptDe({ agent_id: 'a1b2' }), null);
  assert.equal(transcriptDe({}), null);
});

test('leer desde el cursor: solo líneas completas, en bytes, y desde el principio si el fichero encogió', () => {
  const dir = mkdtempSync(join(tmpdir(), 'uc-usage-leer-'));
  try {
    const f = join(dir, 't.jsonl');
    writeFileSync(f, `${linea('msg_ñ', uso(1, 1))}\n{"a medias`);
    const a = leerDesde(f, 0);
    assert.equal(a.lineas.length, 1);
    appendFileSync(f, '"}\n');
    const b = leerDesde(f, a.offset);
    assert.deepEqual(b.lineas, ['{"a medias"}']);
    assert.equal(leerDesde(f, b.offset).lineas.length, 0);
    assert.equal(leerDesde(f, 10_000_000).lineas.length, 2);
    // Con más atraso que el tope, solo la cola y desde un principio de línea.
    const cola = leerDesde(f, 0, 20);
    assert.ok(cola.lineas.every((l) => l === '' || l.startsWith('{')));
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

// ── El hook ────────────────────────────────────────────────────────────

function repo({ native = true, uc = 'UC-12403', startedAt = '2026-11-19T09:30:00.000+00:00' } = {}) {
  const dir = mkdtempSync(join(tmpdir(), 'uc-usage-'));
  spawnSync('git', ['init', '-q', '-b', 'feature/UC-12403-coste'], { cwd: dir });
  mkdirSync(join(dir, '.claude'), { recursive: true });
  mkdirSync(join(dir, '.quality'), { recursive: true });
  if (native) writeFileSync(join(dir, '.claude/project-config.json'), JSON.stringify({ boardId: 'EmbedBuild/demo', backend_type: 'native' }));
  if (uc) writeFileSync(join(dir, '.quality/active_uc.json'), JSON.stringify({ uc_id: uc, started_at: startedAt }));
  return dir;
}

function correr(dir, entrada, env = {}) {
  return spawnSync(process.execPath, [hook], {
    cwd: dir,
    input: JSON.stringify(entrada),
    encoding: 'utf8',
    env: { ...process.env, SPECBOX_UC_USAGE_DRY_RUN: join(dir, 'enviados.jsonl'), ...env },
  });
}

const enviados = (dir) =>
  existsSync(join(dir, 'enviados.jsonl'))
    ? readFileSync(join(dir, 'enviados.jsonl'), 'utf8').trim().split('\n').filter(Boolean).map((l) => JSON.parse(l))
    : [];

test('AC-01 · al terminar cada turno manda solo lo nuevo, calla y sale con 0', () => {
  const dir = repo();
  try {
    const t = join(dir, 'sesion.jsonl');
    writeFileSync(t, `${linea('msg_viejo', uso(500, 500), { timestamp: '2026-11-19T08:00:00.000Z' })}\n${linea('msg_1', uso(10, 20, 30, 40))}\n`);
    const entrada = { hook_event_name: 'Stop', session_id: SESION, transcript_path: t };
    const a = correr(dir, entrada);
    assert.equal(a.status, 0);
    assert.equal(a.stdout, '');
    assert.equal(a.stderr, '');
    assert.deepEqual(enviados(dir), [{
      project_id: 'EmbedBuild/demo', uc_id: 'UC-12403', session_id: SESION, agent_id: '',
      input_tokens: 10, output_tokens: 20, cache_creation_input_tokens: 30, cache_read_input_tokens: 40, messages: 1,
    }]);
    // Otro turno sin nada nuevo no manda nada; con una respuesta nueva, solo esa.
    correr(dir, entrada);
    assert.equal(enviados(dir).length, 1);
    appendFileSync(t, `${linea('msg_1', uso(10, 20, 30, 40))}\n${linea('msg_2', uso(1, 2))}\n`);
    correr(dir, entrada);
    assert.equal(enviados(dir).length, 2);
    assert.equal(enviados(dir)[1].messages, 1);
    assert.equal(enviados(dir)[1].output_tokens, 2);
    assert.match(readFileSync(join(dir, '.quality/.gitignore'), 'utf8'), /uc_usage\//);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test('AC-01 · cada subagente manda lo suyo, con su id; antes de complete_uc, solo para la UC activa', () => {
  const dir = repo();
  try {
    const t = join(dir, 'sesion.jsonl');
    writeFileSync(t, '');
    const sub = join(dir, SESION, 'subagents', 'agent-ab12.jsonl');
    mkdirSync(join(dir, SESION, 'subagents'), { recursive: true });
    writeFileSync(sub, `${linea('msg_s', uso(7, 8))}\n`);
    correr(dir, { hook_event_name: 'SubagentStop', session_id: SESION, transcript_path: t, agent_id: 'ab12' });
    assert.deepEqual(enviados(dir).map((e) => [e.agent_id, e.input_tokens]), [['ab12', 7]]);

    appendFileSync(t, `${linea('msg_m', uso(4, 4))}\n`);
    correr(dir, { hook_event_name: 'PreToolUse', tool_name: 'mcp__SpecBox-MCP__complete_uc', session_id: SESION, transcript_path: t, tool_input: { board_id: 'EmbedBuild/demo', uc_id: 'UC-9999' } });
    assert.equal(enviados(dir).length, 1, 'otra UC: no se manda');
    correr(dir, { hook_event_name: 'PreToolUse', tool_name: 'mcp__SpecBox-MCP__complete_uc', session_id: SESION, transcript_path: t, tool_input: { board_id: 'EmbedBuild/demo', uc_id: 'UC-12403' } });
    assert.deepEqual(enviados(dir).map((e) => [e.agent_id, e.input_tokens]), [['ab12', 7], ['', 4]]);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test('AC-03 · formato desconocido, sin UC activa o sin board native: no manda nada', () => {
  for (const opciones of [{}, { uc: null }, { native: false }]) {
    const dir = repo(opciones);
    try {
      const t = join(dir, 'sesion.jsonl');
      const contenido = opciones.uc === undefined && opciones.native === undefined
        ? `${JSON.stringify({ type: 'assistant', message: { content: SECRETO } })}\n`
        : `${linea('msg_1', uso(1, 1))}\n`;
      writeFileSync(t, contenido);
      const r = correr(dir, { hook_event_name: 'Stop', session_id: SESION, transcript_path: t });
      assert.equal(r.status, 0);
      assert.deepEqual(enviados(dir), []);
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  }
});

test('el envío guarda el cursor solo si el board lo acepta y borra la marca de envío en curso', async () => {
  const dir = mkdtempSync(join(tmpdir(), 'uc-usage-envio-'));
  try {
    const cursorRuta = rutaCursor(dir, '/t/s.jsonl');
    const cursor = { ruta: '/t/s.jsonl', offset: 42, ids: ['msg_1'] };
    const datos = { project_id: 'EmbedBuild/demo', uc_id: 'UC-1', session_id: SESION, agent_id: '', input_tokens: 1, output_tokens: 1, cache_creation_input_tokens: 0, cache_read_input_tokens: 0, messages: 1 };
    const responde = (payload) => async () => new Response(
      JSON.stringify({ jsonrpc: '2.0', id: 1, result: { structuredContent: payload, content: [{ type: 'text', text: JSON.stringify(payload) }] } }),
      { status: 200, headers: { 'content-type': 'application/json' } },
    );
    writeFileSync(`${cursorRuta}.pending`, '1');
    const mal = await enviarUso({ raiz: dir, informe: datos, cursorRuta, cursor, cabeceras: { Authorization: 'Bearer x' }, fetchImpl: async () => { throw new Error('sin red'); } });
    assert.equal(mal, false);
    assert.ok(!existsSync(cursorRuta));
    assert.ok(!existsSync(`${cursorRuta}.pending`));
    assert.match(readFileSync(join(dir, '.quality/logs/uc-usage.log'), 'utf8'), /no enviados: sin red/);

    const bien = await enviarUso({ raiz: dir, informe: datos, cursorRuta, cursor, cabeceras: { Authorization: 'Bearer x' }, fetchImpl: responde({ success: true, recorded: true }) });
    assert.equal(bien, true);
    assert.deepEqual(JSON.parse(readFileSync(cursorRuta, 'utf8')), cursor);
    assert.ok(!readFileSync(join(dir, '.quality/logs/uc-usage.log'), 'utf8').includes('Bearer'));
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
