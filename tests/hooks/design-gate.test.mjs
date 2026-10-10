/**
 * UC-9103 (US-91): la puerta de diseño avisa de verdad.
 *
 * AC-01: cuando un agente escribe una página de interfaz sin diseño previo, recibe el aviso en la
 * misma sesión. Claude Code pasa al modelo el stderr de un PostToolUse que sale con código 2, y el
 * `additionalContext` de uno que sale con 0. Estas pruebas simulan la escritura con la entrada real
 * de Claude Code: `tool_input.file_path` con ruta absoluta y `cwd` del proyecto.
 *
 * Antes no saltaba nunca: el registro usaba `if: Write(src/pages/.*)` (las condiciones son globs de
 * reglas de permisos, no regex), el hook leía `file_path` del nivel superior y salía con 1 por stdout.
 *
 * Ejecutar: node --test tests/hooks/design-gate.test.mjs
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = resolve(fileURLToPath(import.meta.url), '../../..');
const hook = join(repoRoot, '.claude/hooks/design-gate.mjs');

function project() {
  const dir = mkdtempSync(join(tmpdir(), 'design-gate-'));
  return {
    dir,
    write(rel, content = '') {
      mkdirSync(dirname(join(dir, rel)), { recursive: true });
      writeFileSync(join(dir, rel), content);
      return join(dir, rel);
    },
    done: () => rmSync(dir, { recursive: true, force: true }),
  };
}

/** Lanza el hook como lo lanza Claude Code después de un Write. */
function afterWrite(p, absolutePath, tool = 'Write') {
  const payload = {
    hook_event_name: 'PostToolUse',
    tool_name: tool,
    tool_input: { file_path: absolutePath, content: '' },
    tool_response: { filePath: absolutePath, type: 'create' },
    cwd: p.dir,
  };
  return spawnSync(process.execPath, [hook], { cwd: p.dir, input: JSON.stringify(payload), encoding: 'utf8' });
}

test('AC-01: una página de Next.js sin diseño recibe el aviso con código 2 por stderr', () => {
  const p = project();
  try {
    const page = p.write('app/(panel)/propuestas/[id]/page.tsx', 'export default function P() { return null }\n');
    const r = afterWrite(p, page);
    assert.equal(r.status, 2);
    assert.match(r.stderr, /PUERTA DE DISEÑO: app\/\(panel\)\/propuestas\/\[id\]\/page\.tsx/);
    assert.match(r.stderr, /feature «propuestas»/);
    assert.match(r.stderr, /doc\/design\/propuestas\//);
    assert.match(r.stderr, /\/design-review brief propuestas /, 'page.tsx toma el nombre de la feature');
    assert.equal(r.stdout, '');
  } finally {
    p.done();
  }
});

test('AC-01: también con Edit, en Flutter y en src/pages', () => {
  const p = project();
  try {
    for (const [rel, feature] of [
      ['lib/presentation/features/paddock/page/paddock_page.dart', 'paddock'],
      ['lib/presentation/features/paddock/layouts/paddock_mobile_layout.dart', 'paddock'],
      ['lib/presentation/pages/ajustes/ajustes_page.dart', 'ajustes'],
      ['src/pages/precios.astro', 'precios'],
      ['src/pages/panel/index.tsx', 'panel'],
    ]) {
      const r = afterWrite(p, p.write(rel), 'Edit');
      assert.equal(r.status, 2, rel);
      assert.match(r.stderr, new RegExp(`feature «${feature}»`), rel);
    }
  } finally {
    p.done();
  }
});

test('con diseño y comentario de trazabilidad: pasa en silencio', () => {
  const p = project();
  try {
    p.write('doc/design/propuestas/listado.html', '<!-- specbox:design-role=candidate -->\n<html></html>\n');
    const page = p.write('app/propuestas/page.tsx', '// Generated from: doc/design/propuestas/listado.html\nexport default function P() { return null }\n');
    const r = afterWrite(p, page);
    assert.equal(r.status, 0);
    assert.equal(r.stdout, '');
    assert.equal(r.stderr, '');
  } finally {
    p.done();
  }
});

test('con diseño y sin trazabilidad: una nota en additionalContext, sin bloquear', () => {
  const p = project();
  try {
    p.write('doc/design/propuestas/listado.html', '<html></html>\n');
    const r = afterWrite(p, p.write('app/propuestas/page.tsx', 'export default function P() { return null }\n'));
    assert.equal(r.status, 0);
    const out = JSON.parse(r.stdout);
    assert.equal(out.hookSpecificOutput.hookEventName, 'PostToolUse');
    assert.match(out.hookSpecificOutput.additionalContext, /Generated from: doc\/design\/propuestas\//);
  } finally {
    p.done();
  }
});

test('satélite: el diseño puede vivir en el orquestador', () => {
  const p = project();
  try {
    p.write('orq/doc/design/propuestas/listado.html', '<html></html>\n');
    p.write('sat/.claude/settings.local.json', JSON.stringify({ multirepo: { enabled: true, role: 'satellite', orchestrator: '../orq' } }));
    const page = p.write('sat/app/propuestas/page.tsx', '// Generated from: doc/design/propuestas/listado.html\n');
    const payload = { tool_name: 'Write', tool_input: { file_path: page }, cwd: join(p.dir, 'sat') };
    const r = spawnSync(process.execPath, [hook], { cwd: join(p.dir, 'sat'), input: JSON.stringify(payload), encoding: 'utf8' });
    assert.equal(r.status, 0, r.stderr);
  } finally {
    p.done();
  }
});

test('lo que no es una página, o está fuera del proyecto, no se mira', () => {
  const p = project();
  try {
    for (const rel of ['src/components/Boton.tsx', 'lib/data/models/paddock.dart', 'app/api/propuestas/route.ts', 'src/pages/README.md']) {
      const r = afterWrite(p, p.write(rel));
      assert.equal(r.status, 0, rel);
      assert.equal(r.stderr, '', rel);
    }
    const r = afterWrite(p, join(tmpdir(), 'otro', 'app', 'x', 'page.tsx'));
    assert.equal(r.status, 0);
  } finally {
    p.done();
  }
});

test('registro: salta en cualquier Write o Edit, sin una condición que no casa nunca', () => {
  for (const path of ['.claude/settings.json', 'templates/settings.json.template']) {
    const settings = JSON.parse(readFileSync(join(repoRoot, path), 'utf8'));
    for (const matcher of ['Write', 'Edit']) {
      const entries = settings.hooks.PostToolUse
        .filter((g) => g.matcher === matcher)
        .flatMap((g) => g.hooks)
        .filter((h) => h.command.includes('design-gate.mjs'));
      assert.equal(entries.length, 1, `${path} ${matcher}: una sola entrada`);
      assert.equal(entries[0].if, undefined, `${path} ${matcher}: el filtro de rutas lo hace el hook`);
    }
  }
});

// ── UC-9202 (US-92): pantallas traídas de un lienzo de Claude Design ─────

const IMPORTED_VIEW = '<!-- specbox:design-role=candidate · Diseño candidato de Claude Design · proveedor=claude_design · lienzo=https://claude.ai/artifact/abc · version=1-a · artboard=Listado.dc.html -->\n<!doctype html>\n<html><head><meta name="specbox:canvas" content="https://claude.ai/artifact/abc"></head><body><main>Propuestas</main></body></html>\n';

test('UC-9202 AC-02: una pantalla importada del lienzo satisface la puerta igual que una de Stitch', () => {
  const p = project();
  try {
    p.write('doc/design/propuestas/Listado.html', IMPORTED_VIEW);
    p.write('doc/design/propuestas/canvas/Listado.dc.html', '<x-dc><div>{{titulo}}</div></x-dc>\n');
    p.write('doc/design/propuestas/claude-design.json', '{"url":"https://claude.ai/artifact/abc"}\n');
    const page = p.write('app/propuestas/page.tsx', '// Generated from: doc/design/propuestas/Listado.html\nexport default function P() { return null }\n');
    const r = afterWrite(p, page);
    assert.equal(r.status, 0, r.stderr);
    assert.equal(r.stdout, '');
    assert.equal(r.stderr, '');
    // Sin trazabilidad, la misma nota que con Stitch.
    const r2 = afterWrite(p, p.write('app/propuestas/page.tsx', 'export default function P() { return null }\n'));
    assert.equal(r2.status, 0);
    assert.match(JSON.parse(r2.stdout).hookSpecificOutput.additionalContext, /Generated from: doc\/design\/propuestas\//);
  } finally {
    p.done();
  }
});

test('UC-9202: la fuente del lienzo sola (.dc.html) no cuenta como diseño, porque necesita el motor', () => {
  const p = project();
  try {
    p.write('doc/design/propuestas/canvas/Listado.dc.html', '<x-dc><div>{{titulo}}</div></x-dc>\n');
    const r = afterWrite(p, p.write('app/propuestas/page.tsx', 'export default function P() { return null }\n'));
    assert.equal(r.status, 2);
    assert.match(r.stderr, /no tiene diseño/);
  } finally {
    p.done();
  }
});

test('UC-9202 AC-04: una página con piezas del motor del lienzo se bloquea con exit 2', () => {
  const cases = [
    ['<script src="./support.js"></script>', 'support.js'],
    ['<x-dc><div>{{titulo}}</div></x-dc>', '<x-dc>'],
    ['class Component extends DCLogic {}', 'DCLogic'],
    ['<sc-for list="{{items}}" as="it"></sc-for>', '<sc-for>'],
    ['<x-import component-from-global-scope="Cds.Button"></x-import>', '<x-import>'],
    ['<img src="/_blob/0123456789abcdef0123456789abcdef">', '/_blob/'],
  ];
  for (const [snippet, name] of cases) {
    const p = project();
    try {
      p.write('doc/design/propuestas/Listado.html', IMPORTED_VIEW);
      const page = p.write('src/pages/propuestas.astro', `---\n// Generated from: doc/design/propuestas/Listado.html\n---\n${snippet}\n`);
      const r = afterWrite(p, page);
      assert.equal(r.status, 2, name);
      assert.match(r.stderr, /piezas del motor del lienzo de Claude Design/, name);
      assert.ok(r.stderr.includes(name), name);
      assert.match(r.stderr, /vista congelada/, name);
    } finally {
      p.done();
    }
  }
});
