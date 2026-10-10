#!/usr/bin/env node
// /visual-setup (US-92 · UC-9204): el sistema de diseño del proyecto, listo para publicarlo como
// Artifact del tipo Design System y usarlo desde un lienzo de Claude Design.
//
// Uso:
//   node ds-artifact.mjs build --tokens <design-system.tokens.json> --out <carpeta> --title <nombre>
//        [--namespace <Ns>] [--bundle-js <f> --bundle-css <f> --types <f> --components A,B]
//        [--design-md doc/design/DESIGN.md] [--tagline <frase>] [--index <design-system.json leído>]
//        [--fonts-dir <carpeta>] [--no-google-fonts] [--by <persona>] [--via <superficie>]
//
// Escribe en <carpeta>/project/ lo que el tipo lee:
//   tokens.json              los tokens del proyecto en la forma que la página entiende (listas, nombres
//                            válidos y únicos, valores que no se caen). Lo que se cae se lista.
//   tokens.css               las variables de los tokens con la forma «compilada» del tipo y su primera
//                            línea, para que la página lo adopte. El lienzo lo copia al instalar el
//                            sistema y los artboards no declaran variables.
//   components/bundle.css    las fuentes de Google (si las familias no traen fichero) y, si el proyecto
//                            tiene, su hoja de componentes.
//   components/bundle.js     los componentes compilados del proyecto (un script clásico que asigna
//                            window.<Ns>), con su cabecera @ds-bundle; index.d.ts, sus tipos.
//   README.md                reglas de uso que nombran tokens y la sección «Consuming this system».
//   components/Cover/preview.html  la portada.
//   design-system.json       el índice (se escribe el último al publicar).
//
// No publica: lo hace el agente con la herramienta Artifact (ver el Paso 2.9.3 de /visual-setup).
// Salida: 0 hecho · 1 error (tokens ilegibles, bundle que no es un script clásico…).

import { copyFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { basename, dirname, isAbsolute, join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const NAME = /^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$/;
const HEX = /^#([0-9a-f]{3,4}|[0-9a-f]{6}|[0-9a-f]{8})$/i;
const COLOR_FN = /^(rgb|rgba|hsl|hsla|oklch|oklab|lab|lch|color)\(\s*[-a-z0-9.,%/\s]*\)$/i;
const ALIAS = /^\{([A-Za-z0-9][A-Za-z0-9_.-]{0,63})\}$/;
const LENGTH = /^(-?\d*\.?\d+(px|rem|em|%)|0)$/;
const PLAIN = /^[A-Za-z0-9 #%(),./+_-]{1,200}$/;
const MAX_OTHER_FAMILIES = 12;

// ── Validación: lo que la página del tipo puede leer ─────────────────────

const balanced = (s) => {
  let d = 0;
  for (const c of s) { if (c === '(') d++; else if (c === ')' && --d < 0) return false; }
  return d === 0;
};
const noFunctions = (s) => !/\b(var|url|color-mix|calc)\(/i.test(s);

export function colorValueError(v) {
  if (typeof v !== 'string') return 'no es texto';
  if (HEX.test(v)) return null;
  if (ALIAS.test(v)) return null;
  if (COLOR_FN.test(v) && noFunctions(v)) return null;
  if (/^(transparent|currentcolor|inherit|[a-z]+)$/i.test(v)) return 'color con nombre';
  return 'valor de color no admitido (var(), color-mix(), url() o funciones anidadas)';
}

export function lengthOk(v) {
  return typeof v === 'number' || (typeof v === 'string' && LENGTH.test(v.trim()));
}

function plainOk(v) {
  return typeof v === 'number' || (typeof v === 'string' && PLAIN.test(v) && balanced(v) && noFunctions(v));
}

function shadowOk(v) {
  return typeof v === 'string' && v.length <= 400 && /^[A-Za-z0-9 #%(),./+_-]+$/.test(v) && balanced(v) && noFunctions(v);
}

// Devuelve los tokens en la forma del tipo y la lista de lo que se cae, con el motivo.
export function validateTokens(input) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) throw new Error('tokens.json no es un objeto');
  const caidos = [];
  const used = new Set();
  const drop = (familia, nombre, motivo) => caidos.push({ familia, nombre, motivo });
  const out = {};
  for (const k of ['name', 'version', 'meta']) if (k in input) out[k] = input[k];

  // Colores: una lista plana con sus temas.
  const color = input.color;
  if (color && !Array.isArray(color.tokens)) throw new Error('color.tokens tiene que ser una lista (no un mapa DTCG)');
  if (color) {
    const themes = (color.themes || [{ id: 'light' }]).filter((t) => t && NAME.test(String(t.id).toLowerCase())).slice(0, 8)
      .map((t) => ({ ...t, id: String(t.id).toLowerCase() }));
    const first = themes[0].id;
    const raw = new Map();
    for (const t of color.tokens) {
      const name = String(t?.name ?? '').replace(/^(--|\.)/, '');
      if (!NAME.test(name)) { drop('color', t?.name, 'nombre no válido'); continue; }
      if (raw.has(name)) { drop('color', name, 'nombre repetido'); continue; }
      const value = typeof t.value === 'string' ? { [first]: t.value } : { ...(t.value || {}) };
      raw.set(name, { ...t, name, value });
    }
    // Alias: a un color que existe, sin ciclos y como mucho 16 saltos.
    const resolves = (name, theme, seen = new Set()) => {
      if (seen.size > 16 || seen.has(name)) return false;
      const tok = raw.get(name);
      if (!tok) return false;
      const v = tok.value[theme] ?? tok.value[first];
      if (typeof v !== 'string') return false;
      const m = v.match(ALIAS);
      return m ? resolves(m[1], theme, new Set([...seen, name])) : colorValueError(v) === null;
    };
    const tokens = [];
    for (const tok of raw.values()) {
      const value = {};
      for (const th of themes) {
        const v = tok.value[th.id];
        if (v === undefined) continue;
        const why = colorValueError(v);
        if (why) { drop('color', `${tok.name} (${th.id})`, why); continue; }
        const alias = v.match(ALIAS);
        if (alias && (alias[1] === tok.name || !resolves(alias[1], th.id, new Set([tok.name])))) {
          drop('color', `${tok.name} (${th.id})`, `alias a un color que no existe o en ciclo: ${v}`);
          continue;
        }
        value[th.id] = HEX.test(v) ? v.toLowerCase() : v;
      }
      if (!Object.keys(value).length) { drop('color', tok.name, 'sin ningún valor válido'); continue; }
      if (!(first in value)) value[first] = value[Object.keys(value)[0]];
      used.add(tok.name);
      tokens.push({ name: tok.name, value, ...(tok.usage ? { usage: String(tok.usage).slice(0, 1000) } : {}) });
    }
    out.color = { themes, tokens };
  }

  // Tipografía: familias, fuentes y estilos.
  if (input.type) {
    const t = input.type;
    const families = {};
    for (const [key, stack] of Object.entries(t.families || {})) {
      const k = key.toLowerCase();
      if (!NAME.test(k) || typeof stack !== 'string' || stack.length > 200 || /[;{}<>\\()]/.test(stack) || (stack.split('"').length - 1) % 2) {
        drop('type.families', key, 'pila de fuentes no válida');
        continue;
      }
      families[k] = stack;
    }
    const fonts = (t.fonts || []).filter((f) => {
      const ok = f && typeof f.family === 'string' && !/["']/.test(f.family);
      if (!ok) drop('type.fonts', f?.family, 'familia no válida');
      return ok;
    });
    const groups = [];
    for (const g of (t.groups || []).slice(0, 12)) {
      const styles = [];
      for (const s of g.styles || []) {
        const name = String(s?.name ?? '');
        if (!NAME.test(name)) { drop('type', name, 'nombre no válido'); continue; }
        if (!lengthOk(s.fontSize)) { drop('type', name, `fontSize no válido: ${s.fontSize}`); continue; }
        const st = { ...s };
        if (st.lineHeight !== undefined && !(lengthOk(st.lineHeight) || (Number(st.lineHeight) < 10 && !Number.isNaN(Number(st.lineHeight))))) delete st.lineHeight;
        if (st.letterSpacing !== undefined && !lengthOk(st.letterSpacing)) delete st.letterSpacing;
        if (st.fontWeight === 'normal') st.fontWeight = 400;
        if (st.fontWeight === 'bold') st.fontWeight = 700;
        styles.push(st);
      }
      groups.push({ ...g, styles });
    }
    out.type = { ...t, fonts, families, groups };
  }

  // Las demás familias: listas de {name, value, usage}.
  let others = 0;
  for (const [fam, sec] of Object.entries(input)) {
    if (['name', 'version', 'meta', 'color', 'type'].includes(fam)) continue;
    if (!sec || !Array.isArray(sec.tokens)) { drop(fam, '*', 'no es una lista {tokens:[…]} (mapa DTCG u otra forma)'); continue; }
    if (fam === 'motion') { drop(fam, '*', 'el tipo no tiene familia de movimiento'); continue; }
    if (!['spacing', 'radius', 'shadow'].includes(fam) && ++others > MAX_OTHER_FAMILIES) { drop(fam, '*', 'más de 12 familias'); continue; }
    const tokens = [];
    for (const tok of sec.tokens.slice(0, 60)) {
      const name = String(tok?.name ?? '').replace(/^(--|\.)/, '');
      if (!NAME.test(name)) { drop(fam, tok?.name, 'nombre no válido'); continue; }
      if (used.has(name)) { drop(fam, name, 'nombre repetido en otra familia'); continue; }
      const v = tok.value;
      const ok = fam === 'spacing' || fam === 'radius' ? lengthOk(v)
        : fam === 'shadow' ? (typeof v === 'string' ? shadowOk(v) : v && Object.values(v).every(shadowOk))
          : plainOk(v);
      if (!ok) { drop(fam, name, `valor no admitido: ${JSON.stringify(v)}`); continue; }
      used.add(name);
      tokens.push({ name, value: v, ...(tok.usage ? { usage: String(tok.usage).slice(0, 1000) } : {}) });
    }
    out[fam] = { ...(sec.note ? { note: String(sec.note).slice(0, 400) } : {}), tokens };
  }
  return { tokens: out, caidos };
}

// ── tokens.css con la forma «compilada» del tipo ─────────────────────────

const cssName = (n) => n.replace(/\./g, '\\.');
const cssValue = (v) => {
  if (typeof v === 'number') return `${v}px`;
  const m = typeof v === 'string' && v.match(ALIAS);
  return m ? `var(--${cssName(m[1])})` : String(v);
};

export function tokensCss(tokens, title) {
  const lines = [`/* ${title} — generated from tokens.json */`];
  const themes = tokens.color?.themes || [];
  const first = themes[0]?.id;
  const colorTokens = tokens.color?.tokens || [];
  const shadows = tokens.shadow?.tokens || [];
  const themed = (v, th) => (v && typeof v === 'object' ? v[th] : th === first ? v : undefined);
  if (first) {
    lines.push(`:root, [data-theme="${first}"] {`);
    for (const t of colorTokens) lines.push(`  --${cssName(t.name)}: ${cssValue(t.value[first])};`);
    for (const t of shadows) { const v = themed(t.value, first) ?? (typeof t.value === 'object' ? Object.values(t.value)[0] : t.value); lines.push(`  --${cssName(t.name)}: ${v};`); }
    lines.push('}');
    for (const th of themes.slice(1)) {
      lines.push(`[data-theme="${th.id}"] {`);
      for (const t of colorTokens) {
        const v = t.value[th.id];
        if (v !== undefined) lines.push(`  --${cssName(t.name)}: ${cssValue(v)};`);
        else if (ALIAS.test(t.value[first])) lines.push(`  --${cssName(t.name)}: ${cssValue(t.value[first])};`);
      }
      for (const t of shadows) { const v = themed(t.value, th.id); if (v !== undefined) lines.push(`  --${cssName(t.name)}: ${v};`); }
      lines.push('}');
    }
  }
  const flat = [];
  for (const [fam, sec] of Object.entries(tokens)) {
    if (['name', 'version', 'meta', 'color', 'type', 'shadow'].includes(fam) || !sec?.tokens) continue;
    for (const t of sec.tokens) flat.push(`  --${cssName(t.name)}: ${cssValue(t.value)};`);
  }
  for (const [k, stack] of Object.entries(tokens.type?.families || {})) flat.push(`  --font-${k}: ${stack};`);
  if (flat.length) lines.push(':root {', ...flat, '}');
  for (const g of tokens.type?.groups || []) {
    for (const s of g.styles || []) {
      const fam = s.family || g.family;
      const decl = [
        fam ? `font-family: var(--font-${fam})` : null,
        `font-size: ${cssValue(s.fontSize)}`,
        s.lineHeight !== undefined ? `line-height: ${typeof s.lineHeight === 'number' && s.lineHeight >= 10 ? `${s.lineHeight}px` : s.lineHeight}` : null,
        s.fontWeight !== undefined ? `font-weight: ${s.fontWeight}` : null,
        s.letterSpacing !== undefined ? `letter-spacing: ${cssValue(s.letterSpacing)}` : null,
        s.fontStyle ? `font-style: ${s.fontStyle}` : null,
      ].filter(Boolean);
      lines.push(`.${cssName(s.name)} { ${decl.join('; ')}; }`);
    }
  }
  for (const f of tokens.type?.fonts || []) {
    if (!f.file) continue;
    const file = f.file.includes('/') ? f.file : `fonts/${f.file}`;
    const ext = file.split('.').pop().toLowerCase();
    const format = { woff2: 'woff2', woff: 'woff', ttf: 'truetype', otf: 'opentype' }[ext] || ext;
    lines.push(`@font-face { font-family: "${f.family}"; src: url("${file}") format("${format}"); font-weight: ${f.weight || '400'}; font-style: ${f.style || 'normal'}; font-display: swap; }`);
  }
  return `${lines.join('\n')}\n`;
}

// Familias sin fichero propio → una petición a Google Fonts con los pesos que usan los estilos.
export function googleFontsUrl(tokens) {
  const withFile = new Set((tokens.type?.fonts || []).filter((f) => f.file).map((f) => f.family));
  const weights = new Map();
  for (const g of tokens.type?.groups || []) {
    for (const s of g.styles || []) {
      const key = s.family || g.family;
      const stack = tokens.type?.families?.[key];
      if (!stack) continue;
      const family = stack.split(',')[0].trim().replace(/^["']|["']$/g, '');
      if (withFile.has(family) || /^(system-ui|ui-|-apple-system|sans-serif|serif|monospace)/.test(family)) continue;
      if (!weights.has(family)) weights.set(family, new Set());
      for (const w of String(s.fontWeight || 400).split(/\s+/)) weights.get(family).add(Number(w));
    }
  }
  if (!weights.size) return null;
  const params = [...weights].map(([f, ws]) => `family=${f.replace(/ /g, '+')}:wght@${[...ws].sort((a, b) => a - b).join(';')}`);
  return `https://fonts.googleapis.com/css2?${params.join('&')}&display=swap`;
}

// ── Componentes compilados ───────────────────────────────────────────────

export function componentNames(typesText) {
  return [...new Set([...(typesText || '').matchAll(/export\s+(?:declare\s+)?(?:function|const|class)\s+([A-Z][A-Za-z0-9]*)/g)].map((m) => m[1]))];
}

export function checkBundle(js, namespace) {
  const errors = [];
  if (/^\s*(import|export)\s/m.test(js)) errors.push('lleva import o export: tiene que ser un script clásico (IIFE)');
  if (/<\/script|<!--/i.test(js)) errors.push('contiene «</script» o «<!--» literal: el tipo lo incrusta y se rompería');
  // esbuild --global-name deja `var <Ns>=…` en lo alto de un script clásico: también es window.<Ns>.
  if (!new RegExp(`(window|globalThis|self)\\.${namespace}\\b|["']${namespace}["']|^\\s*var\\s+${namespace}\\s*=`, 'm').test(js)) errors.push(`no asigna window.${namespace}`);
  return errors;
}

export function bundleHeader(js, namespace, components) {
  if (/^\/\*\s*@ds-bundle:/.test(js)) return js;
  const header = { format: 4, namespace, components: components.map((name) => ({ name })) };
  return `/* @ds-bundle: ${JSON.stringify(header)} */\n${js}`;
}

// Las props de un componente, leídas de su interfaz `<Comp>Props` en los tipos.
export function componentProps(typesText, name) {
  const m = (typesText || '').match(new RegExp(`interface\\s+${name}Props\\s*\\{([^}]*)\\}`));
  if (!m) return [];
  return m[1].split(/[;\n]/).map((l) => l.trim()).filter(Boolean).map((l) => {
    const [, prop, opt, type] = l.match(/^([A-Za-z_$][\w$]*)(\??)\s*:\s*(.+)$/) || [];
    return prop ? { prop, opcional: !!opt, tipo: type.trim() } : null;
  }).filter(Boolean);
}

export function componentReadme(namespace, name, props) {
  const lines = [`\`${name}\` es un componente compilado del proyecto; se monta desde \`window.${namespace}.${name}\`.`, ''];
  if (props.length) lines.push('| Prop | Tipo | Obligatoria |', '|---|---|---|', ...props.map((p) => `| \`${p.prop}\` | \`${p.tipo.replace(/\|/g, '\\|')}\` | ${p.opcional ? 'no' : 'sí'} |`), '');
  lines.push(`En un lienzo: \`<x-import component-from-global-scope="${namespace}.${name}"></x-import>\`, con las props como atributos en kebab-case.`);
  return `${lines.join('\n')}\n`;
}

export function componentPreview(namespace, name) {
  return `<!-- @dsCard group="Componentes" height=96 -->
<div id="root" style="padding:16px"></div>
<script>
  const C = window.${namespace} && window.${namespace}.${name};
  if (C) ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(C, null, '${name}'));
</script>
`;
}

// ── README ───────────────────────────────────────────────────────────────

function table(rows) {
  if (rows.length < 2) return '';
  const fmt = (r) => `| ${r.map((c) => String(c ?? '').replace(/\|/g, '\\|').replace(/\n/g, ' ')).join(' | ')} |`;
  return `${[fmt(rows[0]), `|${rows[0].map(() => '---').join('|')}|`, ...rows.slice(1).map(fmt)].join('\n')}\n`;
}

// La sección de lo que se rehúsa del DESIGN.md (UC-9002), tal cual.
export function refusedSection(designMd) {
  if (!designMd) return null;
  const m = designMd.match(/^(#{2,3})\s+[^\n]*(rehúsa|rehusa|refuse|avoid|evitar)[^\n]*\n([\s\S]*?)(?=^#{1,3}\s|(?![\s\S]))/im);
  return m ? m[3].trim() : null;
}

export function readme({ title, tokens, namespace, components = [], hasBundle, googleFonts, refused }) {
  const themes = tokens.color?.themes || [];
  const out = [];
  out.push(`Sistema de diseño de ${title}. Los valores salen de los tokens del proyecto (\`tokens.json\`): ningún color, tipo, espaciado o radio se escribe a mano.`);
  if (tokens.color?.tokens?.length) {
    out.push('', '## Color', '', `Temas: ${themes.map((t) => `\`${t.id}\``).join(', ')}, con \`data-theme\` en \`<html>\`; el primero es el de por defecto. Cada color se usa como dice su nota.`, '');
    out.push(table([['Token', ...themes.map((t) => t.name || t.id), 'Uso'], ...tokens.color.tokens.map((t) => [`\`${t.name}\``, ...themes.map((th) => t.value[th.id] ?? ''), t.usage || ''])]));
  }
  const styles = (tokens.type?.groups || []).flatMap((g) => g.styles.map((s) => ({ ...s, group: g.name, family: s.family || g.family })));
  if (styles.length) {
    out.push('## Tipografía', '', 'Cada estilo es una clase (`.<estilo>`) y lleva familia, tamaño, interlineado y peso. Las familias son variables `--font-<clave>`.', '');
    out.push(table([['Estilo', 'Grupo', 'Familia', 'Tamaño / interlineado', 'Peso', 'Uso'], ...styles.map((s) => [`\`${s.name}\``, s.group, s.family ? `\`--font-${s.family}\`` : '', `${s.fontSize}${s.lineHeight !== undefined ? ` / ${s.lineHeight}` : ''}`, s.fontWeight ?? '', s.usage || ''])]));
  }
  for (const [fam, label] of [['spacing', 'Espaciado'], ['radius', 'Radios'], ['shadow', 'Sombras']]) {
    const list = tokens[fam]?.tokens || [];
    if (!list.length) continue;
    out.push(`## ${label}`, '', table([['Token', 'Valor', 'Uso'], ...list.map((t) => [`\`${t.name}\``, typeof t.value === 'object' ? Object.values(t.value)[0] : t.value, t.usage || ''])]));
  }
  if (refused) out.push('## Lo que se rehúsa', '', refused, '');
  if (components.length) out.push('## Componentes', '', ...components.map((c) => `- \`${namespace}.${c}\``), '');
  out.push('## Consuming this system', '');
  out.push(`- Namespace: \`${namespace}\`.`);
  out.push('- Carga, por este orden:');
  out.push('  1. `tokens.css`: declara todas las variables de los tokens y una clase por estilo de texto. Va siempre, también en un lienzo de Claude Design: sin ella, `bundle.css` y los componentes no tienen valores.');
  out.push(`  2. \`components/bundle.css\`${googleFonts ? ': carga las tipografías de Google Fonts' : ''}${hasBundle ? ' y los estilos de los componentes' : ''}.`);
  if (hasBundle) out.push(`  3. \`components/bundle.js\`: asigna \`window.${namespace}\` y usa el React 18 de la página.`);
  out.push('- En un artboard de Claude Design, tras la línea de `support.js`: `<link rel="stylesheet" href="ds/<carpeta>/tokens.css">` y `<link rel="stylesheet" href="ds/<carpeta>/components/bundle.css">`'
    + (hasBundle ? `, y \`<script src="ds/<carpeta>/components/bundle.js"></script>\`. Un componente se monta con \`<x-import component-from-global-scope="${namespace}.${components[0] || 'Button'}">\`.` : '.'));
  out.push('- Los artboards no declaran variables: usan `var(--<token>)` y las clases de los estilos de texto.');
  return `${out.join('\n').replace(/\n{3,}/g, '\n\n')}\n`;
}

// ── Portada ──────────────────────────────────────────────────────────────

function hexToHsl(hex) {
  let h = hex.replace('#', '');
  if (h.length <= 4) h = h.split('').map((c) => c + c).join('');
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16) / 255);
  const max = Math.max(r, g, b), min = Math.min(r, g, b), l = (max + min) / 2;
  const s = max === min ? 0 : (max - min) / (1 - Math.abs(2 * l - 1));
  return { s, l };
}

// Colores de identidad: los más saturados del primer tema y la tinta más oscura.
export function identityColors(tokens, max = 4) {
  const first = tokens.color?.themes?.[0]?.id;
  const solid = (tokens.color?.tokens || []).map((t) => ({ name: t.name, v: t.value[first] })).filter((t) => HEX.test(t.v || ''));
  const withHsl = solid.map((t) => ({ ...t, ...hexToHsl(t.v) }));
  const ink = [...withHsl].sort((a, b) => a.l - b.l)[0];
  const hues = withHsl.filter((t) => t.s > 0.35 && t.l > 0.15 && t.l < 0.85).sort((a, b) => b.s - a.s);
  const picked = [];
  for (const t of hues) if (picked.length < max - 1 && !picked.some((p) => p.v === t.v)) picked.push(t);
  if (ink && !picked.some((p) => p.v === ink.v)) picked.push(ink);
  return picked.map((t) => t.name);
}

function px(v, fallback) {
  const n = typeof v === 'number' ? v : parseFloat(String(v));
  return Number.isFinite(n) ? n : fallback;
}

export function cover({ title, tokens, tagline }) {
  const colors = identityColors(tokens);
  const spacing = (tokens.spacing?.tokens || []).map((t) => ({ name: t.name, v: px(t.value, 0) })).filter((t) => t.v > 0);
  const radius = (tokens.radius?.tokens || []).map((t) => ({ name: t.name, v: px(t.value, 0) })).filter((t) => t.v > 0 && t.v < 64);
  const step = spacing.find((t) => t.v >= 16) || spacing[spacing.length - 1] || { name: null, v: 16 };
  const r = radius[Math.min(1, radius.length - 1)] || { name: null, v: 6 };
  const display = (tokens.type?.groups || []).flatMap((g) => g.styles.map((s) => ({ ...s, family: s.family || g.family })))
    .sort((a, b) => px(b.fontSize, 0) - px(a.fontSize, 0))[0];
  const fam = display?.family ? `var(--font-${display.family})` : 'system-ui, sans-serif';
  const longest = Math.max(...title.split(/\s+/).map((w) => w.length), title.length > 18 ? 0 : title.length);
  const size = Math.max(64, Math.min(120, Math.floor(440 / (0.6 * Math.max(1, longest)))));
  // Losa alta a la derecha y satélites; rejilla de puntos al paso de espaciado.
  const S = step.v;
  const blocks = [
    { x: 528, y: 0, w: S * 12, h: 288, c: 0 },
    { x: 528 + S * 12 + S, y: 0, w: S * 8, h: S * 8, c: 1 },
    { x: 528 + S * 12 + S, y: S * 9, w: S * 4, h: S * 4, c: 2 },
    { x: 528 + S * 12 + S * 6, y: S * 9, w: Math.max(S * 3, 960 - (528 + S * 12 + S * 6)), h: 288 - S * 9, c: 3 },
  ].filter((b, i) => i < Math.max(colors.length, 1) && b.x < 960);
  const dots = [];
  for (let y = S; y < 288 && dots.length < 60; y += S) for (let x = 528 + S; x < 528 + S * 12 && dots.length < 60; x += S * 2) dots.push(`<circle class="dot" cx="${x}" cy="${y}" r="2"/>`);
  const cls = colors.map((c, i) => `.b${i}{fill:var(--${cssName(c)})}`).join('');
  const derivation = [
    `blocks: ${colors.join(', ') || 'ninguno'} (losa ${S * 12}×288 y satélites a múltiplos de ${step.name || '16px'})`,
    'arrangement: losa alta a la derecha con satélites, sangrando por el borde',
    `pattern: rejilla de puntos al paso ${step.name || '16px'}: sistema de herramienta, preciso y en rejilla`,
    `steps/radii: ${step.name || '16px'} · ${r.name || '6px'}`,
  ];
  return `<!-- @dsCard height=288 -->
<div class="cover">
<!--
${derivation.join('\n')}
-->
<svg class="art" viewBox="0 0 960 288" aria-hidden="true">
${blocks.map((b) => `<rect class="b${b.c % Math.max(colors.length, 1)} tile" x="${b.x}" y="${b.y}" width="${b.w}" height="${b.h}"/>`).join('\n')}
${dots.join('')}
</svg>
<p class="name">${title.replace(/[<&]/g, (c) => ({ '<': '&lt;', '&': '&amp;' }[c]))}</p>
<p class="tagline">${(tagline || `Sistema de diseño de ${title}`).replace(/[<&]/g, (c) => ({ '<': '&lt;', '&': '&amp;' }[c]))}</p>
</div>
<style>
.cover{position:relative;width:960px;height:288px;overflow:hidden}
.art{position:absolute;inset:0;width:960px;height:288px}
${cls}
.tile{rx:${r.name ? `var(--${cssName(r.name)})` : '6px'}}
.dot{fill:var(--${cssName(colors[colors.length - 1] || 'ink')});opacity:.35}
.name{position:absolute;left:40px;bottom:72px;margin:0;max-width:440px;font-family:${fam};font-size:${size}px;line-height:.95;font-weight:600;letter-spacing:-0.02em}
.tagline{position:absolute;left:40px;bottom:40px;margin:0;max-width:440px;font-family:${fam};font-size:14px;line-height:20px;opacity:.72}
</style>
`;
}

// ── Índice ───────────────────────────────────────────────────────────────

export function indexJson({ previous, title, namespace, libraries, by, via, note, now }) {
  const lastChange = { by, at: now, via, note };
  if (previous) {
    return { ...previous, namespace: previous.namespace || namespace, libraries, lastChange };
  }
  return {
    v: 3,
    layout: 'files',
    createdOnFiles: { v: 1, at: now },
    title,
    namespace,
    libraries,
    sections: {},
    groups: [],
    assetGroups: {},
    blobs: {},
    docs: { readme: 'project/README.md', sections: [] },
    lastChange,
  };
}

// ── Construcción ─────────────────────────────────────────────────────────

const slug = (s) => s.replace(/[^A-Za-z0-9]+/g, ' ').trim().split(' ').map((w) => w[0].toUpperCase() + w.slice(1)).join('') || 'System';

export function build(opts) {
  const now = opts.now || new Date().toISOString();
  const title = opts.title;
  if (!opts.tokens || !opts.out || !title) throw new Error('Faltan --tokens, --out o --title');
  const raw = JSON.parse(readFileSync(opts.tokens, 'utf8'));
  const { tokens, caidos } = validateTokens(raw);
  tokens.meta = { ...(tokens.meta || {}), source: 'specbox', file: basename(opts.tokens), synced: now };
  const namespace = opts.namespace || slug(title);
  if (!/^[A-Za-z_$][A-Za-z0-9_$]*$/.test(namespace)) throw new Error(`namespace no válido: ${namespace}`);
  const project = join(opts.out, 'project');
  const files = [];
  const put = (rel, data) => {
    const f = join(project, rel);
    mkdirSync(dirname(f), { recursive: true });
    writeFileSync(f, data);
    files.push(`project/${rel}`);
  };
  const avisos = [];

  // Fuentes del proyecto con fichero: se copian a fonts/.
  for (const f of tokens.type?.fonts || []) {
    if (!f.file) continue;
    const src = opts.fontsDir ? join(opts.fontsDir, basename(f.file)) : null;
    if (src && existsSync(src)) { mkdirSync(join(project, 'fonts'), { recursive: true }); copyFileSync(src, join(project, 'fonts', basename(f.file))); files.push(`project/fonts/${basename(f.file)}`); f.file = `fonts/${basename(f.file)}`; }
    else avisos.push(`la fuente ${f.family} nombra ${f.file} y no está en --fonts-dir: no se publica su fichero`);
  }

  put('tokens.json', `${JSON.stringify(tokens, null, 2)}\n`);
  put('tokens.css', tokensCss(tokens, title));

  const googleFonts = opts.googleFonts === false ? null : googleFontsUrl(tokens);
  let css = googleFonts ? `@import url("${googleFonts}");\n` : '';
  if (opts.bundleCss) {
    const own = readFileSync(opts.bundleCss, 'utf8');
    if (/<\/style/i.test(own)) throw new Error('bundle.css contiene «</style» literal');
    css += own;
  }
  if (css) put('components/bundle.css', css);

  let components = [];
  let libraries = [];
  if (opts.bundleJs) {
    const js = readFileSync(opts.bundleJs, 'utf8');
    const errors = checkBundle(js, namespace);
    if (errors.length) throw new Error(`bundle.js: ${errors.join('; ')}`);
    const types = opts.types ? readFileSync(opts.types, 'utf8') : '';
    components = opts.components?.length ? opts.components : componentNames(types);
    put('components/bundle.js', bundleHeader(js, namespace, components));
    if (types) put('components/index.d.ts', types);
    for (const c of components) {
      put(`components/${c}/README.md`, componentReadme(namespace, c, componentProps(types, c)));
      put(`components/${c}/preview.html`, componentPreview(namespace, c));
    }
    if (/\bReact\b/.test(js)) libraries = [{ name: 'react', version: '18' }, { name: 'react-dom', version: '18' }];
  }

  const designMd = opts.designMd && existsSync(opts.designMd) ? readFileSync(opts.designMd, 'utf8') : null;
  put('README.md', readme({ title, tokens, namespace, components, hasBundle: !!opts.bundleJs, googleFonts, refused: refusedSection(designMd) }));
  put('components/Cover/preview.html', cover({ title, tokens, tagline: opts.tagline }));
  const previous = opts.index && existsSync(opts.index) ? JSON.parse(readFileSync(opts.index, 'utf8')) : null;
  if (previous && !previous.createdOnFiles && !previous.convertedFrom) throw new Error('el design-system.json leído no tiene marca: no es un índice del tipo y no se escribe encima');
  put('design-system.json', `${JSON.stringify(indexJson({ previous, title, namespace, libraries, by: opts.by || 'Claude', via: opts.via || 'Claude Code · /visual-setup', note: opts.note || `Sistema generado desde ${basename(opts.tokens)}`, now }), null, 2)}\n`);
  return { carpeta: opts.out, namespace, ficheros: files, componentes: components, caidos, avisos, google_fonts: googleFonts };
}

function parseArgs(argv) {
  const args = { cmd: argv[0] };
  for (let i = 1; i < argv.length; i++) {
    const a = argv[i];
    const next = () => argv[++i];
    if (a === '--no-google-fonts') args.googleFonts = false;
    else if (a === '--components') args.components = next().split(',').filter(Boolean);
    else if (a.startsWith('--')) args[a.slice(2).replace(/-([a-z])/g, (_, c) => c.toUpperCase())] = next();
  }
  return args;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.cmd !== 'build') {
    console.error('Uso: node ds-artifact.mjs build --tokens <design-system.tokens.json> --out <carpeta> --title <nombre> [--namespace Ns] [--bundle-js f --bundle-css f --types f] [--design-md f] [--index f] [--fonts-dir d]');
    process.exit(1);
  }
  for (const k of ['tokens', 'out', 'bundleJs', 'bundleCss', 'types', 'designMd', 'index', 'fontsDir']) if (args[k] && !isAbsolute(args[k])) args[k] = resolve(args[k]);
  try {
    console.log(JSON.stringify(build(args), null, 2));
  } catch (e) {
    console.error(`ds-artifact: ${e.message}`);
    process.exit(1);
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) main();
