/**
 * UC-9202 (US-92): las pantallas aprobadas de un lienzo de Claude Design llegan a la carpeta de diseño
 * con su origen.
 *
 * - AC-01: fuente, vista congelada que se abre sin conexión y vista del lienzo con dirección y versión.
 * - AC-03: sin cambios no se escribe nada; con cambios se dice qué artboards cambiaron.
 * - AC-04: la vista congelada no lleva piezas del motor del lienzo.
 *
 * UC-9201: `scaffold`, el esqueleto del lienzo de una feature que crea /plan (dos artboards por
 * pantalla, notas del brief y el sistema de diseño instalado).
 *
 * La importación se prueba con un pintor simulado. El congelado real necesita Playwright y el motor que
 * sirve cada lienzo (`artifact-type/dc-runtime.js`), que no es nuestro y no entra en el repositorio:
 * se toma de SPECBOX_PLAYWRIGHT y SPECBOX_DC_RUNTIME, y se salta si no están.
 *
 * Ejecutar: SPECBOX_PLAYWRIGHT=<ruta>/playwright SPECBOX_DC_RUNTIME=<ruta>/dc-runtime.js node --test tests/design-review/canvas.test.mjs
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';

import {
  BANNER_MARK,
  boardKey,
  boardPathError,
  briefQuestions,
  declaresProp,
  parseStates,
  stateSlug,
  stateWrapper,
  canvasView,
  dsFolder,
  engineTraces,
  importCanvas,
  offlineFontCss,
  planImport,
  scaffold,
  scaffoldCanvas,
  stampView,
  status,
  viewName,
} from '../../.claude/skills/design-review/scripts/canvas.mjs';
import { loadPlaywright } from '../../.claude/skills/design-review/scripts/verify.mjs';

const URL_LIENZO = 'https://claude.ai/artifact/AbCdEf123';
const BLOB = '0123456789abcdef0123456789abcdef';
const FONT_CSS = 'https://fonts.googleapis.com/css2?family=Demo+Sans:wght@400;600&display=swap';

// ── Funciones puras ──────────────────────────────────────────────────────

test('rutas del índice: solo ficheros .dc.html sin escapar de la carpeta', () => {
  for (const ok of ['Main.dc.html', 'flujo/Pago.dc.html', '_base.dc.html', 'Movil-390.dc.html']) assert.equal(boardPathError(ok), null, ok);
  for (const bad of ['../x.dc.html', '/Main.dc.html', 'a\\b.dc.html', 'Main.html', 'a/../b.dc.html', 'con espacio.dc.html', '']) {
    assert.ok(boardPathError(bad), bad);
  }
  assert.equal(boardKey('Main'), 'Main.dc.html');
  assert.equal(boardKey('Main.dc.html'), 'Main.dc.html');
  assert.equal(viewName('Main.dc.html'), 'Main.html');
  assert.equal(viewName('flujo/Pago.dc.html'), 'flujo-Pago.html');
});

test('planImport: nuevo, cambiado, igual y retirado', () => {
  const previous = { artboards: {
    'A.dc.html': { huella: 'a1', fuente: 'canvas/A.dc.html', vista: 'A.html' },
    'B.dc.html': { huella: 'b1', fuente: 'canvas/B.dc.html', vista: 'B.html' },
    'Viejo.dc.html': { huella: 'v', fuente: 'canvas/Viejo.dc.html', vista: 'Viejo.html' },
  } };
  const boards = { 'A.dc.html': {}, 'B.dc.html': {}, 'C.dc.html': {} };
  const r = planImport({ boards, approved: ['A.dc.html', 'B.dc.html', 'C.dc.html'], prints: { 'A.dc.html': 'a1', 'B.dc.html': 'b2', 'C.dc.html': 'c1' }, previous });
  assert.deepEqual(r.estados, { 'A.dc.html': 'igual', 'B.dc.html': 'cambiado', 'C.dc.html': 'nuevo', 'Viejo.dc.html': 'retirado' });
  assert.equal(r.sinCambios, false);
  const same = planImport({ boards, approved: ['A.dc.html'], prints: { 'A.dc.html': 'a1' }, previous });
  assert.equal(same.sinCambios, true);
  // Una vista borrada a mano se vuelve a escribir aunque el lienzo no haya cambiado.
  const gone = planImport({ boards, approved: ['A.dc.html'], prints: { 'A.dc.html': 'a1' }, previous, exists: (p) => p !== 'A.html' });
  assert.equal(gone.estados['A.dc.html'], 'cambiado');
});

test('AC-01: la vista congelada lleva el origen en la primera línea y viewport', () => {
  const html = stampView('<!doctype html>\n<html><head><title>X</title></head><body>hola</body></html>', { url: URL_LIENZO, version: '17-ab', board: 'Main.dc.html', importado: '2026-10-10T10:00:00Z' });
  const [first, ...rest] = html.split('\n');
  assert.ok(first.startsWith(`<!-- ${BANNER_MARK}`));
  assert.ok(first.includes(`lienzo=${URL_LIENZO}`) && first.includes('version=17-ab') && first.includes('artboard=Main.dc.html'));
  assert.match(rest.join('\n'), /<meta name="viewport" content="width=device-width, initial-scale=1">/);
  assert.match(rest.join('\n'), /<meta name="specbox:canvas" content="https:\/\/claude\.ai\/artifact\/AbCdEf123">/);
  // Si ya trae viewport, no se duplica.
  const twice = stampView('<html><head><meta name="viewport" content="width=390"></head></html>', { url: URL_LIENZO, version: '1', board: 'M.dc.html', importado: 'x' });
  assert.equal((twice.match(/name="viewport"/g) || []).length, 1);
});

test('AC-01: la vista del lienzo enseña dirección, versión y cada artboard a su ancho', () => {
  const html = canvasView({ url: URL_LIENZO, titulo: 'Propuestas <beta>', lienzo_version: '17-ab', importado: '2026-10-10T10:00:00.000Z', artboards: {
    'Main.dc.html': { vista: 'Main.html', ancho: 1440, alto: 1600, titulo: 'Escritorio' },
    'Movil.dc.html': { vista: 'Movil.html', ancho: 390, alto: 3000, titulo: 'Móvil, 390 px' },
    'Viejo.dc.html': { vista: 'Viejo.html', ancho: 390, retirado: true },
  } });
  assert.match(html, /<dt>Lienzo<\/dt><dd><a href="https:\/\/claude\.ai\/artifact\/AbCdEf123">/);
  assert.match(html, /<dt>Versión<\/dt><dd>17-ab<\/dd>/);
  assert.match(html, /Propuestas &lt;beta&gt;/, 'escapa el título');
  assert.match(html, /<iframe src="Main\.html"[^>]*width="1440" height="1600"/);
  assert.match(html, /<iframe src="Movil\.html"[^>]*width="390" height="3000"/);
  assert.doesNotMatch(html, /Viejo\.html/, 'lo retirado no se enseña');
  assert.doesNotMatch(html, /390 px · Movil/, 'no repite el ancho si el título ya lo dice');
});

test('AC-04: detecta las piezas del motor del lienzo', () => {
  assert.deepEqual(engineTraces('<div class="x">hola</div>'), []);
  assert.deepEqual(engineTraces(`<script src="./support.js"></script><x-dc></x-dc><img src="/_blob/${BLOB}">`), ['support.js', '<x-dc>', '/_blob/']);
});

function fakeFetch({ offline = false } = {}) {
  const calls = [];
  const impl = async (url) => {
    calls.push(url);
    if (offline) throw new Error('sin red');
    if (url.startsWith('https://fonts.googleapis.com/')) {
      return new Response('/* cyrillic */\n@font-face { font-family: "Demo Sans"; src: url(https://fonts.gstatic.com/s/demo/cyr.woff2) format("woff2"); unicode-range: U+0400-045F; }\n'
        + '/* latin-ext */\n@font-face { font-family: "Demo Sans"; src: url(https://fonts.gstatic.com/s/demo/ext.woff2) format("woff2"); unicode-range: U+0100-02BA; }\n'
        + '/* latin */\n@font-face { font-family: "Demo Sans"; src: url(https://fonts.gstatic.com/s/demo/latin.woff2) format("woff2"); unicode-range: U+0000-00FF; }\n');
    }
    return new Response(Buffer.from(`font:${url}`));
  };
  return { impl, calls };
}

test('tipografías sin conexión: solo latin y latin-ext, dentro de la hoja', async () => {
  const { impl, calls } = fakeFetch();
  const css = await offlineFontCss(FONT_CSS, impl);
  assert.equal((css.match(/@font-face/g) || []).length, 2);
  assert.match(css, /url\(data:font\/woff2;base64,/);
  assert.doesNotMatch(css, /gstatic|cyr\.woff2/);
  assert.ok(!calls.some((u) => u.includes('cyr.woff2')), 'no baja subconjuntos que no hacen falta');
  assert.equal(await offlineFontCss(FONT_CSS, fakeFetch({ offline: true }).impl), null);
});

// ── Importación con un pintor simulado ───────────────────────────────────

function board(text) {
  return `<!doctype html>\n<html lang="es"><head><meta charset="utf-8"><title>${text}</title><script src="./support.js"></script>`
    + '<link rel="stylesheet" href="ds/demo/components/bundle.css"></head><body><x-dc><helmet>'
    + `<link rel="stylesheet" href="${FONT_CSS.replace(/&/g, '&amp;')}"></helmet><main>{{titulo}}</main></x-dc>`
    + `<script type="text/x-dc" data-dc-script data-props='{}'>class Component extends DCLogic { renderVals() { return { titulo: ${JSON.stringify(text)} }; } }</script></body></html>\n`;
}

// Lo que haría el motor: pinta los huecos y deja el DOM sin <x-dc> ni scripts (lo quita serialize()).
const fakeRenderer = (from, renders = []) => ({
  async render(name, entry) {
    renders.push(name);
    const src = readFileSync(join(from, 'project', name), 'utf8');
    const text = src.match(/titulo: "([^"]*)"/)[1];
    const img = src.includes('_blob') ? `<img src="/_blob/${BLOB}" alt="logo">` : '';
    return {
      html: `<!doctype html>\n<html lang="es"><head><meta charset="utf-8"><title>${text}</title><link rel="stylesheet" href="ds/demo/components/bundle.css"><link rel="stylesheet" href="${FONT_CSS.replace(/&/g, '&amp;')}"></head><body><main style="width:${entry.w}px">${text}${img}</main></body></html>`,
      alto: 800,
    };
  },
  async close() {},
});

function canvasFolder(boards = { 'Main.dc.html': 'Propuestas', 'Movil.dc.html': 'Propuestas móvil' }) {
  const from = mkdtempSync(join(tmpdir(), 'lienzo-'));
  const put = (rel, text) => { mkdirSync(dirname(join(from, rel)), { recursive: true }); writeFileSync(join(from, rel), text); };
  const index = { v: 3, title: 'Seguimiento', boards: {}, order: [], designSystems: [] };
  for (const [name, text] of Object.entries(boards)) {
    index.boards[name] = { x: 0, y: 0, w: name.startsWith('Movil') ? 390 : 1440, h: 900, title: name };
    index.order.push(name);
    put(`project/${name}`, board(text));
  }
  put('project/canvas.json', JSON.stringify(index));
  put('project/ds/demo/components/bundle.css', '.demo{color:#123456}');
  return { from, put, index };
}

function snapshot(dir) {
  const out = {};
  const walk = (d) => {
    for (const name of existsSync(d) ? readdirSync(d) : []) {
      const f = join(d, name);
      if (statSync(f).isDirectory()) walk(f); else out[f] = `${statSync(f).mtimeMs}:${statSync(f).size}`;
    }
  };
  walk(dir);
  return out;
}

async function run(c, out, extra = {}) {
  const renders = [];
  const r = await importCanvas({ from: c.from, url: URL_LIENZO, version: extra.version || '17-ab', feature: 'propuestas', out, renderer: fakeRenderer(c.from, renders), fetchImpl: fakeFetch().impl, ...extra });
  return { r, renders };
}

test('AC-01: la importación deja fuente, vista congelada, vista del lienzo y manifiesto', async () => {
  const c = canvasFolder();
  const out = mkdtempSync(join(tmpdir(), 'diseno-'));
  try {
    const { r } = await run(c, out, { boards: ['Main', 'Movil'] });
    assert.deepEqual(r.estados, { 'Main.dc.html': 'nuevo', 'Movil.dc.html': 'nuevo' });
    for (const f of ['canvas/Main.dc.html', 'canvas/Movil.dc.html', 'Main.html', 'Movil.html', 'canvas.html', 'claude-design.json']) {
      assert.ok(existsSync(join(out, f)), f);
    }
    assert.equal(readFileSync(join(out, 'canvas/Main.dc.html'), 'utf8'), board('Propuestas'), 'la fuente se guarda tal cual');
    const view = readFileSync(join(out, 'Main.html'), 'utf8');
    assert.ok(view.split('\n')[0].includes(`lienzo=${URL_LIENZO}`) && view.split('\n')[0].includes('version=17-ab'));
    assert.deepEqual(engineTraces(view.split('\n').slice(1).join('\n')), [], 'AC-04: sin piezas del motor');
    assert.match(view, /<style data-specbox-from="ds\/demo\/components\/bundle\.css">\n\.demo\{color:#123456\}/, 'la hoja del sistema va en línea');
    assert.match(view, /<link rel="stylesheet" href="fonts\/[0-9a-f]{12}\.css">/, 'Google Fonts pasa a una hoja local');
    assert.doesNotMatch(view, /fonts\.googleapis/);
    const manifest = JSON.parse(readFileSync(join(out, 'claude-design.json'), 'utf8'));
    assert.equal(manifest.url, URL_LIENZO);
    assert.equal(manifest.lienzo_version, '17-ab');
    assert.equal(manifest.artboards['Movil.dc.html'].ancho, 390);
    assert.equal(manifest.artboards['Movil.dc.html'].vista, 'Movil.html');
    assert.match(readFileSync(join(out, 'canvas.html'), 'utf8'), /<dt>Versión<\/dt><dd>17-ab<\/dd>/);
    assert.equal(status({ feature: 'propuestas', out }).artboards['Main.dc.html'].vista, 'Main.html');
  } finally {
    rmSync(c.from, { recursive: true, force: true });
    rmSync(out, { recursive: true, force: true });
  }
});

test('AC-03: sin cambios no se escribe nada; con un artboard cambiado, solo ese', async () => {
  const c = canvasFolder();
  const out = mkdtempSync(join(tmpdir(), 'diseno-'));
  try {
    await run(c, out, { boards: ['Main', 'Movil'] });
    const before = snapshot(out);
    await new Promise((ok) => setTimeout(ok, 20));
    // Sin --boards: reimporta los ya aprobados.
    const again = await run(c, out);
    assert.equal(again.r.sin_cambios, true);
    assert.deepEqual(again.r.escritos, []);
    assert.deepEqual(again.renders, [], 'ni siquiera pinta');
    assert.deepEqual(snapshot(out), before, 'ningún fichero cambia');
    // El lienzo cambia de versión pero lo aprobado es igual: tampoco se escribe.
    const otherVersion = await run(c, out, { version: '18-cd' });
    assert.equal(otherVersion.r.sin_cambios, true);

    c.put('project/Movil.dc.html', board('Propuestas móvil v2'));
    const changed = await run(c, out, { version: '19-ef' });
    assert.deepEqual(changed.r.estados, { 'Main.dc.html': 'igual', 'Movil.dc.html': 'cambiado' });
    assert.deepEqual(changed.renders, ['Movil.dc.html']);
    assert.deepEqual(changed.r.escritos.sort(), ['Movil.html', 'canvas.html', 'canvas/Movil.dc.html', 'claude-design.json']);
    assert.equal(snapshot(out)[join(out, 'Main.html')], before[join(out, 'Main.html')], 'Main no se toca');
    assert.match(readFileSync(join(out, 'Movil.html'), 'utf8'), /Propuestas móvil v2/);
    const manifest = JSON.parse(readFileSync(join(out, 'claude-design.json'), 'utf8'));
    assert.equal(manifest.lienzo_version, '19-ef');
    assert.equal(manifest.artboards['Main.dc.html'].lienzo_version, '17-ab');
    assert.equal(manifest.artboards['Movil.dc.html'].lienzo_version, '19-ef');

    // Un cambio en la copia del sistema de diseño cambia la pantalla.
    c.put('project/ds/demo/components/bundle.css', '.demo{color:#654321}');
    const ds = await run(c, out, { version: '20-gh' });
    assert.deepEqual(ds.r.estados, { 'Main.dc.html': 'cambiado', 'Movil.dc.html': 'cambiado' });
  } finally {
    rmSync(c.from, { recursive: true, force: true });
    rmSync(out, { recursive: true, force: true });
  }
});

test('AC-03: un artboard que desaparece del lienzo se informa como retirado y no se borra', async () => {
  const c = canvasFolder();
  const out = mkdtempSync(join(tmpdir(), 'diseno-'));
  try {
    await run(c, out, { boards: ['Main', 'Movil'] });
    const index = JSON.parse(readFileSync(join(c.from, 'project/canvas.json'), 'utf8'));
    delete index.boards['Movil.dc.html'];
    c.put('project/canvas.json', JSON.stringify(index));
    c.put('project/Main.dc.html', board('Propuestas v2'));
    const { r } = await run(c, out, { version: '21' });
    assert.equal(r.estados['Movil.dc.html'], 'retirado');
    assert.ok(existsSync(join(out, 'Movil.html')), 'no se borra el diseño');
    const manifest = JSON.parse(readFileSync(join(out, 'claude-design.json'), 'utf8'));
    assert.equal(manifest.artboards['Movil.dc.html'].retirado, true);
    assert.doesNotMatch(readFileSync(join(out, 'canvas.html'), 'utf8'), /Movil\.html/);
  } finally {
    rmSync(c.from, { recursive: true, force: true });
    rmSync(out, { recursive: true, force: true });
  }
});

test('aprobar es nombrar: sin nombres la primera vez, o con uno que no está, no se escribe nada', async () => {
  const c = canvasFolder();
  const out = mkdtempSync(join(tmpdir(), 'diseno-'));
  try {
    await assert.rejects(run(c, out), (e) => e.code === 'SIN_APROBAR' && e.disponibles.includes('Main.dc.html'));
    await assert.rejects(run(c, out, { boards: ['Otro'] }), (e) => e.code === 'SIN_APROBAR');
    assert.deepEqual(snapshot(out), {});
  } finally {
    rmSync(c.from, { recursive: true, force: true });
    rmSync(out, { recursive: true, force: true });
  }
});

test('un índice con una ruta que escapa de la carpeta no importa nada', async () => {
  const c = canvasFolder();
  const out = mkdtempSync(join(tmpdir(), 'diseno-'));
  try {
    const index = JSON.parse(readFileSync(join(c.from, 'project/canvas.json'), 'utf8'));
    index.boards['../fuera.dc.html'] = { w: 100, h: 100 };
    c.put('project/canvas.json', JSON.stringify(index));
    await assert.rejects(run(c, out, { boards: ['Main'] }), (e) => e.code === 'RUTA');
    assert.deepEqual(snapshot(out), {});
  } finally {
    rmSync(c.from, { recursive: true, force: true });
    rmSync(out, { recursive: true, force: true });
  }
});

test('imágenes del almacén: si falta una se lista y no se escribe nada; si está, va a assets/', async () => {
  const c = canvasFolder({ 'Main.dc.html': 'Con logo' });
  c.put('project/Main.dc.html', board('Con logo').replace('<main>', `<main><img src="/_blob/${BLOB}">`));
  const out = mkdtempSync(join(tmpdir(), 'diseno-'));
  const blobs = mkdtempSync(join(tmpdir(), 'blobs-'));
  try {
    await assert.rejects(run(c, out, { boards: ['Main'], blobs }), (e) => e.code === 'FALTAN_BLOBS' && e.faltan[0] === BLOB);
    assert.deepEqual(snapshot(out), {});
    writeFileSync(join(blobs, `${BLOB}.png`), Buffer.from([137, 80, 78, 71]));
    await run(c, out, { boards: ['Main'], blobs });
    const view = readFileSync(join(out, 'Main.html'), 'utf8');
    assert.match(view, new RegExp(`src="assets/${BLOB}\\.png"`));
    assert.ok(existsSync(join(out, `assets/${BLOB}.png`)));
    assert.deepEqual(engineTraces(view.split('\n').slice(1).join('\n')), []);
  } finally {
    for (const d of [c.from, out, blobs]) rmSync(d, { recursive: true, force: true });
  }
});

test('sin motor ni pintor: guarda fuentes y manifiesto, sin vistas, y lo dice', async () => {
  const c = canvasFolder({ 'Main.dc.html': 'Solo fuente' });
  const out = mkdtempSync(join(tmpdir(), 'diseno-'));
  try {
    const r = await importCanvas({ from: c.from, url: URL_LIENZO, version: '1', feature: 'propuestas', out, boards: ['Main'] });
    assert.match(r.sin_vistas, /motor del lienzo/);
    assert.ok(existsSync(join(out, 'canvas/Main.dc.html')));
    assert.ok(!existsSync(join(out, 'Main.html')));
    assert.equal(JSON.parse(readFileSync(join(out, 'claude-design.json'), 'utf8')).artboards['Main.dc.html'].vista, null);
    // La próxima vez, con pintor, el artboard cuenta como cambiado y se congela.
    const { r: r2 } = await run(c, out, { version: '1' });
    assert.equal(r2.estados['Main.dc.html'], 'cambiado');
    assert.ok(existsSync(join(out, 'Main.html')));
  } finally {
    rmSync(c.from, { recursive: true, force: true });
    rmSync(out, { recursive: true, force: true });
  }
});

// ── Congelado real (Playwright + motor del lienzo) ───────────────────────

const pw = loadPlaywright(process.env.SPECBOX_PLAYWRIGHT);
const runtime = process.env.SPECBOX_DC_RUNTIME;
const real = { skip: pw && runtime && existsSync(runtime) ? false : 'sin Playwright o sin el motor del lienzo (SPECBOX_PLAYWRIGHT, SPECBOX_DC_RUNTIME)' };

test('real: congela un artboard con bucles y huecos en HTML sin motor que se ve igual sin JavaScript', real, async () => {
  const from = mkdtempSync(join(tmpdir(), 'lienzo-real-'));
  const out = mkdtempSync(join(tmpdir(), 'diseno-real-'));
  try {
    mkdirSync(join(from, 'project'), { recursive: true });
    writeFileSync(join(from, 'project/canvas.json'), JSON.stringify({ v: 3, title: 'Real', boards: { 'Main.dc.html': { x: 0, y: 0, w: 390, h: 600, title: 'Móvil' } }, order: ['Main.dc.html'] }));
    writeFileSync(join(from, 'project/Main.dc.html'), `<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>Lista</title><script src="./support.js"></script></head>
<body><x-dc><helmet><style>body{margin:0;font-family:system-ui}</style></helmet>
<div style="padding: 16px; display: flex; flex-direction: column; gap: 8px">
<h1 style="margin: 0; font-size: 24px">{{titulo}}</h1>
<sc-for list="{{filas}}" as="f" hint-placeholder-count="3"><div style="padding: 8px; background: #eef">{{f.nombre}} · {{f.importe}}</div></sc-for>
</div></x-dc>
<script type="text/x-dc" data-dc-script data-props='{"$preview":{"width":390,"height":600}}'>
class Component extends DCLogic { renderVals() { return { titulo: 'Propuestas', filas: [{ nombre: 'Taller Ríos', importe: '4.800 €' }, { nombre: 'Costa Luz', importe: '9.800 €' }] }; } }
</script></body></html>
`);
    const r = await importCanvas({ from, url: URL_LIENZO, version: 'real-1', feature: 'real', out, boards: ['Main'], runtime, playwright: process.env.SPECBOX_PLAYWRIGHT });
    assert.equal(r.estados['Main.dc.html'], 'nuevo', JSON.stringify(r));
    const view = readFileSync(join(out, 'Main.html'), 'utf8');
    assert.deepEqual(engineTraces(view.split('\n').slice(1).join('\n')), []);
    assert.match(view, /Taller Ríos · 4\.800 €/, 'los huecos quedan como texto, sin el <span> del motor');
    assert.match(view, /Costa Luz · 9\.800 €/);
    assert.doesNotMatch(view, /data-dc-tpl|sc-interp|sc-placeholder|x-dc\{/, 'sin lo que el motor añade para editar');
    assert.ok(view.indexOf('<meta charset="utf-8">') < 1024, 'el charset en el primer KB');
    // Abierta desde el disco, sin JavaScript y sin red, enseña lo mismo.
    const browser = await pw.chromium.launch({ channel: 'chrome' }).catch(() => pw.chromium.launch());
    try {
      const ctx = await browser.newContext({ viewport: { width: 390, height: 600 }, javaScriptEnabled: false, offline: true });
      const page = await ctx.newPage();
      await page.goto(`file://${join(out, 'Main.html')}`);
      const text = await page.textContent('body');
      assert.match(text, /Propuestas/);
      assert.match(text, /Costa Luz · 9\.800 €/);
    } finally {
      await browser.close();
    }
  } finally {
    rmSync(from, { recursive: true, force: true });
    rmSync(out, { recursive: true, force: true });
  }
});

// ── UC-9201: el esqueleto del lienzo de una feature ──────────────────────


const BRIEF = '# Brief: cola (Operate)\n\n## Quién la usa y para qué\nEl responsable.\n\nTiene que responder en segundos a:\n1. ¿Qué UC esperan mi aceptación?\n2. ¿Tienen evidencia?\n3. ¿Qué he aceptado hoy?\n\n## Pantalla a construir\n1. Cabecera\n';
const DS = { url: 'https://claude.ai/artifact/RdNh3zEkgd71XiR2TMR23M', namespace: 'TintaPrueba', version: '17-ab', title: 'Tinta prueba', files: ['tokens.json', 'tokens.css', 'components/bundle.css', 'components/bundle.js'] };

test('UC-9201: las tres preguntas salen del brief de /design-review', () => {
  assert.deepEqual(briefQuestions(BRIEF), ['¿Qué UC esperan mi aceptación?', '¿Tienen evidencia?', '¿Qué he aceptado hoy?']);
  assert.deepEqual(briefQuestions('# Brief sin preguntas'), []);
  assert.equal(dsFolder('TintaPrueba'), 'tintaprueba');
  assert.equal(dsFolder('Acme UI 2'), 'acme-ui-2');
});

test('UC-9201 AC-01: dos artboards por pantalla, a 1440 y a 390, y el primero es Main', () => {
  const r = scaffoldCanvas({
    title: 'Cola',
    screens: [{ slug: 'cola', titulo: 'Cola de aceptación', ucs: ['UC-1'], brief: 'cola.md' }, { slug: 'detalle', titulo: 'Detalle', ucs: ['UC-2'], brief: 'detalle.md' }],
    ds: DS,
    now: '2026-10-10T12:00:00Z',
    readBrief: (p) => (p === 'cola.md' ? BRIEF : null),
  });
  const b = r.canvas.boards;
  assert.deepEqual(r.canvas.order, ['Main.dc.html', 'cola-390.dc.html', 'detalle.dc.html', 'detalle-390.dc.html']);
  assert.deepEqual([b['Main.dc.html'].w, b['cola-390.dc.html'].w, b['detalle.dc.html'].w, b['detalle-390.dc.html'].w], [1440, 390, 1440, 390]);
  assert.equal(b['cola-390.dc.html'].x, 1440 + 80, '80 px entre artboards de una fila');
  assert.equal(b['cola-390.dc.html'].y, b['Main.dc.html'].y, 'la misma fila');
  assert.ok(b['detalle.dc.html'].y - (b['Main.dc.html'].y + 900) >= 120 + 223, 'filas separadas y sitio para el título');
  for (const k of Object.keys(b)) assert.equal(b[k].expand, 'fill', `${k} es una página fluida`);
  assert.deepEqual(r.canvas.createdOnFiles, { v: 1, at: '2026-10-10T12:00:00Z' });
  assert.equal(r.canvas.notes['titulo-cola'].kind, 'title1');
  assert.match(r.canvas.notes['brief-cola'].text, /1\. ¿Qué UC esperan mi aceptación\?/);
  assert.deepEqual(r.sinBrief, ['detalle'], 'una pantalla sin brief se dice');
  assert.equal(r.artboards.filter((a) => a.pantalla === 'cola').length, 2);
});

test('UC-9201 AC-02: el sistema del proyecto queda instalado y la cabecera lo carga en orden', () => {
  const r = scaffoldCanvas({ title: 'Cola', screens: [{ slug: 'cola' }], ds: DS, now: 'x' });
  assert.deepEqual(r.canvas.designSystems, [{ title: 'Tinta prueba', namespace: 'tintaprueba', artifact: DS.url, version: '17-ab', copiedAt: 'x' }]);
  assert.deepEqual(r.dsFiles['project/ds/tintaprueba/tokens.json'], { artifact: DS.url, path: 'project/tokens.json' });
  assert.ok(r.dsFiles['project/ds/tintaprueba/components/bundle.js']);
  assert.deepEqual(r.headLines, [
    '<script src="./support.js"></script>',
    '<link rel="stylesheet" href="ds/tintaprueba/tokens.css">',
    '<link rel="stylesheet" href="ds/tintaprueba/components/bundle.css">',
    '<script src="ds/tintaprueba/components/bundle.js"></script>',
  ]);
  assert.throws(() => scaffoldCanvas({ title: 'x', screens: [{ slug: 'a' }], ds: { ...DS, url: 'https://evil.example/artifact/x' } }), /no es la dirección de un sistema/);
  assert.throws(() => scaffoldCanvas({ title: 'x', screens: [{ slug: 'a' }], ds: { ...DS, files: ['../fuera.css'] } }), /no válido/);
  assert.throws(() => scaffoldCanvas({ title: 'x', screens: [{ slug: 'Con Espacio' }] }), /slug/);
  assert.throws(() => scaffoldCanvas({ title: 'x', screens: [{ slug: 'a' }, { slug: 'a' }] }), /repetida/);
});

test('UC-9201: scaffold apunta pantallas y UC en el manifiesto, y la importación lo conserva', async () => {
  const root = mkdtempSync(join(tmpdir(), 'scaffold-'));
  const out = mkdtempSync(join(tmpdir(), 'diseno-'));
  try {
    writeFileSync(join(out, 'cola.brief.md'), BRIEF);
    const r = scaffold({ feature: 'cola', title: 'Cola', url: URL_LIENZO, root, out, ds: DS, screens: JSON.stringify([{ slug: 'cola', titulo: 'Cola', ucs: ['UC-1'], brief: join(out, 'cola.brief.md') }]) });
    assert.ok(existsSync(join(root, 'project/canvas.json')));
    assert.deepEqual(r.sin_brief, []);
    const m = JSON.parse(readFileSync(join(out, 'claude-design.json'), 'utf8'));
    assert.equal(m.url, URL_LIENZO);
    assert.deepEqual(m.pantallas['Main.dc.html'].ucs, ['UC-1']);
    assert.equal(m.pantallas['cola-390.dc.html'].ancho, 390);
    assert.equal(m.artboards, undefined, 'nada se da por aprobado al crear el lienzo');
    assert.equal(status({ feature: 'cola', out }).pantallas['Main.dc.html'].pantalla, 'cola');
    // Otro lienzo para la misma feature: no.
    assert.throws(() => scaffold({ feature: 'cola', title: 'Cola', url: 'https://claude.ai/artifact/otro', root, out, screens: '[{"slug":"cola"}]' }), /otro lienzo/);
  } finally {
    rmSync(root, { recursive: true, force: true });
    rmSync(out, { recursive: true, force: true });
  }
});

// ── UC-9201: cada estado de una pantalla, congelado aparte ───────────────

test('UC-9201: --states congela cada estado declarado en el artboard como vista aparte', async () => {
  assert.deepEqual(parseStates('estado=vacía, cargando,error'), { prop: 'estado', values: ['vacía', 'cargando', 'error'] });
  assert.throws(() => parseStates('sin-igual'), /no válido/);
  assert.equal(stateSlug('vacía'), 'vacia');
  assert.equal(stateSlug('sin aceptar'), 'sin-aceptar');
  const conEstado = board('Cola').replace("data-props='{}'", `data-props='{"estado":{"editor":"enum","options":["con datos","vacía"],"default":"con datos"}}'`);
  assert.equal(declaresProp(conEstado, 'estado'), true);
  assert.equal(declaresProp(board('Cola'), 'estado'), false);
  const w = stateWrapper(conEstado, 'Main.dc.html', 'estado', 'vacía');
  assert.match(w, /<dc-import name="Main" estado="vacía"/);
  assert.match(w, /<script src="\.\/support\.js"><\/script>/, 'misma cabecera que el original');

  const c = canvasFolder({ 'Main.dc.html': 'Cola', 'Movil.dc.html': 'Sin estados' });
  c.put('project/Main.dc.html', conEstado);
  const out = mkdtempSync(join(tmpdir(), 'diseno-'));
  const rendered = [];
  const renderer = {
    async render(name) {
      rendered.push(name);
      const src = readFileSync(join(c.from, 'project', name), 'utf8');
      const estado = src.match(/estado="([^"]+)"/)?.[1] || 'por defecto';
      return { html: `<!doctype html>\n<html><head></head><body><main>${estado}</main></body></html>`, alto: 600 };
    },
    async close() {},
  };
  try {
    const r = await importCanvas({ from: c.from, url: URL_LIENZO, version: '1', feature: 'cola', out, boards: ['Main', 'Movil'], renderer, fetchImpl: fakeFetch().impl, states: 'estado=vacía,error' });
    assert.ok(r.escritos.includes('Main@vacia.html') && r.escritos.includes('Main@error.html'));
    assert.ok(!r.escritos.some((e) => e.startsWith('Movil@')), 'un artboard sin esa opción no tiene estados');
    assert.match(readFileSync(join(out, 'Main@vacia.html'), 'utf8'), /<main>vacía<\/main>/);
    assert.ok(readFileSync(join(out, 'Main@vacia.html'), 'utf8').split('\n')[0].includes('artboard=Main.dc.html · estado=vacía'));
    const m = JSON.parse(readFileSync(join(out, 'claude-design.json'), 'utf8'));
    assert.deepEqual(m.artboards['Main.dc.html'].estados, { 'vacía': 'Main@vacia.html', error: 'Main@error.html' });
    assert.ok(!readdirSync(join(c.from, 'project')).some((f) => f.startsWith('_estado-')), 'el artboard auxiliar se borra');
    assert.match(readFileSync(join(out, 'canvas.html'), 'utf8'), /Estados: <a href="Main@vacia\.html">vacía<\/a>/);
    // Pedir otros estados cambia lo que se congela: no cuenta como «igual».
    const again = await importCanvas({ from: c.from, url: URL_LIENZO, version: '1', feature: 'cola', out, renderer, fetchImpl: fakeFetch().impl, states: 'estado=vacía' });
    assert.equal(again.estados['Main.dc.html'], 'cambiado');
  } finally {
    rmSync(c.from, { recursive: true, force: true });
    rmSync(out, { recursive: true, force: true });
  }
});
