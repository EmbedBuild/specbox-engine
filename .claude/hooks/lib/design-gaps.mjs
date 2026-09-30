/**
 * lib/design-gaps.mjs — Design gaps in UI code (US-49 · UC-4902).
 *
 * The JS twin of server/design_system/code_gaps.py: same rules, same output.
 * tests/fixtures/design_system/code_gap_cases.json is the contract both meet
 * (tests/test_design_code_gaps.py runs it against the two).
 *
 * Kinds: direct_color · font_outside · weight_above · gradient.
 * Escape hatches: `design-gate:ignore` on the line or the line above;
 * `design-gate:disable-file` anywhere in the file.
 */

import { existsSync, readFileSync } from 'fs';
import { join } from 'path';

export const SYSTEM_TOKENS_CANDIDATE_PATHS = [
  'doc/design/design-system.tokens.json',
  'src/styles/tokens/design-system.tokens.json',
  'apps/web/src/styles/tokens/design-system.tokens.json',
  'web/src/styles/tokens/design-system.tokens.json',
  'packages/tokens/dist/design-system.tokens.json',
  'design-system.tokens.json',
];

const UI_EXTENSIONS = new Set([
  '.css', '.scss', '.sass', '.less', '.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs',
  '.astro', '.vue', '.svelte', '.html', '.dart',
]);
const EXCLUDED_SEGMENTS = new Set([
  'node_modules', 'dist', 'build', '.astro', '.next', 'coverage', 'public', '__tests__',
  'tests', 'test', 'e2e',
]);
const EXCLUDED_PREFIXES = ['doc/', 'docs/'];
const EXCLUDED_FRAGMENTS = ['styles/tokens/', 'packages/tokens/'];
const EXCLUDED_NAME_RE = /\.(test|spec)\.[a-z]+$|\.d\.ts$/;

export const GENERIC_FAMILIES = new Set([
  'serif', 'sans-serif', 'monospace', 'cursive', 'fantasy', 'system-ui', 'ui-monospace',
  'ui-sans-serif', 'ui-serif', 'ui-rounded', '-apple-system', 'blinkmacsystemfont', 'emoji', 'math',
  'inherit', 'initial', 'unset', 'revert', 'revert-layer',
]);

export const IGNORE_MARK = 'design-gate:ignore';
export const DISABLE_FILE_MARK = 'design-gate:disable-file';

// ── patterns (kept identical to code_gaps.py) ─────────────────────────

const GRADIENT_RE = /\b(?:repeating-)?(?:linear|radial|conic)-gradient(?=\()/g;
const TW_GRADIENT_RE =
  /(?<![\w-])bg-(?:gradient-to-[a-z]{1,2}|linear-[a-z0-9-]+|radial(?:-[a-z0-9-]+)?|conic(?:-[a-z0-9-]+)?)(?![\w-])/g;
const DART_GRADIENT_RE = /\b(?:Linear|Radial|Sweep)Gradient(?=\()/g;

const HEX_RE = /(?:(?<=[:\s,(\[='"`])|^)#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})(?![0-9a-zA-Z_(-])/g;
const FUNC_COLOR_RE = /\b(?:rgba?|hsla?|oklch|oklab|lab|lch|hwb)\(([^)]*)\)/g;
const PALETTE =
  'slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|' +
  'indigo|violet|purple|fuchsia|pink|rose';
const TW_PREFIX =
  'bg|text|border(?:-[trblxyse])?|ring|ring-offset|fill|stroke|from|via|to|outline|divide|' +
  'placeholder|decoration|shadow|accent|caret';
const TW_PALETTE_RE = new RegExp(`(?<![\\w-])(?:${TW_PREFIX})-(?:${PALETTE})-(?:50|[1-9]00|950)(?![\\w-])`, 'g');
const TW_BW_RE = /(?<![\w-])(?:bg|text|border|ring|fill|stroke|from|via|to|outline|divide)-(?:white|black)(?![\w-])/g;
const DART_COLOR_RE = /\bColor\(\s*0x[0-9A-Fa-f]{6,8}\s*\)|\bColor\.from(?:ARGB|RGBO)\(|\bColors\.(?!transparent\b)[a-z][A-Za-z]*(?:\[\d+\])?/g;

const CSS_FONT_RE = /font-family\s*:\s*([^;{}]+)/g;
const JS_FONT_RE = /fontFamily\s*:\s*(['"`])([^'"`]+)\1/g;
const TW_FONT_RE = /(?<![\w-])font-\[([^\]]+)\]/g;
const GFONTS_RE = /fonts\.googleapis\.com\/css2?\?([^'"\s)]+)/g;
const GOOGLEFONTS_DART_RE = /\bGoogleFonts\.([a-z][A-Za-z0-9]*)\(/g;

const CSS_WEIGHT_RE = /font-weight\s*:\s*(\d{3}|bold|bolder)\b/g;
const JS_WEIGHT_RE = /fontWeight\s*:\s*['"]?(\d{3}|bold|bolder)\b/g;
const TW_WEIGHT_RE = /(?<![\w-])font-(bold|extrabold|black)(?![\w-])/g;
const TW_WEIGHT_ARBITRARY_RE = /(?<![\w-])font-\[(\d{3})\]/g;
const DART_WEIGHT_RE = /\bFontWeight\.(w[1-9]00|bold)\b/g;

const NAMED_WEIGHTS = { bold: 700, bolder: 900, extrabold: 800, black: 900 };

// ── system ────────────────────────────────────────────────────────────

export function splitFamilyStack(stack) {
  return String(stack)
    .split(',')
    .map((p) => p.trim().replace(/^["']+|["']+$/g, '').trim())
    .filter(Boolean);
}

/** Rules from a design-system.tokens.json object: allowed families + max weight. */
export function rulesFromTokens(tokens) {
  const families = new Set();
  for (const stack of Object.values(tokens?.type?.families || {})) {
    for (const name of splitFamilyStack(stack)) families.add(name.toLowerCase());
  }
  const weights = [];
  for (const group of tokens?.type?.groups || []) {
    for (const style of group?.styles || []) {
      if (style?.fontWeight != null) weights.push(Number(style.fontWeight));
    }
  }
  return { families, maxWeight: weights.length ? Math.max(...weights) : 600 };
}

/** { path, rules } of the project's system tokens, or null. */
export function findSystemTokens(root = '.') {
  for (const rel of SYSTEM_TOKENS_CANDIDATE_PATHS) {
    const file = join(root, rel);
    if (!existsSync(file)) continue;
    try {
      return { path: rel, rules: rulesFromTokens(JSON.parse(readFileSync(file, 'utf-8'))) };
    } catch {
      return { path: rel, rules: null, error: 'invalid JSON' };
    }
  }
  return null;
}

// ── scanning ──────────────────────────────────────────────────────────

export function isUiSource(path) {
  const p = String(path).replace(/\\/g, '/').replace(/^(\.\/)+/, '').replace(/^\/+/, '');
  const dot = p.lastIndexOf('.');
  if (dot === -1 || !UI_EXTENSIONS.has(p.slice(dot).toLowerCase())) return false;
  if (EXCLUDED_PREFIXES.some((x) => p.startsWith(x)) || EXCLUDED_FRAGMENTS.some((f) => p.includes(f))) return false;
  if (p.split('/').slice(0, -1).some((seg) => EXCLUDED_SEGMENTS.has(seg))) return false;
  return !EXCLUDED_NAME_RE.test(p);
}

export function fixFor(kind, rules) {
  const families = [...rules.families].filter((f) => !GENERIC_FAMILIES.has(f)).sort().join(', ') || 'las del sistema';
  return {
    direct_color: 'Usa un token del sistema (su clase o var(--…)) en lugar del color escrito.',
    font_outside: `Usa las familias del sistema (${families}) con su clase o variable.`,
    weight_above: `El peso máximo del sistema es ${rules.maxWeight}: usa ese peso o uno menor.`,
    gradient: 'El sistema pinta los fondos planos: usa un color de superficie del sistema.',
  }[kind];
}

/** All design gaps of the UI files in `files` ({relpath: content}). */
export function scanFiles(files, rules) {
  const gaps = [];
  for (const path of Object.keys(files).sort()) {
    if (isUiSource(path)) gaps.push(...scanFile(path, files[path], rules));
  }
  return gaps;
}

export function scanFile(path, content, rules) {
  if (content.includes(DISABLE_FILE_MARK)) return [];
  const gaps = [];
  let inBlock = null;
  let prevRaw = '';
  content.split(/\r?\n/).forEach((raw, i) => {
    const ignored = raw.includes(IGNORE_MARK) || prevRaw.includes(IGNORE_MARK);
    prevRaw = raw;
    const stripped = stripComments(raw, inBlock);
    inBlock = stripped.inBlock;
    if (ignored || !stripped.line.trim()) return;
    for (const [kind, column, value] of lineGaps(stripped.line, rules)) {
      gaps.push({ kind, file: path, line: i + 1, column, value, location: `${path}:${i + 1}` });
    }
  });
  gaps.sort((a, b) => a.line - b.line || a.column - b.column || a.kind.localeCompare(b.kind));
  return gaps;
}

function stripComments(raw, inBlock) {
  let line = raw;
  if (inBlock) {
    const end = line.indexOf(inBlock);
    if (end === -1) return { line: '', inBlock };
    line = ' '.repeat(end + inBlock.length) + line.slice(end + inBlock.length);
    inBlock = null;
  }
  for (const [opener, closer] of [['/*', '*/'], ['<!--', '-->']]) {
    for (;;) {
      const start = line.indexOf(opener);
      if (start === -1) break;
      const end = line.indexOf(closer, start + opener.length);
      if (end === -1) {
        line = line.slice(0, start);
        inBlock = closer;
        break;
      }
      line = line.slice(0, start) + ' '.repeat(end + closer.length - start) + line.slice(end + closer.length);
    }
  }
  line = line.replace(/(^|\s)\/\/.*$/, '$1');
  return { line, inBlock };
}

function familiesOf(value) {
  return splitFamilyStack(value.replace('!important', ''))
    .map((n) => n.trim().toLowerCase())
    .filter((n) => n && !n.startsWith('var(') && !n.startsWith('theme('));
}

function camelToWords(name) {
  return name.replace(/(?<!^)(?=[A-Z0-9])/g, ' ').toLowerCase();
}

function* lineGaps(line, rules) {
  const outside = (f) => !rules.families.has(f) && !GENERIC_FAMILIES.has(f);

  for (const rx of [GRADIENT_RE, TW_GRADIENT_RE, DART_GRADIENT_RE]) {
    for (const m of line.matchAll(rx)) yield ['gradient', m.index, m[0]];
  }

  for (const m of line.matchAll(HEX_RE)) {
    const digits = m[0].slice(1);
    const before = line.slice(0, m.index);
    if (before.endsWith('url(')) continue;
    if ((digits.length === 3 || digits.length === 4) && /^\d+$/.test(digits)) {
      const inValue = ["'", '"', '`', '[', '('].includes(before.slice(-1)) || before.includes(':');
      if (!inValue) continue;
    }
    yield ['direct_color', m.index, m[0]];
  }
  for (const m of line.matchAll(FUNC_COLOR_RE)) {
    if (!m[1].includes('var(')) yield ['direct_color', m.index, m[0]];
  }
  for (const rx of [TW_PALETTE_RE, TW_BW_RE, DART_COLOR_RE]) {
    for (const m of line.matchAll(rx)) yield ['direct_color', m.index, m[0]];
  }

  for (const m of line.matchAll(CSS_FONT_RE)) {
    for (const f of familiesOf(m[1])) if (outside(f)) yield ['font_outside', m.index, f];
  }
  for (const m of line.matchAll(JS_FONT_RE)) {
    for (const f of familiesOf(m[2])) if (outside(f)) yield ['font_outside', m.index, f];
  }
  for (const m of line.matchAll(TW_FONT_RE)) {
    const raw = m[1];
    if (/^\d+$/.test(raw) || raw.startsWith('var(') || raw.startsWith('length:')) continue;
    for (const f of familiesOf(raw.replace(/_/g, ' '))) if (outside(f)) yield ['font_outside', m.index, f];
  }
  for (const m of line.matchAll(GFONTS_RE)) {
    for (const part of m[1].split('&')) {
      if (!part.startsWith('family=')) continue;
      let family = part.slice('family='.length).replace(/\+/g, ' ');
      try { family = decodeURIComponent(family); } catch { /* keep raw */ }
      family = family.split(':')[0].trim().toLowerCase();
      if (family && outside(family)) yield ['font_outside', m.index, family];
    }
  }
  for (const m of line.matchAll(GOOGLEFONTS_DART_RE)) {
    if (['getFont', 'config', 'asMap'].includes(m[1])) continue;
    const family = camelToWords(m[1]);
    if (outside(family)) yield ['font_outside', m.index, family];
  }

  for (const rx of [CSS_WEIGHT_RE, JS_WEIGHT_RE]) {
    for (const m of line.matchAll(rx)) {
      const weight = /^\d+$/.test(m[1]) ? Number(m[1]) : NAMED_WEIGHTS[m[1]];
      if (weight > rules.maxWeight) yield ['weight_above', m.index, m[1]];
    }
  }
  for (const m of line.matchAll(TW_WEIGHT_RE)) {
    if (NAMED_WEIGHTS[m[1]] > rules.maxWeight) yield ['weight_above', m.index, m[0]];
  }
  for (const m of line.matchAll(TW_WEIGHT_ARBITRARY_RE)) {
    if (Number(m[1]) > rules.maxWeight) yield ['weight_above', m.index, m[0]];
  }
  for (const m of line.matchAll(DART_WEIGHT_RE)) {
    const weight = m[1] === 'bold' ? 700 : Number(m[1].slice(1));
    if (weight > rules.maxWeight) yield ['weight_above', m.index, m[0]];
  }
}
