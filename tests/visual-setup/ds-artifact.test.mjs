/**
 * UC-9204 (US-92): cada proyecto tiene un sistema de diseño utilizable desde el lienzo.
 *
 * - AC-01: el sistema publicado lleva tokens.css con todas las variables y una clase por estilo de
 *   texto, para que el lienzo pinte con sus valores sin declarar variables en los artboards.
 * - AC-02: los componentes compilados del proyecto se publican como un script clásico con su
 *   cabecera, y el README explica cómo cargarlos y montarlos.
 *
 * Ejecutar: node --test tests/visual-setup/ds-artifact.test.mjs
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  build,
  checkBundle,
  colorValueError,
  componentNames,
  componentProps,
  googleFontsUrl,
  identityColors,
  refusedSection,
  tokensCss,
  validateTokens,
} from '../../.claude/skills/visual-setup/scripts/ds-artifact.mjs';

const repoRoot = resolve(fileURLToPath(import.meta.url), '../../..');
const TINTA = join(repoRoot, 'tests/fixtures/design_system/tinta.design-system.tokens.json');
const tinta = () => JSON.parse(readFileSync(TINTA, 'utf8'));

test('los tokens de Tinta pasan enteros: nada se cae', () => {
  const { tokens, caidos } = validateTokens(tinta());
  assert.deepEqual(caidos, []);
  assert.equal(tokens.color.tokens.length, tinta().color.tokens.length);
  assert.deepEqual(tokens.color.themes.map((t) => t.id), ['light', 'dark']);
});

test('lo que la página no lee se cae con su motivo, y lo demás se queda', () => {
  const { tokens, caidos } = validateTokens({
    color: {
      themes: [{ id: 'light' }, { id: 'dark' }],
      tokens: [
        { name: 'ink', value: { light: '#1A1B1E', dark: '#F2F1EE' } },
        { name: 'brand', value: 'oklch(0.62 0.19 250)' },
        { name: 'link', value: '{ink}' },
        { name: 'roto', value: '{no-existe}' },
        { name: 'ciclo', value: '{ciclo}' },
        { name: 'nombre', value: 'red' },
        { name: 'mezcla', value: 'color-mix(in srgb, red 50%, blue)' },
        { name: 'con espacio', value: '#000' },
        { name: 'ink', value: '#000' },
      ],
    },
    spacing: { tokens: [{ name: 'space-4', value: '16px' }, { name: 'space-x', value: 'calc(1px + 2px)' }, { name: 'ink', value: '4px' }] },
    radius: { tokens: [{ name: 'radius-md', value: 6 }] },
    motion: { tokens: [{ name: 'dur', value: '120ms' }] },
    dtcg: { brand: { $value: '#f00' } },
  });
  assert.deepEqual(tokens.color.tokens.map((t) => t.name), ['ink', 'brand', 'link']);
  assert.equal(tokens.color.tokens[0].value.light, '#1a1b1e', 'hex en minúsculas');
  assert.deepEqual(tokens.spacing.tokens.map((t) => t.name), ['space-4']);
  const motivo = (n) => caidos.find((c) => c.nombre === n || c.nombre?.startsWith(`${n} `))?.motivo;
  assert.match(motivo('roto'), /no existe/);
  assert.match(motivo('ciclo'), /ciclo/);
  assert.match(motivo('nombre'), /con nombre/);
  assert.match(motivo('mezcla'), /color-mix/);
  assert.match(motivo('con espacio'), /nombre no válido/);
  assert.ok(caidos.some((c) => c.familia === 'spacing' && c.nombre === 'ink' && /repetido/.test(c.motivo)), 'un nombre por familia, salvo type');
  assert.ok(caidos.some((c) => c.familia === 'motion'));
  assert.ok(caidos.some((c) => c.familia === 'dtcg' && /DTCG/.test(c.motivo)));
});

test('valores de color: los que lee el tipo', () => {
  for (const ok of ['#fff', '#ffffff80', 'rgb(1, 2, 3)', 'hsl(210 50% 40%)', 'oklch(0.7 0.1 200)', 'color(display-p3 1 0 0)', '{ink}']) assert.equal(colorValueError(ok), null, ok);
  for (const bad of ['transparent', 'currentColor', 'var(--x)', 'rgb(var(--r), 0, 0)', 'url(x)']) assert.ok(colorValueError(bad), bad);
});

test('AC-01: tokens.css lleva la forma compilada del tipo y su primera línea', () => {
  const { tokens } = validateTokens(tinta());
  const css = tokensCss(tokens, 'Tinta');
  assert.equal(css.split('\n')[0], '/* Tinta — generated from tokens.json */', 'la página adopta solo un fichero con esta línea');
  assert.match(css, /:root, \[data-theme="light"\] \{\n {2}--paper-100: #ffffff;/);
  assert.match(css, /\[data-theme="dark"\] \{\n {2}--paper-100: #1a1b1e;/);
  assert.match(css, /--accent: var\(--ink-900\);/, 'un alias pasa a var()');
  assert.match(css, /:root \{\n {2}--space-1: 4px;/);
  assert.match(css, /--font-sans: "IBM Plex Sans"/);
  assert.match(css, /^\.display-lg \{ font-family: var\(--font-sans\); font-size: 24px; line-height: 30px; font-weight: 600; letter-spacing: -0\.01em; \}$/m);
  // Cada color del primer tema y cada estilo de texto tienen su declaración.
  for (const t of tokens.color.tokens) assert.ok(css.includes(`--${t.name}:`), t.name);
  for (const s of tokens.type.groups.flatMap((g) => g.styles)) assert.ok(css.includes(`.${s.name} {`), s.name);
});

test('tipografías: Google Fonts con los pesos que usan los estilos; una fuente con fichero lleva @font-face', () => {
  const { tokens } = validateTokens(tinta());
  assert.equal(googleFontsUrl(tokens), 'https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');
  const conFichero = { ...tokens, type: { ...tokens.type, fonts: [{ family: 'IBM Plex Sans', file: 'IBMPlexSans.woff2', weight: '400 700' }] } };
  assert.match(googleFontsUrl(conFichero), /^https:\/\/fonts\.googleapis\.com\/css2\?family=IBM\+Plex\+Mono/, 'la que tiene fichero no se pide a Google');
  assert.match(tokensCss(conFichero, 'T'), /@font-face \{ font-family: "IBM Plex Sans"; src: url\("fonts\/IBMPlexSans\.woff2"\) format\("woff2"\); font-weight: 400 700;/);
});

test('AC-02: el bundle tiene que ser un script clásico que asigna window.<Ns>', () => {
  assert.deepEqual(checkBundle('var Acme=(()=>{return {}})();', 'Acme'), [], 'esbuild --global-name');
  assert.deepEqual(checkBundle('window.Acme = { Button };', 'Acme'), []);
  assert.ok(checkBundle('export function Button() {}', 'Acme').some((e) => /script clásico/.test(e)));
  assert.ok(checkBundle('window.Acme = {}; // </script>', 'Acme').some((e) => /<\/script/.test(e)));
  assert.ok(checkBundle('window.Otro = {}', 'Acme').some((e) => /window\.Acme/.test(e)));
});

test('componentes y props desde los tipos', () => {
  const types = 'export interface ButtonProps { variant?: "a" | "b"; label: string }\nexport declare function Button(p: ButtonProps): JSX.Element;\nexport const Badge = () => null;\nexport declare function useThing(): void;';
  assert.deepEqual(componentNames(types), ['Button', 'Badge']);
  assert.deepEqual(componentProps(types, 'Button'), [{ prop: 'variant', opcional: true, tipo: '"a" | "b"' }, { prop: 'label', opcional: false, tipo: 'string' }]);
});

test('la sección de lo que se rehúsa del DESIGN.md pasa al README tal cual', () => {
  const md = '# Diseño\n\n## Paleta\n\nx\n\n## Lo que se rehúsa\n\n- Degradados violeta.\n- Inter como única voz.\n\n## Movimiento\n\ny\n';
  assert.equal(refusedSection(md), '- Degradados violeta.\n- Inter como única voz.');
  assert.equal(refusedSection('# Nada'), null);
});

test('la portada toma los colores de identidad, no las superficies', () => {
  const { tokens } = validateTokens(tinta());
  const picked = identityColors(tokens);
  assert.ok(picked.length >= 1 && picked.length <= 4);
  assert.ok(!picked.some((n) => n.startsWith('paper-')), picked.join());
});

test('AC-01/AC-02: build deja el sistema completo y el README dice cómo cargarlo', () => {
  const out = mkdtempSync(join(tmpdir(), 'ds-'));
  const src = mkdtempSync(join(tmpdir(), 'ds-src-'));
  try {
    writeFileSync(join(src, 'bundle.js'), 'var Acme=(()=>{const R=window.React;function Button(p){return R.createElement("button",null,p.children)}return {Button}})();');
    writeFileSync(join(src, 'bundle.css'), '.acme-btn{background:var(--accent)}');
    writeFileSync(join(src, 'index.d.ts'), 'export interface ButtonProps { children?: React.ReactNode }\nexport declare function Button(props: ButtonProps): JSX.Element;\n');
    writeFileSync(join(src, 'DESIGN.md'), '# D\n\n## Lo que se rehúsa\n\n- Degradados.\n');
    const r = build({ tokens: TINTA, out, title: 'Acme', namespace: 'Acme', bundleJs: join(src, 'bundle.js'), bundleCss: join(src, 'bundle.css'), types: join(src, 'index.d.ts'), designMd: join(src, 'DESIGN.md'), by: 'Prueba', now: '2026-10-10T12:00:00Z' });
    for (const f of ['tokens.json', 'tokens.css', 'components/bundle.css', 'components/bundle.js', 'components/index.d.ts', 'components/Button/README.md', 'components/Button/preview.html', 'README.md', 'components/Cover/preview.html', 'design-system.json']) {
      assert.ok(existsSync(join(out, 'project', f)), f);
    }
    assert.deepEqual(r.componentes, ['Button']);
    const p = (f) => readFileSync(join(out, 'project', f), 'utf8');
    assert.match(p('components/bundle.js'), /^\/\* @ds-bundle: \{"format":4,"namespace":"Acme","components":\[\{"name":"Button"\}\]\} \*\/\n/);
    assert.match(p('components/bundle.css'), /^@import url\("https:\/\/fonts\.googleapis\.com\/css2\?/);
    assert.match(p('components/bundle.css'), /\.acme-btn\{background:var\(--accent\)\}/);
    assert.match(p('components/Button/preview.html'), /^<!-- @dsCard group="Componentes" height=96 -->/);
    const readme = p('README.md');
    assert.match(readme, /## Consuming this system/);
    assert.match(readme, /`tokens\.css`/);
    assert.match(readme, /`components\/bundle\.js`: asigna `window\.Acme`/);
    assert.match(readme, /<x-import component-from-global-scope="Acme\.Button">/);
    assert.match(readme, /## Lo que se rehúsa\n\n- Degradados\./);
    assert.match(p('components/Cover/preview.html'), /^<!-- @dsCard height=288 -->/);
    const index = JSON.parse(p('design-system.json'));
    assert.deepEqual(index.createdOnFiles, { v: 1, at: '2026-10-10T12:00:00Z' });
    assert.equal(index.namespace, 'Acme');
    assert.deepEqual(index.libraries, [{ name: 'react', version: '18' }, { name: 'react-dom', version: '18' }]);
    assert.equal(JSON.parse(p('tokens.json')).meta.source, 'specbox');

    // Al actualizar: el índice leído conserva sus claves y su marca.
    const leido = join(src, 'leido.json');
    writeFileSync(leido, JSON.stringify({ ...index, groups: ['Logos'], assetGroups: { Logos: { name: 'Logos' } }, createdOnFiles: { v: 1, at: '2026-01-01T00:00:00Z' } }));
    build({ tokens: TINTA, out, title: 'Acme', namespace: 'Acme', index: leido, now: '2026-10-11T12:00:00Z' });
    const again = JSON.parse(p('design-system.json'));
    assert.deepEqual(again.groups, ['Logos']);
    assert.equal(again.createdOnFiles.at, '2026-01-01T00:00:00Z');
    assert.equal(again.lastChange.at, '2026-10-11T12:00:00Z');
    // Un design-system.json sin marca no es un índice: no se escribe encima.
    writeFileSync(leido, JSON.stringify({ title: 'x' }));
    assert.throws(() => build({ tokens: TINTA, out, title: 'Acme', index: leido }), /sin marca|no tiene marca/);
  } finally {
    rmSync(out, { recursive: true, force: true });
    rmSync(src, { recursive: true, force: true });
  }
});
