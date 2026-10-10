/**
 * UC-9101 (US-91): /design-review verify mide la pantalla y aplica reglas deterministas.
 *
 * - AC-01: capturas a 1440 y 390 y desbordamiento con los elementos que sobresalen.
 * - AC-02: cada regla (degradado, borde lateral, eyebrow, transition all, emoji, contraste y área de
 *   pulsación) con su ubicación.
 * - AC-04: sin dependencias nuevas: usa el Playwright del proyecto y, si no lo hay, lo dice y sale.
 *
 * Las funciones puras se prueban siempre. La integración necesita Playwright: se toma de
 * SPECBOX_PLAYWRIGHT (ruta al paquete) o del proyecto, y se salta si no está.
 *
 * Ejecutar: SPECBOX_PLAYWRIGHT=<ruta>/node_modules/playwright node --test tests/design-review/verify.test.mjs
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  contrastRatio,
  findSourceLine,
  hasEmoji,
  loadPlaywright,
  numbersIn,
  numbersWithoutSource,
  verify,
} from '../../.claude/skills/design-review/scripts/verify.mjs';

const repoRoot = resolve(fileURLToPath(import.meta.url), '../../..');
const script = join(repoRoot, '.claude/skills/design-review/scripts/verify.mjs');
const fixtures = join(repoRoot, 'tests/design-review/fixtures');
const pw = loadPlaywright(process.env.SPECBOX_PLAYWRIGHT);
const needsPlaywright = { skip: pw ? false : 'sin Playwright (SPECBOX_PLAYWRIGHT o el del proyecto)' };

// ── Funciones puras ──────────────────────────────────────────────────────

test('contraste WCAG: negro sobre blanco 21:1, gris claro por debajo de 4,5', () => {
  assert.equal(Math.round(contrastRatio([0, 0, 0], [255, 255, 255])), 21);
  assert.ok(contrastRatio([187, 187, 187], [255, 255, 255]) < 4.5);
  assert.ok(contrastRatio([89, 97, 106], [255, 255, 255]) >= 4.5);
});

test('emoji: pictogramas sí, signos de marca y texto no', () => {
  assert.ok(hasEmoji('🚀'));
  assert.ok(hasEmoji('Lanzar ✨'));
  assert.ok(!hasEmoji('© SpecBox ™'));
  assert.ok(!hasEmoji('Reforma cocina → 4.800 €'));
});

test('ubicación: un hallazgo se lleva a su línea por id, clase o texto', () => {
  const lines = ['<main>', '  <div id="resumen">', '  <p class="tenue nota">Hola</p>', '  <span>Texto largo único</span>'];
  assert.equal(findSourceLine(lines, { tag: 'div', id: 'resumen' }), 2);
  assert.equal(findSourceLine(lines, { tag: 'p', className: 'tenue nota' }), 3);
  assert.equal(findSourceLine(lines, { tag: 'span', className: '', text: 'Texto largo único' }), 4);
  assert.equal(findSourceLine(lines, { tag: 'b', className: 'otra' }), null);
  // El <title> repite el texto del enlace: la línea es la del cuerpo.
  const page = ['<title>ESBK 2026</title>', '<style>.crumb a{}</style>', '<body>', '<nav>', '  <li><a href="#">ESBK 2026</a></li>'];
  assert.equal(findSourceLine(page, { tag: 'a', className: '', text: 'ESBK 2026' }), 5);
});

test('cifras: se normalizan los separadores y se detectan las nuevas sin fuente', () => {
  assert.deepEqual(numbersIn('4.800 € · 81 % · 9 min'), ['4800€', '81%', '9']);
  const antes = numbersIn('Tres propuestas: 4.800 €');
  const despues = numbersIn('Tres propuestas: 4.800 € · 12 participantes · 81 %');
  assert.deepEqual(numbersWithoutSource(antes, despues, 'El brief dice que la tasa es del 81 %'), ['12']);
});

// ── Integración ──────────────────────────────────────────────────────────

test('pantalla con tells: cada regla aparece con su ubicación y el desbordamiento con quién sobresale', needsPlaywright, async () => {
  const out = mkdtempSync(join(tmpdir(), 'verify-'));
  try {
    const source = join(fixtures, 'tells.html');
    const r = await verify({ target: source, out, name: 'tells', playwright: process.env.SPECBOX_PLAYWRIGHT });
    const lines = readFileSync(source, 'utf8').split('\n');
    const lineOf = (needle) => lines.findIndex((l) => l.includes(needle)) + 1;

    // AC-01
    assert.ok(existsSync(join(out, 'tells-1440.png')) && existsSync(join(out, 'tells-390.png')));
    assert.ok(existsSync(join(out, 'tells-verify.json')));
    assert.equal(r.anchos[1440].desborda, false);
    assert.equal(r.anchos[390].desborda, true);
    assert.ok(r.anchos[390].sobresalen.some((s) => s.selector.includes('div.ancha')));

    // AC-02
    const of = (regla) => r.hallazgos.filter((f) => f.regla === regla);
    assert.equal(of('texto-degradado')[0].linea, lineOf('class="degradado"'));
    assert.equal(of('borde-lateral')[0].linea, lineOf('class="aviso"'));
    assert.equal(of('eyebrow')[0].linea, lineOf('class="antetitulo"'));
    assert.equal(of('transition-all')[0].linea, lineOf('class="boton"'));
    assert.equal(of('emoji-icono')[0].linea, lineOf('class="icono"'));
    assert.ok(of('contraste').some((f) => f.linea === lineOf('class="tenue"') && /:1/.test(f.detalle)));
    const tap = of('area-pulsacion');
    assert.ok(tap.some((f) => f.linea === lineOf('class="peque"') && f.ancho === 390));
    assert.ok(!tap.some((f) => f.selector.includes('boton')), 'un botón de 44 px no es un hallazgo');
    for (const f of r.hallazgos) assert.ok(f.selector, `${f.regla} sin selector`);
  } finally {
    rmSync(out, { recursive: true, force: true });
  }
});

test('pantalla limpia: sin hallazgos ni desbordamiento', needsPlaywright, async () => {
  const out = mkdtempSync(join(tmpdir(), 'verify-'));
  try {
    const r = await verify({ target: join(fixtures, 'limpia.html'), out, name: 'limpia', playwright: process.env.SPECBOX_PLAYWRIGHT });
    assert.deepEqual(r.hallazgos, []);
    assert.deepEqual(Object.values(r.resumen.desborda), [false, false]);
    assert.ok(r.duracion_ms < 180000, 'menos de 3 minutos por pantalla');
  } finally {
    rmSync(out, { recursive: true, force: true });
  }
});

test('pantalla quieta: espera a que acabe la animación de entrada antes de medir', needsPlaywright, async () => {
  const out = mkdtempSync(join(tmpdir(), 'verify-'));
  try {
    // .nota empieza invisible y aparece a los 1,4 s: medida antes, no existiría.
    const r = await verify({ target: join(fixtures, 'animada.html'), out, name: 'animada', playwright: process.env.SPECBOX_PLAYWRIGHT });
    assert.ok(r.hallazgos.some((f) => f.regla === 'borde-lateral' && f.selector.includes('nota')));
  } finally {
    rmSync(out, { recursive: true, force: true });
  }
});

test('dato-sin-fuente: tras una corrección, las cifras nuevas que no están en las fuentes', needsPlaywright, async () => {
  const out = mkdtempSync(join(tmpdir(), 'verify-'));
  try {
    const previous = join(out, 'antes-verify.json');
    writeFileSync(previous, JSON.stringify({ numeros: numbersIn('Propuestas pendientes 4.800 € 2.150 €') }));
    const brief = join(out, 'pantalla.brief.md');
    writeFileSync(brief, '# Brief\n\n- Ingresos del mes: 12.400 €\n');
    const r = await verify({ target: join(fixtures, 'tells.html'), out, name: 'despues', previous, sources: [brief], playwright: process.env.SPECBOX_PLAYWRIGHT });
    assert.ok(r.dato_sin_fuente.includes('81%'));
    assert.ok(!r.dato_sin_fuente.includes('12400€'), 'una cifra del brief tiene fuente');
  } finally {
    rmSync(out, { recursive: true, force: true });
  }
});

test('sin Playwright: lo dice y sale con código 2, sin instalar nada', () => {
  const cwd = mkdtempSync(join(tmpdir(), 'sin-pw-'));
  try {
    writeFileSync(join(cwd, 'package.json'), '{"name":"sin-playwright"}');
    const res = spawnSync(process.execPath, [script, join(fixtures, 'limpia.html'), '--out', join(cwd, 'out')], {
      cwd,
      encoding: 'utf8',
      env: { ...process.env, NODE_PATH: '' },
    });
    assert.equal(res.status, 2, res.stderr);
    assert.match(res.stderr, /no tiene Playwright/);
    assert.ok(!existsSync(join(cwd, 'node_modules')), 'no instala nada');
  } finally {
    rmSync(cwd, { recursive: true, force: true });
  }
});
