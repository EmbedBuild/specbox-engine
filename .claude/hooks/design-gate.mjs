#!/usr/bin/env node
/**
 * design-gate.mjs — PostToolUse hook for Write/Edit on UI page files (US-91 · UC-9103).
 *
 * When an agent writes a UI page and its feature has no design in doc/design/{feature}/ (at least
 * one HTML), the agent gets the warning in the same session: exit 2 with the message on stderr,
 * which Claude Code feeds back to the model. PostToolUse cannot undo the write; the warning says
 * what to do before going on with that screen.
 *
 * With a design, a page without its traceability comment gets a note through `additionalContext`
 * (exit 0: informs, does not block).
 *
 * Claude Design (US-92 · UC-9202): what counts as a design is the frozen view `/design-review import`
 * leaves (`{artboard}.html`), not the canvas source (`canvas/*.dc.html`), which needs the canvas
 * engine to render. A page that carries pieces of that engine (`support.js`, `<x-dc>`, `DCLogic`,
 * `<sc-for>`, `<sc-if>`, `<dc-import>`, `<x-import>`, `/_blob/`) gets exit 2: the design-to-code has
 * to start from the frozen view and produce code of the stack.
 *
 * Registered without `if`: the path filter lives here. `if` takes permission-rule globs, not
 * regexes, so the old `Write(src/pages/.*)` only matched dotfiles and the gate never ran. The input
 * is Claude Code's PostToolUse payload: the path comes absolute in `tool_input.file_path`.
 *
 * Pages detected (path relative to the project root):
 *   Flutter  lib/presentation/features/{feature}/(page|pages|layouts)/*.dart
 *            presentation/pages/[{feature}/]*.dart
 *   Web      src/pages/[{feature}/]*.{tsx,jsx,ts,js,astro,vue,svelte}
 *   Next.js  app/**\/page.{tsx,jsx,ts,js} (feature = first segment that is not a group or param)
 */

import { readStdin, fileExists, findFiles } from './lib/utils.mjs';
import { getProjectConfig } from './lib/config.mjs';
import { readFileSync } from 'fs';
import { basename, extname, isAbsolute, join, relative, resolve, sep } from 'path';

let payload = {};
try {
  payload = JSON.parse(readStdin() || '{}');
} catch {
  process.exit(0);
}

const toolInput = payload.tool_input ?? payload.toolInput ?? {};
const filePath = toolInput.file_path || payload.file_path || '';
if (!filePath) process.exit(0);

const root = resolve(payload.cwd || process.cwd());
const rel = (isAbsolute(filePath) ? relative(root, filePath) : filePath).split(sep).join('/');
if (!rel || rel.startsWith('../')) process.exit(0);

/** The feature a UI page belongs to, or '' when the file is not a page. */
function pageFeature(path) {
  const stem = (p) => basename(p, extname(p));
  let m = path.match(/(?:^|\/)presentation\/features\/([^/]+)\/(?:page|pages|layouts)\/[^/]+\.dart$/);
  if (m) return m[1];
  m = path.match(/(?:^|\/)presentation\/pages\/(?:([^/]+)\/)?([^/]+)\.dart$/);
  if (m) return m[1] || stem(m[2]);
  m = path.match(/(?:^|\/)src\/pages\/(?:([^/]+)\/)?([^/]+)\.(?:tsx|jsx|ts|js|astro|vue|svelte)$/);
  if (m) return m[1] || stem(m[2]);
  m = path.match(/(?:^|\/)app\/((?:[^/]+\/)*)page\.(?:tsx|jsx|ts|js)$/);
  if (m) {
    const segment = m[1].split('/').find((s) => s && !/^[([@]/.test(s));
    return segment || 'index';
  }
  return '';
}

const feature = pageFeature(rel);
if (!feature) process.exit(0);

// Pieces of the Claude Design canvas engine: the page would not work outside the canvas.
const ENGINE_TRACES = [
  ['support.js', /\bsupport\.js\b/],
  ['<x-dc>', /<x-dc[\s>]/i],
  ['DCLogic', /\bDCLogic\b/],
  ['<sc-for>', /<sc-for[\s>]/i],
  ['<sc-if>', /<sc-if[\s>]/i],
  ['<dc-import>', /<dc-import[\s>]/i],
  ['<x-import>', /<x-import[\s>]/i],
  ['/_blob/', /\/_blob\/[0-9a-f]{8,}/],
];
const written = resolve(root, rel);
if (fileExists(written)) {
  let text = '';
  try { text = readFileSync(written, 'utf-8'); } catch { /* unreadable: nothing to say */ }
  const traces = ENGINE_TRACES.filter(([, re]) => re.test(text)).map(([name]) => name);
  if (traces.length) {
    process.stderr.write(
      [
        `PUERTA DE DISEÑO: ${rel} lleva piezas del motor del lienzo de Claude Design (${traces.join(', ')}).`,
        'Esa página solo funciona dentro del lienzo. El design-to-code parte de la vista congelada',
        `(doc/design/${feature}/{artboard}.html, de /design-review import) y produce código del stack,`,
        'con los valores de los tokens del sistema. Quita esas piezas antes de seguir.',
        '',
      ].join('\n'),
    );
    process.exit(2);
  }
}

// Multi-repo: the designs may live in the orchestrator repo.
const { orchestratorRoot } = getProjectConfig();
const designDir = resolve(root, orchestratorRoot, 'doc', 'design', feature);
const shownDir = relative(root, designDir).split(sep).join('/') || '.';
// `page.tsx` and `index.tsx` say nothing: the screen is then named after its feature.
const stem = basename(rel, extname(rel));
const screen = ['page', 'index'].includes(stem) ? feature : stem;

// A canvas source (`.dc.html`) is not a design on its own: it needs the canvas engine.
if (findFiles(designDir, /\.html$/).filter((f) => !f.endsWith('.dc.html')).length === 0) {
  process.stderr.write(
    [
      `PUERTA DE DISEÑO: ${rel} es una página de interfaz y la feature «${feature}» no tiene diseño`,
      `(no hay ningún HTML en ${shownDir}/).`,
      'La escritura ya está hecha. Antes de seguir con esta pantalla:',
      `  1. /design-review brief ${screen} y /design-review direction ${screen}: para quién es y qué dirección toma.`,
      '  2. Genera el candidato con la cadena de /plan (Paso 6); dentro de /implement, con su Paso 3.3.',
      '  3. Implementa desde ese diseño, con colores, tipografía y espaciado de los tokens del sistema (D18).',
      'Si esta página no necesita diseño (un cambio menor en una pantalla que ya existe), dilo al usuario.',
      '',
    ].join('\n'),
  );
  process.exit(2);
}

// Design exists: the page should say which design it comes from (AG-08 Check 6). A note, not a block.
if (fileExists(written)) {
  try {
    const head = readFileSync(written, 'utf-8').split('\n').slice(0, 10).join('\n');
    if (!head.includes('Generated from: doc/design/')) {
      process.stdout.write(
        JSON.stringify({
          hookSpecificOutput: {
            hookEventName: 'PostToolUse',
            additionalContext:
              `Trazabilidad de diseño: ${rel} no dice de qué diseño sale. Añade en sus 10 primeras líneas ` +
              `«// Generated from: doc/design/${feature}/{pantalla}.html» (AG-08, Check 6).`,
          },
        }),
      );
    }
  } catch { /* unreadable: nothing to say */ }
}

process.exit(0);
