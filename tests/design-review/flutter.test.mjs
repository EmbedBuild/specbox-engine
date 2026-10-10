/**
 * UC-9104 (US-91): /design-review verify funciona en apps Flutter.
 *
 * - AC-01: las reglas de pulido y movimiento tienen su versión para Flutter (48 dp, curvas y
 *   duraciones, Material 3) y verify elige la del stack: un destino .dart va por Flutter.
 * - AC-02: capturas a 390 y 820 con las pruebas de widgets, sin simulador. La integración necesita
 *   flutter (SPECBOX_FLUTTER=<orden>, p. ej. «fvm flutter») y se salta si no está.
 * - AC-03: áreas táctiles por debajo de 48 dp y escala de texto anulada, cada una con su ubicación.
 *
 * Ejecutar: SPECBOX_FLUTTER="fvm flutter" node --test tests/design-review/flutter.test.mjs
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { FLUTTER_RULES, scanDart } from '../../.claude/skills/design-review/scripts/flutter-rules.mjs';
import { flutterCommand, parseFlutterOutput, screenSources, verifyFlutter, writeGoldenTest } from '../../.claude/skills/design-review/scripts/verify-flutter.mjs';

const repoRoot = resolve(fileURLToPath(import.meta.url), '../../..');
const fixtures = join(repoRoot, 'tests/design-review/fixtures/flutter');
const verifyScript = join(repoRoot, '.claude/skills/design-review/scripts/verify.mjs');
const tells = readFileSync(join(fixtures, 'pantalla_con_tells.dart'), 'utf8');
const clean = readFileSync(join(fixtures, 'pantalla_limpia.dart'), 'utf8');
const lineOf = (src, needle) => src.split('\n').findIndex((l) => l.includes(needle)) + 1;
const FLUTTER = process.env.SPECBOX_FLUTTER;
const needsFlutter = { skip: FLUTTER ? false : 'sin flutter (SPECBOX_FLUTTER="fvm flutter" para ejecutarla)' };

test('AC-03: áreas por debajo de 48 dp y escala de texto anulada, con su línea', () => {
  const found = scanDart(tells, 'pantalla_con_tells.dart');
  const at = (regla) => found.filter((f) => f.regla === regla).map((f) => f.linea);
  assert.deepEqual(at('escala-texto'), [lineOf(tells, 'withNoTextScaling')]);
  assert.deepEqual(at('area-pulsacion').sort((a, b) => a - b), [lineOf(tells, 'BoxConstraints()'), lineOf(tells, 'shrinkWrap')]);
  for (const f of found) assert.ok(f.columna > 0 && f.fichero === 'pantalla_con_tells.dart');
});

test('AC-01: movimiento de la rúbrica en Flutter (duración, curva, movimiento reducido) y emoji', () => {
  const found = scanDart(tells);
  assert.ok(found.some((f) => f.regla === 'movimiento' && /600 ms/.test(f.detalle)));
  assert.ok(found.some((f) => f.regla === 'movimiento' && /Curves\.easeIn/.test(f.detalle)));
  assert.ok(found.some((f) => f.regla === 'movimiento-reducido'));
  assert.ok(found.some((f) => f.regla === 'emoji-icono'));
  assert.ok(scanDart('ThemeData(useMaterial3: false)').some((f) => f.regla === 'material3'));
});

test('una pantalla que cumple no da hallazgos', () => {
  assert.deepEqual(scanDart(clean), []);
});

test('más casos de 48 dp: densidad compacta, restricciones y cajas pequeñas en controles', () => {
  const src = [
    "IconButton(visualDensity: VisualDensity.compact, onPressed: f, icon: const Icon(Icons.add)),",
    "IconButton(constraints: const BoxConstraints(minWidth: 32, minHeight: 32), onPressed: f, icon: i),",
    'SizedBox(',
    '  width: 32, height: 32,',
    '  child: IconButton(onPressed: f, icon: i),',
    '),',
    'SizedBox(height: 32, child: Text("no es un control")),',
    "Text('ok', textScaleFactor: 1.0),",
    '// MaterialTapTargetSize.shrinkWrap en un comentario no cuenta',
    "TextButton(style: TextButton.styleFrom(tapTargetSize: MaterialTapTargetSize.shrinkWrap), onPressed: f, child: c), // design-review:ignore",
  ].join('\n');
  const found = scanDart(src);
  const lines = (regla) => found.filter((f) => f.regla === regla).map((f) => f.linea);
  assert.deepEqual(lines('area-pulsacion'), [1, 2, 3]);
  assert.deepEqual(lines('escala-texto'), [8]);
  assert.deepEqual(FLUTTER_RULES.includes('area-pulsacion') && FLUTTER_RULES.includes('escala-texto'), true);
});

test('la salida de flutter test se lee: desbordamientos con su fichero y el texto visible', () => {
  const root = '/proyecto';
  const out = [
    '00:00 +0: propuestas a 390',
    'DESIGN_REVIEW {"regla":"desbordamiento","ancho":390,"detalle":"A RenderFlex overflowed by 82 pixels on the right.","fichero":"/proyecto/lib/a.dart","linea":31}',
    'DESIGN_REVIEW_TEXT {"ancho":390,"texto":"Reforma 4.800 €"}',
    'ruido DESIGN_REVIEW {roto',
  ].join('\n');
  const r = parseFlutterOutput(out, root);
  assert.deepEqual(r.overflows.map((o) => [o.fichero, o.linea, o.ancho]), [['lib/a.dart', 31, 390]]);
  assert.match(r.texto, /4\.800/);
});

test('el código revisado sale de los imports de la app en la prueba; flutter se elige por proyecto', () => {
  const root = mkdtempSync(join(tmpdir(), 'flutter-src-'));
  try {
    writeFileSync(join(root, 'pubspec.yaml'), 'name: mi_app\n');
    mkdirSync(join(root, 'lib/presentation/features/propuestas/page'), { recursive: true });
    const testSrc = "import 'package:flutter/material.dart';\nimport 'package:mi_app/presentation/features/propuestas/page/propuestas_page.dart';";
    assert.deepEqual(screenSources(testSrc, root), [join(root, 'lib/presentation/features/propuestas')]);
    assert.deepEqual(flutterCommand(root, { FLUTTER_CMD: 'fvm flutter' }), ['fvm', 'flutter']);
    writeFileSync(join(root, '.fvmrc'), '{"flutter":"3.44.0"}');
    assert.deepEqual(flutterCommand(root, {}, (c) => c === 'fvm' || c === 'flutter'), ['fvm', 'flutter']);
    assert.equal(flutterCommand(root, {}, () => false), null);
    const file = writeGoldenTest({ root, name: 'propuestas', imports: ['package:mi_app/x.dart'], screen: 'const MaterialApp(home: X())' });
    const body = readFileSync(file, 'utf8');
    assert.ok(body.includes("import 'package:mi_app/x.dart';") && body.includes('Widget buildScreen() => const MaterialApp(home: X());'));
    assert.ok(!/\{\{[A-Z]+\}\}/.test(body), 'no quedan marcadores sin rellenar');
    assert.throws(() => writeGoldenTest({ root, name: 'Mal-Nombre', imports: [], screen: 'x' }), /snake_case/);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test('sin flutter ni fvm: lo dice y sale con código 2, sin instalar nada', () => {
  const root = mkdtempSync(join(tmpdir(), 'sin-flutter-'));
  try {
    writeFileSync(join(root, 'pubspec.yaml'), 'name: mi_app\n');
    mkdirSync(join(root, 'test/design_review'), { recursive: true });
    writeFileSync(join(root, 'test/design_review/x_design_review_test.dart'), '');
    const res = spawnSync(process.execPath, [verifyScript, 'test/design_review/x_design_review_test.dart', '--out', join(root, 'out')], {
      cwd: root, encoding: 'utf8', env: { PATH: '/usr/bin:/bin', HOME: root },
    });
    assert.equal(res.status, 2, res.stderr);
    assert.match(res.stderr, /No hay flutter ni fvm/);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test('AC-02: capturas a 390 y 820 con las pruebas de widgets, desbordamiento y reglas', needsFlutter, async () => {
  const dir = mkdtempSync(join(tmpdir(), 'flutter-verify-'));
  try {
    const cmd = FLUTTER.split(/\s+/);
    const created = spawnSync(cmd[0], [...cmd.slice(1), 'create', '--offline', '--empty', '--platforms=web', '--project-name', 'propuestas_app', 'app'], { cwd: dir, encoding: 'utf8' });
    assert.equal(created.status, 0, created.stderr);
    const root = join(dir, 'app');
    const page = join(root, 'lib/presentation/features/propuestas/page/propuestas_page.dart');
    mkdirSync(join(root, 'lib/presentation/features/propuestas/page'), { recursive: true });
    writeFileSync(page, tells);
    const testFile = writeGoldenTest({
      root,
      name: 'propuestas',
      imports: ['package:propuestas_app/presentation/features/propuestas/page/propuestas_page.dart'],
      screen: 'const MaterialApp(debugShowCheckedModeBanner: false, home: PropuestasPage())',
    });
    const out = join(dir, 'out');
    const r = await verifyFlutter({ target: testFile, out, env: { ...process.env, FLUTTER_CMD: FLUTTER } });
    assert.deepEqual(r.capturas, { 390: 'propuestas-390.png', 820: 'propuestas-820.png' });
    assert.ok(existsSync(join(out, 'propuestas-390.png')) && existsSync(join(out, 'propuestas-820.png')));
    assert.equal(r.anchos[390].desborda, true);
    assert.equal(r.anchos[820].desborda, false);
    const overflow = r.hallazgos.find((h) => h.regla === 'desbordamiento');
    assert.equal(overflow.linea, lineOf(tells, 'const Row('));
    assert.ok(r.hallazgos.some((h) => h.regla === 'area-pulsacion' && h.fichero.endsWith('propuestas_page.dart')));
    assert.ok(r.numeros.includes('4800€'), 'el texto visible llega al informe');
    assert.equal(r.prueba.estado, 'ok');
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
