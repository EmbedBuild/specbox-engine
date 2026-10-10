#!/usr/bin/env node
// /design-review verify (US-91 · UC-9101): mide una pantalla y aplica reglas deterministas.
//
// Uso:
//   node verify.mjs <fichero.html | URL> --out <dir> [--name <pantalla>] [--widths 1440,390]
//                   [--previous <verify.json>] [--sources <brief.md,prd.md>] [--playwright <ruta>]
//
// No trae dependencias: usa el Playwright que el proyecto ya tiene para sus e2e (`playwright`,
// `@playwright/test` o `playwright-core`). Prueba primero el Chrome del sistema y después el
// Chromium de Playwright. Escribe <name>-<ancho>.png y <name>-verify.json en --out.
//
// Salida: 0 informe escrito · 2 el proyecto no tiene Playwright (no se instala nada) · 1 error.

import { createRequire } from 'node:module';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { isAbsolute, join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

export const RULES = [
  'desbordamiento', 'texto-degradado', 'borde-lateral', 'eyebrow', 'transition-all',
  'emoji-icono', 'contraste', 'area-pulsacion',
];

// ── Funciones puras (también las usan los tests) ─────────────────────────

export function relativeLuminance([r, g, b]) {
  const lin = (c) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

export function contrastRatio(fg, bg) {
  const a = relativeLuminance(fg);
  const b = relativeLuminance(bg);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}

const EMOJI_RE = /\p{Extended_Pictographic}/u;
const NOT_EMOJI = new Set(['©', '®', '™']);

export function hasEmoji(text) {
  return [...String(text)].some((ch) => !NOT_EMOJI.has(ch) && EMOJI_RE.test(ch));
}

/**
 * Línea (1-based) del fichero fuente donde está el elemento, o null. Busca desde `<body>` (el
 * `<title>` y los estilos no son el elemento) y de lo más preciso a lo menos: id, etiqueta con clase
 * y texto, etiqueta con clase, etiqueta con texto, texto y clase. Si el elemento se repite o lo pinta
 * un script, es la primera línea que casa: una pista para el revisor, no una prueba.
 */
export function findSourceLine(lines, hint) {
  if (!lines || !hint) return null;
  const body = lines.findIndex((l) => /<body[\s>]/i.test(l));
  const start = body >= 0 ? body : 0;
  const first = hint.className ? hint.className.trim().split(/\s+/)[0] : '';
  const cls = first ? new RegExp(`class=["'][^"']*(?<![\\w-])${escapeRe(first)}(?![\\w-])`) : null;
  const tag = (l) => l.includes(`<${hint.tag}`) && new RegExp(`<${hint.tag}[\\s>/]`).test(l);
  const snippet = hint.text && hint.text.length >= 4 ? hint.text.slice(0, 16) : null;
  const tries = [];
  if (hint.id) tries.push((l) => l.includes(`id="${hint.id}"`) || l.includes(`id='${hint.id}'`));
  if (cls && snippet) tries.push((l) => tag(l) && cls.test(l) && l.includes(snippet));
  if (cls) tries.push((l) => tag(l) && cls.test(l));
  if (snippet) tries.push((l) => tag(l) && l.includes(snippet));
  if (snippet) tries.push((l) => l.includes(snippet));
  if (cls) tries.push((l) => cls.test(l));
  for (const test of tries) {
    const idx = lines.findIndex((l, i) => i >= start && test(l));
    if (idx >= 0) return idx + 1;
  }
  return null;
}

function escapeRe(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/** Cifras visibles normalizadas («4.800 €», «81 %», «9 min» → «4800€», «81%», «9»). */
export function numbersIn(text) {
  const out = new Set();
  for (const m of String(text).matchAll(/\d[\d.,]*(?:\s?[%€])?/g)) {
    const token = m[0].replace(/\s/g, '').replace(/[.,](?=\d{3}\b)/g, '').replace(/[.,]$/, '');
    if (token) out.add(token);
  }
  return [...out];
}

/** Cifras que aparecen después de una corrección y no están ni antes ni en las fuentes. */
export function numbersWithoutSource(previous, current, sourcesText) {
  const before = new Set(previous);
  const sources = new Set(numbersIn(sourcesText));
  return current.filter((n) => !before.has(n) && !sources.has(n) && !sources.has(n.replace(/[%€]$/, '')));
}

// ── Lo que se ejecuta dentro de la página (autocontenido) ────────────────

function inPage({ width, tap }) {
  const MAX = 40;
  const out = [];
  // Lo que mide 1 px o menos (sr-only, entradas ocultas con clip) no se ve: no cuenta.
  const visible = (el) => {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return r.width > 1 && r.height > 1 && cs.visibility !== 'hidden' && cs.display !== 'none' && parseFloat(cs.opacity) > 0.05;
  };
  const selector = (el) => {
    const parts = [];
    let node = el;
    for (let depth = 0; node && node.nodeType === 1 && node !== document.body && depth < 4; depth++) {
      let part = node.tagName.toLowerCase();
      if (node.id) { parts.unshift(`${part}#${node.id}`); break; }
      const cls = typeof node.className === 'string' ? node.className.trim().split(/\s+/)[0] : '';
      if (cls) part += `.${cls}`;
      const same = node.parentElement ? [...node.parentElement.children].filter((c) => c.tagName === node.tagName) : [];
      if (same.length > 1) part += `:nth-of-type(${same.indexOf(node) + 1})`;
      parts.unshift(part);
      node = node.parentElement;
    }
    return parts.join(' > ');
  };
  const ownText = (el) => [...el.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent).join('').replace(/\s+/g, ' ').trim();
  const hint = (el) => ({
    tag: el.tagName.toLowerCase(),
    id: el.id || null,
    className: typeof el.className === 'string' ? el.className : '',
    text: (ownText(el) || el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 60),
  });
  // Tope de MAX hallazgos por regla; los que pasan se cuentan en `omitidos`.
  const omitidos = {};
  const push = (regla, el, detalle) => {
    const sel = selector(el);
    if (out.some((f) => f.regla === regla && f.selector === sel)) return;
    if (out.filter((f) => f.regla === regla).length >= MAX) { omitidos[regla] = (omitidos[regla] || 0) + 1; return; }
    out.push({ regla, selector: sel, detalle, ancho: width, ...hint(el) });
  };
  const ctx = document.createElement('canvas').getContext('2d');
  const rgba = (color) => {
    ctx.fillStyle = '#000';
    ctx.fillStyle = color;
    const v = ctx.fillStyle;
    if (v.startsWith('#')) {
      const n = parseInt(v.slice(1), 16);
      return [(n >> 16) & 255, (n >> 8) & 255, n & 255, 1];
    }
    const m = v.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1].split(',').map((s) => parseFloat(s));
    return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1];
  };
  // Fondo efectivo: primer fondo opaco hacia arriba, mezclando los semitransparentes.
  const backgroundOf = (el) => {
    const layers = [];
    for (let node = el; node && node.nodeType === 1; node = node.parentElement) {
      const cs = getComputedStyle(node);
      if (cs.backgroundImage && cs.backgroundImage !== 'none') return null;
      const c = rgba(cs.backgroundColor);
      if (c && c[3] > 0) {
        layers.push(c);
        if (c[3] >= 1) break;
      }
    }
    let base = [255, 255, 255];
    for (const [r, g, b, a] of layers.reverse()) base = [r * a + base[0] * (1 - a), g * a + base[1] * (1 - a), b * a + base[2] * (1 - a)];
    return base;
  };
  const lum = ([r, g, b]) => {
    const f = (c) => { const s = c / 255; return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4; };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
  };
  const ratio = (a, b) => { const x = lum(a); const y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };

  const all = [...document.querySelectorAll('body *')].filter((el) => !['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE'].includes(el.tagName) && visible(el));

  // Áreas de pulsación: solo en el ancho de móvil, donde se pulsa con el dedo.
  if (tap) {
    const TAP = 40;
    const interactive = all.filter((el) => el.matches('a[href], button, input:not([type=hidden]), select, textarea, summary, [role=button], [role=link], [role=tab], [tabindex]:not([tabindex="-1"])'));
    for (const el of interactive) {
      if (el.disabled) continue;
      // Excepción WCAG 2.5.8: enlaces dentro de un texto.
      if (el.tagName === 'A' && el.parentElement && ['P', 'LI', 'SPAN', 'TD', 'DD', 'SMALL', 'EM', 'STRONG'].includes(el.parentElement.tagName) && ownText(el.parentElement).length > 0) continue;
      if (el.matches('input[type=checkbox], input[type=radio]') && el.closest('label') && el.closest('label').getBoundingClientRect().height >= TAP) continue;
      const r = el.getBoundingClientRect();
      let w = r.width;
      let h = r.height;
      for (const pseudo of ['::before', '::after']) {
        const ps = getComputedStyle(el, pseudo);
        if (ps.content === 'none' || ps.position !== 'absolute') continue;
        const [t, rr, b, l] = [ps.top, ps.right, ps.bottom, ps.left].map(parseFloat);
        if ([t, rr, b, l].every(Number.isFinite)) { w = Math.max(w, r.width - l - rr); h = Math.max(h, r.height - t - b); }
        else { const pw = parseFloat(ps.width); const ph = parseFloat(ps.height); if (Number.isFinite(pw)) w = Math.max(w, pw); if (Number.isFinite(ph)) h = Math.max(h, ph); }
      }
      if (w < TAP || h < TAP) push('area-pulsacion', el, `${Math.round(w)}×${Math.round(h)} px (mínimo ${TAP}; recomendado 44 en táctil)`);
    }
  }

  for (const el of all) {
    const cs = getComputedStyle(el);
    const text = ownText(el);
    const clip = cs.backgroundClip || cs.webkitBackgroundClip;
    if ((clip === 'text' || cs.webkitBackgroundClip === 'text') && /gradient/.test(cs.backgroundImage)) push('texto-degradado', el, cs.backgroundImage.slice(0, 80));

    for (const side of ['Left', 'Right']) {
      const wSide = parseFloat(cs[`border${side}Width`]);
      const other = side === 'Left' ? 'Right' : 'Left';
      const c = rgba(cs[`border${side}Color`]);
      if (wSide > 1 && cs[`border${side}Style`] !== 'none' && c && c[3] > 0 && el.tagName !== 'HR'
        && parseFloat(cs.borderTopWidth) <= 1 && parseFloat(cs.borderBottomWidth) <= 1 && parseFloat(cs[`border${other}Width`]) <= 1
        && el.getBoundingClientRect().width > 24) {
        push('borde-lateral', el, `border-${side.toLowerCase()}: ${cs[`border${side}Width`]} ${cs[`border${side}Color`]}`);
      }
    }

    if (text && cs.textTransform === 'uppercase' && (parseFloat(cs.letterSpacing) || 0) >= 0.5 && parseFloat(cs.fontSize) <= 15) {
      const next = el.nextElementSibling;
      const isHeading = (n) => n && (/^H[1-4]$/.test(n.tagName) || (n.firstElementChild && /^H[1-4]$/.test(n.firstElementChild.tagName)));
      if (isHeading(next) || isHeading(el.parentElement && el.parentElement.nextElementSibling)) push('eyebrow', el, `mayúsculas con letter-spacing ${cs.letterSpacing} sobre un título`);
    }

    const props = cs.transitionProperty.split(',').map((s) => s.trim());
    const durs = cs.transitionDuration.split(',').map((s) => parseFloat(s));
    if (props.some((p, i) => p === 'all' && (durs[i % durs.length] || 0) > 0)) push('transition-all', el, `transition: all ${cs.transitionDuration}`);

    const label = (text || '').trim();
    const iconLike = el.matches('button, a, [role=button], [role=img], i, .icon, [class*="icon"], [aria-hidden="true"]');
    const emojiOnly = label && [...label].length <= 3 && [...label].some((ch) => /\p{Extended_Pictographic}/u.test(ch) && !['©', '®', '™'].includes(ch));
    if (emojiOnly || (iconLike && [...label].some((ch) => /\p{Extended_Pictographic}/u.test(ch) && !['©', '®', '™'].includes(ch)))) push('emoji-icono', el, `«${label.slice(0, 12)}»`);

    if (text && text.replace(/[\s\p{P}]/gu, '').length >= 2 && !el.closest('[aria-hidden="true"]') && !el.matches(':disabled') && !el.closest('[disabled]')) {
      const fg = rgba(cs.color);
      const bg = backgroundOf(el);
      if (fg && bg) {
        const alpha = fg[3] * parseFloat(cs.opacity);
        const fgMix = [fg[0] * alpha + bg[0] * (1 - alpha), fg[1] * alpha + bg[1] * (1 - alpha), fg[2] * alpha + bg[2] * (1 - alpha)];
        const size = parseFloat(cs.fontSize);
        const large = size >= 24 || (size >= 18.66 && parseInt(cs.fontWeight, 10) >= 700);
        const need = large ? 3 : 4.5;
        const r = ratio(fgMix, bg);
        if (r < need) push('contraste', el, `${r.toFixed(2).replace('.', ',')}:1 (necesita ${String(need).replace('.', ',')}:1, ${Math.round(size)} px)`);
      }
    }
  }
  return { hallazgos: out, omitidos, texto: document.body.innerText };
}

function measure(vw) {
  const de = document.documentElement;
  const sel = (el) => {
    const parts = [];
    let node = el;
    for (let d = 0; node && node.nodeType === 1 && node !== document.body && d < 4; d++) {
      let p = node.tagName.toLowerCase();
      if (node.id) { parts.unshift(`${p}#${node.id}`); break; }
      const cls = typeof node.className === 'string' ? node.className.trim().split(/\s+/)[0] : '';
      if (cls) p += `.${cls}`;
      parts.unshift(p);
      node = node.parentElement;
    }
    return parts.join(' > ');
  };
  const sobresalen = [...document.querySelectorAll('body *')].filter((e) => {
    const r = e.getBoundingClientRect();
    const cs = getComputedStyle(e);
    return r.width > 0 && r.right > vw + 1 && cs.visibility !== 'hidden' && cs.display !== 'none';
  }).slice(0, 15).map((e) => ({ selector: sel(e), right: Math.round(e.getBoundingClientRect().right) }));
  return { viewport: vw, scrollWidth: de.scrollWidth, clientWidth: de.clientWidth, alto: de.scrollHeight, desborda: de.scrollWidth > vw, sobresalen };
}

// ── Orquestación ─────────────────────────────────────────────────────────

export function loadPlaywright(explicit) {
  const tries = [];
  if (explicit) tries.push(() => createRequire(import.meta.url)(resolve(explicit)));
  const req = createRequire(join(process.cwd(), 'package.json'));
  for (const name of ['playwright', '@playwright/test', 'playwright-core']) tries.push(() => req(name));
  for (const t of tries) {
    try {
      const mod = t();
      if (mod && mod.chromium) return mod;
    } catch { /* siguiente */ }
  }
  return null;
}

// Se mide la pantalla quieta: recorre la página para que aparezca lo que entra al hacer scroll y
// espera a las fuentes y a que acaben las animaciones finitas (como mucho 5 s). Sin esto, la captura
// sale a mitad de una animación de carga y lo que empieza oculto no se mide.
async function settle() {
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  if (document.fonts) await document.fonts.ready;
  const step = Math.max(window.innerHeight, 300);
  for (let y = 0, i = 0; y < document.documentElement.scrollHeight && i < 40; y += step, i++) {
    window.scrollTo(0, y);
    await wait(100);
  }
  window.scrollTo(0, 0);
  const finite = document.getAnimations().filter((a) => Number.isFinite(a.effect?.getComputedTiming().endTime));
  await Promise.race([Promise.all(finite.map((a) => a.finished.catch(() => {}))), wait(5000)]);
  await wait(150);
}

async function launch(pw) {
  const attempts = [];
  if (process.env.CHROME_PATH) attempts.push(() => pw.chromium.launch({ executablePath: process.env.CHROME_PATH, headless: true }));
  attempts.push(() => pw.chromium.launch({ channel: 'chrome', headless: true }));
  attempts.push(() => pw.chromium.launch({ headless: true }));
  let last;
  for (const a of attempts) {
    try { return await a(); } catch (e) { last = e; }
  }
  throw last;
}

export async function verify({ target, out, name = 'pantalla', widths = [1440, 390], previous, sources = [], playwright }) {
  const started = Date.now();
  const pw = loadPlaywright(playwright);
  if (!pw) {
    const err = new Error('El proyecto no tiene Playwright (playwright o @playwright/test). verify no instala nada: '
      + 'sin capturas ni reglas, el revisor trabaja solo sobre el código.');
    err.code = 'NO_PLAYWRIGHT';
    throw err;
  }
  const isUrl = /^https?:\/\//.test(target);
  const file = isUrl ? null : resolve(target);
  if (file && !existsSync(file)) throw new Error(`No existe ${target}`);
  const url = isUrl ? target : pathToFileURL(file).href;
  const sourceLines = file ? readFileSync(file, 'utf8').split('\n') : null;
  mkdirSync(out, { recursive: true });

  const browser = await launch(pw);
  const report = { version: 1, objetivo: target, fecha: new Date().toISOString(), anchos: {}, capturas: {}, hallazgos: [] };
  try {
    for (const w of widths) {
      const page = await browser.newPage({ viewport: { width: w, height: 900 }, deviceScaleFactor: 1 });
      await page.goto(url, { waitUntil: 'load', timeout: 60000 });
      await page.evaluate(settle);
      const medidas = await page.evaluate(measure, w);
      report.anchos[w] = medidas;
      if (medidas.desborda) {
        report.hallazgos.push({ regla: 'desbordamiento', selector: 'html', ancho: w, detalle: `el documento mide ${medidas.scrollWidth} px en una ventana de ${w}`, sobresalen: medidas.sobresalen });
      }
      const png = `${name}-${w}.png`;
      await page.screenshot({ path: join(out, png), fullPage: true });
      report.capturas[w] = png;
      const res = await page.evaluate(inPage, { width: w, tap: w <= 480 });
      // Una regla en el mismo elemento se cuenta una vez, aunque aparezca en los dos anchos.
      for (const f of res.hallazgos) {
        const seen = report.hallazgos.find((g) => g.regla === f.regla && g.selector === f.selector);
        if (seen) seen.anchos = [...new Set([...(seen.anchos || [seen.ancho]), w])];
        else report.hallazgos.push(f);
      }
      report.numeros = [...new Set([...(report.numeros || []), ...numbersIn(res.texto)])];
      for (const [regla, n] of Object.entries(res.omitidos)) report.omitidos = { ...report.omitidos, [regla]: Math.max(n, report.omitidos?.[regla] || 0) };
      await page.close();
    }
  } finally {
    await browser.close();
  }
  for (const f of report.hallazgos) {
    if (sourceLines && f.regla !== 'desbordamiento') f.linea = findSourceLine(sourceLines, f);
  }
  if (previous) {
    const prev = JSON.parse(readFileSync(previous, 'utf8'));
    const sourcesText = sources.filter((s) => existsSync(s)).map((s) => readFileSync(s, 'utf8')).join('\n');
    report.dato_sin_fuente = numbersWithoutSource(prev.numeros || [], report.numeros || [], sourcesText);
  }
  report.resumen = {
    desborda: Object.fromEntries(Object.entries(report.anchos).map(([w, m]) => [w, m.desborda])),
    por_regla: Object.fromEntries(RULES.map((r) => [r, report.hallazgos.filter((f) => f.regla === r).length])),
    omitidos: report.omitidos,
    dato_sin_fuente: report.dato_sin_fuente ? report.dato_sin_fuente.length : undefined,
  };
  report.duracion_ms = Date.now() - started;
  writeFileSync(join(out, `${name}-verify.json`), JSON.stringify(report, null, 2));
  return report;
}

function parseArgs(argv) {
  const args = { widths: [1440, 390], sources: [] };
  const rest = [];
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    const next = () => argv[++i];
    if (a === '--out') args.out = next();
    else if (a === '--name') args.name = next();
    else if (a === '--widths') args.widths = next().split(',').map(Number);
    else if (a === '--previous') args.previous = next();
    else if (a === '--sources') args.sources = next().split(',').filter(Boolean);
    else if (a === '--playwright') args.playwright = next();
    else rest.push(a);
  }
  args.target = rest[0];
  return args;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.target || !args.out) {
    console.error('Uso: node verify.mjs <fichero.html | URL> --out <dir> [--name pantalla] [--widths 1440,390] [--previous verify.json] [--sources brief.md,prd.md]');
    process.exit(1);
  }
  if (!isAbsolute(args.out)) args.out = resolve(args.out);
  try {
    const r = await verify(args);
    const lines = [`verify · ${args.target} · ${(r.duracion_ms / 1000).toFixed(1)} s`];
    for (const [w, m] of Object.entries(r.anchos)) lines.push(`  ${w} px: scrollWidth ${m.scrollWidth}${m.desborda ? ` DESBORDA (${m.sobresalen.length} elementos sobresalen)` : ''}`);
    for (const [regla, n] of Object.entries(r.resumen.por_regla)) if (n) lines.push(`  ${regla}: ${n}${r.omitidos?.[regla] ? ` (y ${r.omitidos[regla]} más sin listar)` : ''}`);
    if (r.dato_sin_fuente && r.dato_sin_fuente.length) lines.push(`  dato-sin-fuente: ${r.dato_sin_fuente.join(', ')}`);
    lines.push(`  informe: ${join(args.out, `${args.name || 'pantalla'}-verify.json`)}`);
    console.log(lines.join('\n'));
  } catch (e) {
    console.error(`verify: ${e.message}`);
    process.exit(e.code === 'NO_PLAYWRIGHT' ? 2 : 1);
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) main();
