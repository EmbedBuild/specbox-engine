/**
 * Pruebas de app-spec-zones.mjs (UC-12205).
 * Run: node --test .claude/hooks/lib/app-spec-zones.test.mjs
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { parseAutoZones, zoneAttributes, SESSION_ZONES } from './app-spec-zones.mjs';

const TEMPLATE = resolve(fileURLToPath(import.meta.url), '..', '..', '..', '..', 'templates/app_spec.md.template');

const zone = (attrs, body) => `<!-- @specbox:zone start ${attrs} -->\n${body}\n<!-- @specbox:zone end -->`;

test('AC-01/AC-03: la plantilla real de app_spec da las tres zonas del arranque, con contenido', () => {
  const zones = parseAutoZones(readFileSync(TEMPLATE, 'utf-8'));
  assert.deepEqual(Object.keys(zones).sort(), [...SESSION_ZONES].sort());
  assert.match(zones.stack, /## 1\. Stack/);
  assert.match(zones.tracking_backend, /\*\*Tipo:\*\*/);
  assert.match(zones.autopilot, /\*\*Level:\*\*/);
});

test('AC-02: los atributos valen en cualquier orden y con otros atributos', () => {
  const content = [
    zone('id="stack" kind="auto"', 'A'),
    zone('auto_sync_on="set_auth_token" kind="auto" id="tracking_backend"', 'B'),
    zone('kind="auto" merge="append_only" id="autopilot" auto_sync_on="x,y"', 'C'),
  ].join('\n\n');
  assert.deepEqual(parseAutoZones(content), { stack: 'A', tracking_backend: 'B', autopilot: 'C' });
});

test('AC-02: el marcador corto de siempre sigue valiendo', () => {
  const content = zone('kind="auto" id="tracking_backend"', '- Backend: freeform');
  assert.deepEqual(parseAutoZones(content), { tracking_backend: '- Backend: freeform' });
});

test('AC-02: comillas simples y espacios alrededor del igual', () => {
  const content = zone("kind = 'auto'   id='stack'", 'S');
  assert.deepEqual(parseAutoZones(content), { stack: 'S' });
});

test('las zonas manuales, híbridas o no pedidas no se devuelven', () => {
  const content = [
    zone('kind="manual" id="stack"', 'manual'),
    zone('kind="hybrid" id="autopilot" merge="append_only"', 'híbrida'),
    zone('kind="auto" id="roadmap"', 'otra'),
  ].join('\n');
  assert.deepEqual(parseAutoZones(content), {});
});

test('una zona no se come la siguiente', () => {
  const content = `${zone('kind="manual" id="a"', 'uno')}\n${zone('kind="auto" id="stack"', 'dos')}`;
  assert.deepEqual(parseAutoZones(content), { stack: 'dos' });
});

test('contenido ausente o sin zonas devuelve un objeto vacío', () => {
  assert.deepEqual(parseAutoZones(undefined), {});
  assert.deepEqual(parseAutoZones('# App Spec sin zonas'), {});
});

test('zoneAttributes lee todos los atributos', () => {
  assert.deepEqual(zoneAttributes(' kind="auto" id="stack" auto_sync_on="a,b" '), {
    kind: 'auto',
    id: 'stack',
    auto_sync_on: 'a,b',
  });
});
