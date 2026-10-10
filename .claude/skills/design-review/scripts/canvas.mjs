#!/usr/bin/env node
// /design-review import (US-92 · UC-9202): trae al proyecto los artboards aprobados de un lienzo de
// Claude Design, con su origen.
//
// Uso:
//   node canvas.mjs import --from <carpeta leída> --url <lienzo> --version <id> --feature <f>
//                   [--boards Main,Movil] [--runtime <dc-runtime.js>] [--blobs <carpeta>]
//                   [--out doc/design/<f>] [--playwright <ruta>]
//   node canvas.mjs status --feature <f> [--out doc/design/<f>]
//
// `--from` es la carpeta donde la herramienta Artifact guardó lo leído del lienzo (`project/canvas.json`,
// los `project/*.dc.html`, `project/ds/**` y `artifact-type/dc-runtime.js`). El script no habla con
// claude.ai: lee el disco.
//
// Por cada artboard aprobado deja en la carpeta de diseño de la feature:
//   canvas/<artboard>.dc.html  la fuente, tal como está en el lienzo;
//   <artboard>.html            la vista congelada: el DOM ya pintado, sin scripts ni motor, con las
//                              hojas del sistema en línea, las tipografías en fonts/ y las imágenes en
//                              assets/. Se abre sin conexión y es la entrada del design-to-code;
//   canvas.html                la vista del lienzo: cabecera con dirección y versión, y cada artboard a
//                              su ancho real;
//   claude-design.json         el manifiesto: lienzo, versión y huella de cada artboard.
//
// Para pintar usa el motor que sirve el propio lienzo (`artifact-type/dc-runtime.js`, en su versión) en
// el lugar de `support.js`, con el Playwright del proyecto. El motor solo se usa para pintar: no se copia
// al proyecto. Si el lienzo y los artboards aprobados no han cambiado desde la última importación, no se
// escribe nada.
//
// Salida: 0 hecho o sin cambios · 2 sin Playwright o sin motor (se guardan fuentes y manifiesto, sin
// vistas) · 3 faltan imágenes del almacén del lienzo (se listan; léelas y repite) · 4 artboards sin nombrar
// o que no están en el lienzo · 1 error.

import { createHash } from 'node:crypto';
import { createServer } from 'node:http';
import { existsSync, mkdirSync, readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { basename, dirname, extname, isAbsolute, join, relative, resolve, sep } from 'node:path';
import { pathToFileURL } from 'node:url';

import { launch, loadPlaywright, settle } from './verify.mjs';

export const MANIFEST = 'claude-design.json';
export const BANNER_MARK = 'specbox:design-role=candidate';
const NOTE = 'Diseño candidato de Claude Design: sirve para decidir disposición, jerarquía y flujo. '
  + 'Nunca es fuente de producción: colores, tipografía, radios y estados salen de los tokens del sistema '
  + 'del proyecto, y el código no copia valores de este diseño.';

// Restos del motor del lienzo. Ni la vista congelada ni el código que sale de ella pueden llevarlos.
export const ENGINE_TRACES = [
  ['support.js', /\bsupport\.js\b/],
  ['<x-dc>', /<x-dc[\s>]/i],
  ['DCLogic', /\bDCLogic\b/],
  ['<sc-for>', /<sc-for[\s>]/i],
  ['<sc-if>', /<sc-if[\s>]/i],
  ['<dc-import>', /<dc-import[\s>]/i],
  ['<x-import>', /<x-import[\s>]/i],
  ['/_blob/', /\/_blob\/[0-9a-f]{8,}/],
];

export function engineTraces(text) {
  return ENGINE_TRACES.filter(([, re]) => re.test(text)).map(([name]) => name);
}

// ── Funciones puras ──────────────────────────────────────────────────────

// Una ruta de artboard leída del índice: si trae `..`, `\` o `/` inicial no nombra un fichero.
export function boardPathError(p) {
  if (typeof p !== 'string' || !p) return 'vacía';
  if (p.startsWith('/')) return 'empieza por /';
  if (p.includes('\\')) return 'lleva \\';
  if (p.split('/').some((s) => s === '..' || s === '.')) return 'lleva .. o .';
  if (!p.endsWith('.dc.html')) return 'no termina en .dc.html';
  if (!p.split('/').every((s) => /^[A-Za-z0-9_][A-Za-z0-9_.-]*$/.test(s))) return 'segmento no válido';
  return null;
}

// `Main` o `Main.dc.html` → `Main.dc.html`.
export function boardKey(name) {
  return name.endsWith('.dc.html') ? name : `${name}.dc.html`;
}

// `Main.dc.html` → `Main.html`; `flujo/Pago.dc.html` → `flujo-Pago.html`.
export function viewName(board) {
  return `${board.replace(/\.dc\.html$/, '').split('/').join('-')}.html`;
}

export const sha256 = (data) => createHash('sha256').update(data).digest('hex');

// Lo que cambia la pantalla: su fuente, su marco en el lienzo y la copia del sistema de diseño.
export function fingerprint({ source, entry = {}, dsHash = '' }) {
  const frame = { w: entry.w, h: entry.h, expand: entry.expand ?? null };
  return sha256(`${sha256(source)}|${JSON.stringify(frame)}|${dsHash}`);
}

// Ids de imágenes del almacén del lienzo (`/_blob/<id>`).
export function blobRefs(text) {
  return [...new Set([...text.matchAll(/\/_blob\/([0-9a-f]{32})/g)].map((m) => m[1]))];
}

// Qué pasa con cada artboard. `exists(path)` dice si un fichero ya está en la carpeta de diseño.
export function planImport({ boards, approved, prints, previous, exists = () => true }) {
  const prev = previous?.artboards || {};
  const estados = {};
  for (const b of approved) {
    const before = prev[b];
    if (!before) estados[b] = 'nuevo';
    else if (before.huella !== prints[b] || !before.vista || !exists(before.fuente) || !exists(before.vista)) estados[b] = 'cambiado';
    else estados[b] = 'igual';
  }
  const retirados = Object.keys(prev).filter((b) => !(b in boards));
  for (const b of retirados) estados[b] = 'retirado';
  const sinCambios = approved.every((b) => estados[b] === 'igual');
  return { estados, retirados, sinCambios };
}

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

export function banner({ url, version, board, importado }) {
  const clean = (s) => String(s).replace(/--/g, '—');
  return `<!-- ${BANNER_MARK} · ${NOTE} · proveedor=claude_design · lienzo=${clean(url)} · version=${clean(version)} · artboard=${clean(board)} · importado=${importado} -->`;
}

// Primera línea con el origen y dos metas para quien lo lea con una herramienta.
export function stampView(html, { url, version, board, importado }) {
  // El charset va el primero del <head>: abierta desde el disco, una vista con él más allá del primer
  // KB pierde las tildes.
  const body = html.replace(/^<!doctype html>\s*/i, '').replace(/<meta\s+charset=["']?[\w-]+["']?\s*\/?>/gi, '');
  // La fuente del lienzo no trae viewport: sin él, un navegador móvil (y verify a 390) maquetaría a 980.
  const viewport = /<meta[^>]+name=["']?viewport/i.test(body) ? '' : '<meta name="viewport" content="width=device-width, initial-scale=1">';
  const metas = `<meta charset="utf-8">${viewport}<meta name="specbox:canvas" content="${esc(url)}"><meta name="specbox:canvas-version" content="${esc(version)}"><meta name="specbox:artboard" content="${esc(board)}">`;
  const withMeta = /<head[^>]*>/i.test(body) ? body.replace(/<head([^>]*)>/i, `<head$1>${metas}`) : `${metas}${body}`;
  return `${banner({ url, version, board, importado })}\n<!doctype html>\n${withMeta}`;
}

// La vista del lienzo: cabecera con dirección y versión, y cada artboard congelado a su ancho real.
export function canvasView(manifest) {
  const boards = Object.entries(manifest.artboards || {}).filter(([, a]) => a.vista && !a.retirado);
  const fecha = (manifest.importado || '').replace('T', ' ').replace(/\.\d+Z$|Z$/, ' UTC');
  const items = boards.map(([b, a]) => `
<section>
  <h2>${esc(a.titulo || b)} <span>${String(a.titulo || '').includes(String(a.ancho)) ? '' : `${a.ancho} px · `}${esc(b)}</span></h2>
  <div class="marco"><iframe src="${esc(a.vista)}" title="${esc(a.titulo || b)}" width="${a.ancho}" height="${a.alto || 900}" loading="lazy"></iframe></div>
</section>`).join('');
  return `<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="specbox:canvas" content="${esc(manifest.url)}">
<meta name="specbox:canvas-version" content="${esc(manifest.lienzo_version)}">
<title>${esc(manifest.titulo || 'Lienzo')} · Claude Design</title>
<style>
body{margin:0;background:#f3f3f1;color:#1b1b1a;font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
header{padding:24px 32px;background:#fff;border-bottom:1px solid #d9d9d5}
h1{margin:0 0 12px;font-size:22px;line-height:1.25}
dl{display:grid;grid-template-columns:max-content minmax(0,1fr);gap:4px 16px;margin:0}
dt{color:#5c5c58}dd{margin:0;overflow-wrap:anywhere;font-variant-numeric:tabular-nums}
a{color:#0b5c8a}
header p{margin:12px 0 0;color:#5c5c58;max-width:72ch}
main{padding:24px 32px;display:flex;flex-direction:column;gap:32px}
h2{margin:0 0 8px;font-size:16px}h2 span{font-weight:400;color:#5c5c58;font-size:14px}
.marco{overflow-x:auto;max-width:100%}
iframe{display:block;border:0;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.12)}
</style>
</head>
<body>
<header>
  <h1>${esc(manifest.titulo || 'Lienzo de Claude Design')}</h1>
  <dl>
    <dt>Lienzo</dt><dd><a href="${esc(manifest.url)}">${esc(manifest.url)}</a></dd>
    <dt>Versión</dt><dd>${esc(manifest.lienzo_version)}</dd>
    <dt>Importado</dt><dd>${esc(fecha)}</dd>
  </dl>
  <p>${esc(NOTE)}</p>
</header>
<main>${items}
</main>
</body>
</html>
`;
}

// ── Tipografías sin conexión ─────────────────────────────────────────────

const CHROME_UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36';
const KEEP_SUBSETS = new Set(['latin', 'latin-ext']);

// Hoja de Google Fonts → la misma hoja con las fuentes en data: (solo latin y latin-ext, que cubren el
// español, «», € y los símbolos tipográficos). Sin red, devuelve null y la vista conserva el enlace.
export async function offlineFontCss(cssUrl, fetchImpl = fetch) {
  let css;
  try {
    const res = await fetchImpl(cssUrl, { headers: { 'User-Agent': CHROME_UA } });
    if (!res.ok) return null;
    css = await res.text();
  } catch { return null; }
  const blocks = [...css.matchAll(/\/\*\s*([a-z-]+)\s*\*\/\s*(@font-face\s*{[^}]*})/g)];
  const chosen = blocks.length ? blocks.filter((m) => KEEP_SUBSETS.has(m[1])).map((m) => m[2]) : [...css.matchAll(/@font-face\s*{[^}]*}/g)].map((m) => m[0]);
  const out = [];
  for (const block of chosen) {
    const m = block.match(/url\((https:[^)]+)\)/);
    if (!m) continue;
    try {
      const res = await fetchImpl(m[1]);
      if (!res.ok) return null;
      const b64 = Buffer.from(await res.arrayBuffer()).toString('base64');
      const fmt = m[1].endsWith('.woff2') ? 'woff2' : m[1].endsWith('.woff') ? 'woff' : 'truetype';
      out.push(block.replace(m[0], `url(data:font/${fmt};base64,${b64})`));
    } catch { return null; }
  }
  return out.length ? `/* ${cssUrl} — sin conexión (latin y latin-ext) */\n${out.join('\n')}\n` : null;
}

const GOOGLE_FONTS = /https:\/\/fonts\.googleapis\.com\/css2?\?[^"')\s]+/g;

// ── Congelado ────────────────────────────────────────────────────────────

const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.gif': 'image/gif', '.webp': 'image/webp', '.woff2': 'font/woff2', '.woff': 'font/woff', '.ttf': 'font/ttf', '.otf': 'font/otf' };

export function findBlob(dir, id) {
  if (!dir || !existsSync(dir)) return null;
  const hit = readdirSync(dir).find((f) => f === id || f.startsWith(`${id}.`));
  return hit ? join(dir, hit) : null;
}

// Servidor local: la carpeta `project/` del lienzo, el motor en lugar de `support.js` y las imágenes.
function serveCanvas({ projectDir, runtime, blobs }) {
  const server = createServer((req, res) => {
    const path = decodeURIComponent(new URL(req.url, 'http://x').pathname);
    let file = null;
    if (path.endsWith('/support.js')) file = runtime;
    else if (path.startsWith('/_blob/')) file = findBlob(blobs, path.slice(7).split('.')[0]);
    else {
      const f = resolve(projectDir, `.${path}`);
      if (f.startsWith(projectDir + sep) && existsSync(f) && statSync(f).isFile()) file = f;
    }
    if (!file) { res.writeHead(404); res.end(); return; }
    res.writeHead(200, { 'Content-Type': TYPES[extname(file).toLowerCase()] || 'application/octet-stream' });
    res.end(readFileSync(file));
  });
  return new Promise((ok) => server.listen(0, '127.0.0.1', () => ok(server)));
}

// En la página: el documento ya pintado, sin scripts ni lo que el motor añade para editar (su hoja
// para el modo streaming, las marcas de plantilla y un <span> en cada hueco). Un hueco sin valor se
// conserva y se cuenta, para avisar.
function serialize() {
  const d = document.documentElement.cloneNode(true);
  d.querySelectorAll('script, link[rel="modulepreload"], link[rel="preload"]').forEach((n) => n.remove());
  const missing = d.querySelectorAll('.sc-interp.sc-missing, .sc-interp.sc-unresolved, .sc-placeholder').length;
  d.querySelectorAll('style').forEach((st) => {
    const css = st.textContent.trim();
    if (/^x-dc\s*\{\s*display:\s*none/.test(css) || (!missing && css.includes('.sc-placeholder{'))) st.remove();
  });
  d.querySelectorAll('span.sc-interp:not(.sc-missing):not(.sc-unresolved)').forEach((sp) => {
    if (!sp.attributes.length || [...sp.attributes].every((a) => a.name === 'class')) sp.replaceWith(...sp.childNodes);
  });
  d.querySelectorAll('[data-dc-tpl]').forEach((n) => n.removeAttribute('data-dc-tpl'));
  return { html: `<!doctype html>\n${d.outerHTML}`, alto: document.documentElement.scrollHeight, huecos_sin_valor: missing };
}

export async function makeRenderer({ projectDir, runtime, blobs, playwright }) {
  const pw = loadPlaywright(playwright);
  if (!pw) {
    const err = new Error('El proyecto no tiene Playwright: se guardan las fuentes y el manifiesto, sin vistas congeladas.');
    err.code = 'NO_PLAYWRIGHT';
    throw err;
  }
  const server = await serveCanvas({ projectDir, runtime, blobs });
  const base = `http://127.0.0.1:${server.address().port}`;
  const browser = await launch(pw);
  return {
    async render(board, entry) {
      // Como lo pinta el lienzo: un iframe de su ancho, sin emulación de móvil (a 390 px y sin
      // etiqueta viewport, la emulación maquetaría a 980).
      const w = entry.w || 1440;
      const page = await browser.newPage({ viewport: { width: w, height: 900 }, deviceScaleFactor: 1 });
      try {
        await page.goto(`${base}/${board}`, { waitUntil: 'networkidle', timeout: 60000 });
        await page.waitForFunction(() => !document.querySelector('x-dc'), null, { timeout: 15000 });
        await page.evaluate(settle);
        return await page.evaluate(serialize);
      } finally {
        await page.close();
      }
    },
    async close() {
      await browser.close();
      await new Promise((ok) => server.close(ok));
    },
  };
}

// Las hojas locales van en línea; Google Fonts, a fonts/<huella>.css con las fuentes dentro; las
// imágenes del almacén, a assets/.
// Escribe solo si el contenido es otro: una reimportación no toca lo que no cambió.
function writeIfChanged(file, data, escritos, rel) {
  if (existsSync(file) && Buffer.compare(readFileSync(file), Buffer.from(data)) === 0) return;
  mkdirSync(dirname(file), { recursive: true });
  writeFileSync(file, data);
  escritos?.push(rel);
}

export async function localize(html, { boardDir, projectDir, outDir, blobs, fetchImpl = fetch, fontCache = new Map(), avisos = [], escritos }) {
  let out = html.replace(/<link\b[^>]*\brel=["']?stylesheet["']?[^>]*>/gi, (tag) => {
    const href = tag.match(/\bhref=["']([^"']+)["']/i)?.[1];
    if (!href || /^(https?:|data:)/.test(href)) return tag;
    const file = resolve(boardDir, href);
    if (!file.startsWith(projectDir + sep) || !existsSync(file)) { avisos.push(`hoja no encontrada: ${href}`); return ''; }
    return `<style data-specbox-from="${esc(href)}">\n${readFileSync(file, 'utf8')}\n</style>`;
  });
  for (const cssUrl of new Set((out.match(GOOGLE_FONTS) || []).map((u) => u.replace(/&amp;/g, '&')))) {
    if (!fontCache.has(cssUrl)) {
      const css = await offlineFontCss(cssUrl, fetchImpl);
      const name = css ? `fonts/${sha256(cssUrl).slice(0, 12)}.css` : null;
      if (css) writeIfChanged(join(outDir, name), css, escritos, name);
      else avisos.push(`sin conexión para ${cssUrl}: la vista usa la tipografía de reserva cuando no hay red`);
      fontCache.set(cssUrl, name);
    }
    const local = fontCache.get(cssUrl);
    if (local) {
      const htmlUrl = cssUrl.replace(/&/g, '&amp;');
      out = out.split(htmlUrl).join(local).split(cssUrl).join(local);
    }
  }
  for (const id of blobRefs(out)) {
    const file = findBlob(blobs, id);
    if (!file) continue;
    const name = `assets/${basename(file)}`;
    writeIfChanged(join(outDir, name), readFileSync(file), escritos, name);
    out = out.replace(new RegExp(`/_blob/${id}(\\.[a-z0-9]+)?`, 'g'), name);
  }
  return out;
}

// ── Importación ──────────────────────────────────────────────────────────

function readJson(file) {
  try { return JSON.parse(readFileSync(file, 'utf8')); } catch { return null; }
}

function filesUnder(dir) {
  if (!existsSync(dir)) return [];
  const out = [];
  const walk = (d) => {
    for (const e of readdirSync(d, { withFileTypes: true })) {
      const f = join(d, e.name);
      if (e.isDirectory()) walk(f); else if (e.isFile()) out.push(f);
    }
  };
  walk(dir);
  return out.sort();
}

export function fail(message, code, extra = {}) {
  const err = new Error(message);
  err.code = code;
  Object.assign(err, extra);
  return err;
}

export async function importCanvas({ from, url, version, feature, boards, runtime, blobs, out, playwright, renderer, fetchImpl, now = () => new Date().toISOString() }) {
  if (!from || !url || !version || !feature) throw fail('Faltan --from, --url, --version o --feature', 'USO');
  const projectDir = resolve(from, 'project');
  const canvas = readJson(join(projectDir, 'canvas.json'));
  if (!canvas || typeof canvas.boards !== 'object') throw fail(`No hay un project/canvas.json legible en ${from}`, 'USO');
  for (const b of Object.keys(canvas.boards)) {
    const why = boardPathError(b);
    if (why) throw fail(`El índice del lienzo nombra «${b}» (${why}): no se importa nada.`, 'RUTA');
  }
  const outDir = resolve(out || join('doc', 'design', feature));
  const manifestFile = join(outDir, MANIFEST);
  const previous = readJson(manifestFile);
  if (previous?.url && previous.url !== url) throw fail(`${MANIFEST} es de otro lienzo (${previous.url}).`, 'USO');

  const approved = (boards && boards.length ? boards.map(boardKey) : Object.keys(previous?.artboards || {}).filter((b) => b in canvas.boards));
  const disponibles = Object.keys(canvas.boards);
  if (!approved.length) throw fail('Nombra los artboards aprobados.', 'SIN_APROBAR', { disponibles });
  const ausentes = approved.filter((b) => !(b in canvas.boards));
  if (ausentes.length) throw fail(`No están en el lienzo: ${ausentes.join(', ')}`, 'SIN_APROBAR', { disponibles });

  const sources = Object.fromEntries(approved.map((b) => {
    const f = join(projectDir, b);
    if (!existsSync(f)) throw fail(`Falta ${b} en ${from}: léelo del lienzo con los demás ficheros.`, 'USO');
    return [b, readFileSync(f, 'utf8')];
  }));
  const dsFiles = filesUnder(join(projectDir, 'ds'));
  const dsHash = sha256(dsFiles.map((f) => `${relative(projectDir, f)}:${sha256(readFileSync(f))}`).join('\n'));
  const prints = Object.fromEntries(approved.map((b) => [b, fingerprint({ source: sources[b], entry: canvas.boards[b], dsHash })]));
  const plan = planImport({ boards: canvas.boards, approved, prints, previous, exists: (p) => p && existsSync(join(outDir, p)) });
  const result = { lienzo: url, version, version_anterior: previous?.lienzo_version ?? null, carpeta: outDir, estados: plan.estados, escritos: [], avisos: [] };
  if (plan.sinCambios) {
    result.sin_cambios = true;
    return result;
  }

  // Imágenes del almacén: sin ellas la vista sale rota. Se listan y no se escribe nada.
  const blobDir = blobs || from;
  const needed = blobRefs([...approved.filter((b) => plan.estados[b] !== 'igual').map((b) => sources[b]), ...dsFiles.filter((f) => f.endsWith('.css')).map((f) => readFileSync(f, 'utf8'))].join('\n'));
  const faltan = needed.filter((id) => !findBlob(blobDir, id));
  if (faltan.length) throw fail(`Faltan ${faltan.length} imágenes del almacén del lienzo.`, 'FALTAN_BLOBS', { faltan });

  const runtimeFile = runtime || join(from, 'artifact-type', 'dc-runtime.js');
  const stamp = now();
  const manifest = {
    version: 1,
    proveedor: 'claude_design',
    ...(previous || {}),
    url,
    titulo: canvas.title || previous?.titulo || feature,
    lienzo_version: version,
    importado: stamp,
    artboards: { ...(previous?.artboards || {}) },
  };
  for (const b of plan.retirados) manifest.artboards[b] = { ...manifest.artboards[b], retirado: true };

  let render = renderer;
  let sinVistas = null;
  if (!render) {
    if (!existsSync(runtimeFile)) sinVistas = `No está el motor del lienzo (${relative(process.cwd(), runtimeFile)}): léelo del lienzo (artifact-type/dc-runtime.js).`;
    else {
      try {
        render = await makeRenderer({ projectDir, runtime: runtimeFile, blobs: blobDir, playwright });
      } catch (e) {
        if (e.code !== 'NO_PLAYWRIGHT') throw e;
        sinVistas = e.message;
      }
    }
  }

  const write = (rel, data) => {
    const f = join(outDir, rel);
    mkdirSync(dirname(f), { recursive: true });
    writeFileSync(f, data);
    result.escritos.push(rel);
  };
  const fontCache = new Map();
  try {
    for (const b of approved) {
      if (plan.estados[b] === 'igual') continue;
      const entry = canvas.boards[b];
      const fuente = `canvas/${b}`;
      write(fuente, sources[b]);
      const record = { ...(manifest.artboards[b] || {}), fuente, titulo: entry.title || manifest.artboards[b]?.titulo || null, ancho: entry.w, huella: prints[b], lienzo_version: version, importado: stamp, retirado: undefined };
      if (render) {
        const { html, alto, huecos_sin_valor: huecos } = await render.render(b, entry);
        if (huecos) result.avisos.push(`${b}: ${huecos} huecos sin valor en el lienzo; la vista los enseña vacíos`);
        const boardDir = dirname(join(projectDir, b));
        const local = await localize(html, { boardDir, projectDir, outDir, blobs: blobDir, fetchImpl, fontCache, avisos: result.avisos, escritos: result.escritos });
        const vista = viewName(b);
        const final = stampView(local, { url, version, board: b, importado: stamp });
        const restos = engineTraces(final.split('\n').slice(1).join('\n'));
        if (restos.length) result.avisos.push(`${vista} conserva restos del motor: ${restos.join(', ')}`);
        write(vista, final);
        Object.assign(record, { vista, alto, huella_vista: sha256(final) });
      } else {
        Object.assign(record, { vista: null, alto: null, huella_vista: null });
      }
      manifest.artboards[b] = JSON.parse(JSON.stringify(record));
    }
  } finally {
    if (render && !renderer) await render.close();
  }
  if (render) write('canvas.html', canvasView(manifest));
  write(MANIFEST, `${JSON.stringify(manifest, null, 2)}\n`);
  if (sinVistas) {
    result.sin_vistas = sinVistas;
  }
  return result;
}

export function status({ feature, out }) {
  const outDir = resolve(out || join('doc', 'design', feature));
  const manifest = readJson(join(outDir, MANIFEST));
  if (!manifest) return null;
  return {
    url: manifest.url,
    titulo: manifest.titulo,
    lienzo_version: manifest.lienzo_version,
    importado: manifest.importado,
    artboards: Object.fromEntries(Object.entries(manifest.artboards || {}).map(([b, a]) => [b, {
      vista: a.vista, ancho: a.ancho, importado: a.importado, retirado: !!a.retirado, pantalla: a.pantalla ?? null, ucs: a.ucs ?? [],
    }])),
  };
}

// ── CLI ──────────────────────────────────────────────────────────────────

function parseArgs(argv) {
  const args = { cmd: argv[0] };
  for (let i = 1; i < argv.length; i++) {
    const a = argv[i];
    const next = () => argv[++i];
    if (a === '--boards') args.boards = next().split(',').map((s) => s.trim()).filter(Boolean);
    else if (a.startsWith('--')) args[a.slice(2)] = next();
  }
  return args;
}

const EXIT = { NO_PLAYWRIGHT: 2, FALTAN_BLOBS: 3, SIN_APROBAR: 4 };

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.cmd === 'status') {
    if (!args.feature) { console.error('Uso: node canvas.mjs status --feature <f> [--out doc/design/<f>]'); process.exit(1); }
    const s = status(args);
    console.log(JSON.stringify(s ?? { error: `No hay ${MANIFEST} en doc/design/${args.feature}` }, null, 2));
    process.exit(s ? 0 : 1);
  }
  if (args.cmd !== 'import') {
    console.error('Uso: node canvas.mjs import --from <carpeta> --url <lienzo> --version <id> --feature <f> [--boards a,b] [--runtime f] [--blobs d] [--out d]\n     node canvas.mjs status --feature <f>');
    process.exit(1);
  }
  for (const k of ['from', 'runtime', 'blobs', 'out', 'playwright']) if (args[k] && !isAbsolute(args[k])) args[k] = resolve(args[k]);
  try {
    const r = await importCanvas(args);
    console.log(JSON.stringify(r, null, 2));
    if (r.sin_vistas) { console.error(`import: ${r.sin_vistas}`); process.exit(2); }
  } catch (e) {
    console.error(`import: ${e.message}`);
    if (e.disponibles) console.error(`artboards del lienzo: ${e.disponibles.join(', ')}`);
    if (e.faltan) console.log(JSON.stringify({ faltan_blobs: e.faltan }, null, 2));
    process.exit(EXIT[e.code] || 1);
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) main();
