/**
 * US-122 / UC-12212 — los hooks leen el mismo modo de cada medida que el servidor (AC-04).
 *
 * FreeForm: doc/tracking/policy.json. native: get_enforcement_policy con la identidad del
 * dispositivo y 10 minutos de caché; sin red, la última copia; sin copia, «warn». Trello y Plane,
 * «warn» como máximo. Ejecutar: node --test tests/hooks/enforcement-policy.test.mjs
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import {
  CACHE_FILE,
  CACHE_MS,
  MEASURES,
  leerPolitica,
  modoDe,
  modosDe,
  textoDeMedida,
} from '../../.claude/hooks/lib/enforcement-policy.mjs';

function carpeta() {
  return mkdtempSync(join(tmpdir(), 'enforcement-policy-'));
}

function servidorFalso(respuestaTool) {
  const llamadas = [];
  const fetchImpl = async (_url, opts) => {
    const cuerpo = JSON.parse(opts.body);
    llamadas.push({ metodo: cuerpo.method, params: cuerpo.params });
    const cabeceras = new Map([['mcp-session-id', 'sesion-1'], ['content-type', 'application/json']]);
    const res = (status, texto) => ({ status, headers: { get: (k) => cabeceras.get(k) ?? null }, text: async () => texto });
    if (cuerpo.method === 'initialize') return res(200, JSON.stringify({ jsonrpc: '2.0', id: 1, result: {} }));
    if (cuerpo.method === 'notifications/initialized') return res(202, '');
    return res(200, JSON.stringify({ jsonrpc: '2.0', id: 2, result: { structuredContent: respuestaTool } }));
  };
  return { fetchImpl, llamadas };
}

const H = { Authorization: 'Bearer t' };
const POLITICA_TABLERO = {
  success: true,
  policy: { origin: 'existing', measures: { spec_quality: { mode: 'block' }, drift_gate: { mode: 'off' } } },
};

test('sin política, un tablero ya existía: todas las medidas en «warn»', () => {
  const p = modosDe(null, 'native');
  assert.equal(p.origin, 'existing');
  assert.deepEqual(Object.keys(p.modos), Object.keys(MEASURES));
  assert.ok(Object.values(p.modos).every((m) => m === 'warn'));
  assert.equal(modoDe(p, 'no_existe'), 'warn');
});

test('FreeForm: el hook lee el mismo policy.json que recibe el servidor', async () => {
  const root = carpeta();
  try {
    mkdirSync(join(root, 'doc', 'tracking'), { recursive: true });
    writeFileSync(
      join(root, 'doc', 'tracking', 'policy.json'),
      JSON.stringify({ schema: 1, origin: 'new', measures: { spec_quality: { mode: 'block' } } }),
    );
    const p = await leerPolitica({ root, backendType: 'freeform', fetchImpl: () => assert.fail('sin red') });
    assert.equal(p.fuente, 'policy.json');
    assert.equal(p.origin, 'new');
    assert.equal(modoDe(p, 'spec_quality'), 'block');
    assert.equal(modoDe(p, 'drift_gate'), 'warn');
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test('Trello y Plane: «warn» como máximo, sin preguntar a nadie', async () => {
  for (const backendType of ['trello', 'plane']) {
    const p = await leerPolitica({ backendType, fetchImpl: () => assert.fail('sin red') });
    assert.ok(Object.values(p.modos).every((m) => m === 'warn'));
    assert.equal(modosDe({ origin: 'new', measures: { spec_quality: { mode: 'block' } } }, backendType).modos.spec_quality, 'warn');
  }
});

test('native: pregunta al tablero, guarda 10 minutos y sin red usa la última copia', async () => {
  const root = carpeta();
  try {
    const { fetchImpl, llamadas } = servidorFalso(POLITICA_TABLERO);
    const ahora = Date.parse('2026-11-18T10:00:00Z');
    const p = await leerPolitica({ root, backendType: 'native', boardId: 'Acme/web', env: {}, cabeceras: H, fetchImpl, ahora });
    assert.equal(p.fuente, 'tablero');
    assert.equal(modoDe(p, 'spec_quality'), 'block');
    assert.equal(modoDe(p, 'drift_gate'), 'off');
    const llamada = llamadas.find((l) => l.metodo === 'tools/call');
    assert.deepEqual(llamada.params, { name: 'get_enforcement_policy', arguments: { board_id: 'Acme/web' } });
    const copia = JSON.parse(readFileSync(join(root, CACHE_FILE), 'utf-8'));
    assert.equal(copia.project_id, 'Acme/web');

    const sinRed = async () => {
      throw new Error('offline');
    };
    const enCache = await leerPolitica({ root, backendType: 'native', boardId: 'Acme/web', env: {}, cabeceras: H, fetchImpl: sinRed, ahora: ahora + CACHE_MS - 1 });
    assert.equal(enCache.fuente, 'caché');
    const vieja = await leerPolitica({ root, backendType: 'native', boardId: 'Acme/web', env: {}, cabeceras: H, fetchImpl: sinRed, ahora: ahora + CACHE_MS + 1 });
    assert.equal(vieja.fuente, 'caché antigua');
    assert.equal(modoDe(vieja, 'spec_quality'), 'block');

    // La copia es de un proyecto: otro proyecto sin red no la usa.
    const otro = await leerPolitica({ root, backendType: 'native', boardId: 'Acme/otro', env: {}, cabeceras: H, fetchImpl: sinRed, ahora });
    assert.equal(otro.fuente, 'por defecto');
    assert.ok(Object.values(otro.modos).every((m) => m === 'warn'));
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test('native sin credencial o con la lectura apagada no llama a nadie y queda en «warn»', async () => {
  const root = carpeta();
  try {
    const nunca = () => assert.fail('no debía llamar');
    const sinCredencial = await leerPolitica({ root, backendType: 'native', boardId: 'Acme/web', env: {}, cabeceras: {}, fetchImpl: nunca });
    assert.equal(sinCredencial.fuente, 'por defecto');
    const apagada = await leerPolitica({ root, backendType: 'native', boardId: 'Acme/web', env: { SPECBOX_ENFORCEMENT_POLICY: 'off' }, cabeceras: H, fetchImpl: nunca });
    assert.equal(apagada.fuente, 'por defecto');
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test('el texto de una medida dice la medida, el motivo y cómo seguir (AC-06)', () => {
  const texto = textoDeMedida({ medida: 'spec_in_pr', modo: 'block', motivo: 'El PRD no cambia en esta PR.', comoSeguir: 'Actualiza doc/prd en la misma rama.' });
  for (const parte of ['spec_in_pr', 'El PRD no cambia en esta PR.', 'Actualiza doc/prd en la misma rama.', 'detuvo']) {
    assert.ok(texto.includes(parte), parte);
  }
  assert.ok(textoDeMedida({ medida: 'x', modo: 'warn', motivo: 'm', comoSeguir: 'c' }).startsWith('Aviso de SpecBox'));
});
