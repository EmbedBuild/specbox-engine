#!/usr/bin/env node
// /design-review verify para Flutter (US-91 · UC-9104).
//
//   node verify-flutter.mjs init --name <pantalla> --import <package:app/…dart> [--import …] \
//        --screen "<widget de la pantalla con su tema y sus datos de prueba>"
//     → escribe test/design_review/<pantalla>_design_review_test.dart desde la plantilla
//
//   node verify-flutter.mjs <test/design_review/<pantalla>_design_review_test.dart> --out <dir> \
//        [--name <pantalla>] [--previous <verify.json>] [--sources <brief.md,prd.md>]
//     → capturas a 390 y 820 con las pruebas de widgets, desbordamientos y reglas del código Dart
//
// Sin simulador ni dependencias nuevas: solo flutter_test, que trae todo proyecto Flutter. Usa
// `fvm flutter` si el proyecto fija versión con fvm, si no `flutter` (FLUTTER_CMD lo fuerza).
// verify.mjs delega aquí cuando el destino es un .dart.

import { spawnSync } from 'node:child_process';
import { copyFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { FLUTTER_RULES, scanPaths } from './flutter-rules.mjs';
import { numbersIn, numbersWithoutSource } from './verify.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const TEMPLATE = join(here, 'flutter', 'design_review_golden_test.dart.tmpl');
export const FLUTTER_WIDTHS = [390, 820];

/** Raíz del proyecto Flutter: la primera carpeta hacia arriba con pubspec.yaml. */
export function flutterRoot(from) {
  let dir = resolve(from);
  for (let i = 0; i < 30; i++) {
    if (existsSync(join(dir, 'pubspec.yaml'))) return dir;
    const up = dirname(dir);
    if (up === dir) break;
    dir = up;
  }
  return null;
}

const onPath = (cmd) => spawnSync(process.platform === 'win32' ? 'where' : 'which', [cmd], { encoding: 'utf8' }).status === 0;

/** Orden para lanzar flutter en este proyecto, o null si no hay. */
export function flutterCommand(root, env = process.env, has = onPath) {
  if (env.FLUTTER_CMD) return env.FLUTTER_CMD.split(/\s+/).filter(Boolean);
  const pinned = existsSync(join(root, '.fvmrc')) || existsSync(join(root, '.fvm', 'fvm_config.json'));
  if (pinned && has('fvm')) return ['fvm', 'flutter'];
  if (has('flutter')) return ['flutter'];
  if (has('fvm')) return ['fvm', 'flutter'];
  return null;
}

/** Escribe la prueba de captura de una pantalla desde la plantilla. */
export function writeGoldenTest({ root, name, imports, screen }) {
  if (!/^[a-z][a-z0-9_]*$/.test(name)) throw new Error(`El nombre «${name}» tiene que ser snake_case (es el nombre de un fichero Dart).`);
  if (!screen) throw new Error('Falta --screen: el widget de la pantalla con su tema y sus datos de prueba.');
  const body = readFileSync(TEMPLATE, 'utf8')
    .replaceAll('{{NAME}}', name)
    .replace('{{IMPORTS}}', imports.map((i) => `import '${i}';`).join('\n'))
    .replace('{{SCREEN}}', screen);
  const file = join(root, 'test', 'design_review', `${name}_design_review_test.dart`);
  mkdirSync(dirname(file), { recursive: true });
  writeFileSync(file, body);
  return file;
}

/** Carpetas del código de la pantalla: las de cada import `package:<app>/…` de la prueba. */
export function screenSources(testSource, root) {
  const app = (readFileSync(join(root, 'pubspec.yaml'), 'utf8').match(/^name:\s*(\S+)/m) || [])[1];
  if (!app) return [];
  const dirs = new Set();
  for (const m of testSource.matchAll(new RegExp(`import\\s+'package:${app}/([^']+)'`, 'g'))) {
    const file = join(root, 'lib', m[1]);
    // La carpeta de la feature (…/features/<f>/), o la del fichero si no sigue esa estructura.
    const feature = file.match(/^(.*\/features\/[^/]+)\//);
    dirs.add(feature ? feature[1] : dirname(file));
  }
  return [...dirs].filter(existsSync);
}

/** Líneas `DESIGN_REVIEW …` y `DESIGN_REVIEW_TEXT …` de la salida de flutter test. */
export function parseFlutterOutput(stdout, root) {
  const overflows = [];
  const texts = [];
  for (const line of String(stdout).split('\n')) {
    const m = line.match(/DESIGN_REVIEW(_TEXT)? (\{.*\})\s*$/);
    if (!m) continue;
    let data;
    try { data = JSON.parse(m[2]); } catch { continue; }
    if (m[1]) texts.push(data.texto || '');
    else overflows.push({ ...data, fichero: data.fichero && data.fichero.startsWith(`${root}/`) ? data.fichero.slice(root.length + 1) : data.fichero });
  }
  return { overflows, texto: texts.join('\n') };
}

export async function verifyFlutter({ target, out, name, previous, sources = [], env = process.env }) {
  const started = Date.now();
  const test = resolve(target);
  if (!existsSync(test)) throw new Error(`No existe ${target}. Créalo con: node verify-flutter.mjs init --name … --import … --screen …`);
  const root = flutterRoot(dirname(test));
  if (!root) throw new Error(`${target} no está en un proyecto Flutter (no hay pubspec.yaml).`);
  const cmd = flutterCommand(root, env);
  if (!cmd) {
    const err = new Error('No hay flutter ni fvm en este equipo. verify no instala nada: sin capturas, el revisor trabaja solo sobre el código.');
    err.code = 'NO_FLUTTER';
    throw err;
  }
  const screen = name || test.match(/([a-z0-9_]+)_design_review_test\.dart$/)?.[1] || 'pantalla';
  mkdirSync(out, { recursive: true });

  const run = spawnSync(cmd[0], [...cmd.slice(1), 'test', '--update-goldens', test], { cwd: root, encoding: 'utf8', timeout: 10 * 60 * 1000, env });
  const goldens = join(dirname(test), 'goldens');
  const capturas = {};
  for (const w of FLUTTER_WIDTHS) {
    const src = join(goldens, `${screen}-${w}.png`);
    if (existsSync(src)) {
      copyFileSync(src, join(out, `${screen}-${w}.png`));
      capturas[w] = `${screen}-${w}.png`;
    }
  }
  if (run.status !== 0 && Object.keys(capturas).length === 0) {
    throw new Error(`flutter test falló sin capturas:\n${`${run.stdout}\n${run.stderr}`.trim().split('\n').slice(-25).join('\n')}`);
  }

  const { overflows, texto } = parseFlutterOutput(run.stdout, root);
  const anchos = Object.fromEntries(FLUTTER_WIDTHS.map((w) => {
    const here = overflows.filter((o) => o.ancho === w);
    return [w, { viewport: w, desborda: here.length > 0, sobresalen: here.map((o) => ({ selector: o.fichero ? `${o.fichero}:${o.linea}` : 'desconocido', detalle: o.detalle })) }];
  }));
  const hallazgos = [];
  for (const o of overflows) {
    const seen = hallazgos.find((h) => h.regla === 'desbordamiento' && h.fichero === o.fichero && h.linea === o.linea);
    if (seen) seen.anchos = [...new Set([...(seen.anchos || [seen.ancho]), o.ancho])];
    else hallazgos.push({ regla: 'desbordamiento', selector: o.fichero ? `${o.fichero}:${o.linea}` : 'desconocido', fichero: o.fichero, linea: o.linea, ancho: o.ancho, detalle: o.detalle });
  }
  const codeDirs = screenSources(readFileSync(test, 'utf8'), root);
  for (const f of scanPaths(codeDirs, root)) hallazgos.push({ ...f, selector: `${f.fichero}:${f.linea}:${f.columna}` });

  const report = {
    version: 1,
    stack: 'flutter',
    objetivo: target,
    fecha: new Date().toISOString(),
    anchos,
    capturas,
    hallazgos,
    codigo_revisado: codeDirs.map((d) => d.slice(root.length + 1)),
    numeros: numbersIn(texto),
    prueba: { estado: run.status === 0 ? 'ok' : 'con fallos', salida: run.status === 0 ? undefined : `${run.stdout}`.split('\n').slice(-15).join('\n') },
  };
  if (previous) {
    const prev = JSON.parse(readFileSync(previous, 'utf8'));
    const sourcesText = sources.filter((s) => existsSync(s)).map((s) => readFileSync(s, 'utf8')).join('\n');
    report.dato_sin_fuente = numbersWithoutSource(prev.numeros || [], report.numeros, sourcesText);
  }
  const rules = ['desbordamiento', ...FLUTTER_RULES];
  report.resumen = {
    desborda: Object.fromEntries(Object.entries(anchos).map(([w, m]) => [w, m.desborda])),
    por_regla: Object.fromEntries(rules.map((r) => [r, hallazgos.filter((h) => h.regla === r).length])),
    dato_sin_fuente: report.dato_sin_fuente ? report.dato_sin_fuente.length : undefined,
  };
  report.duracion_ms = Date.now() - started;
  writeFileSync(join(out, `${screen}-verify.json`), JSON.stringify(report, null, 2));
  return report;
}

function parseArgs(argv) {
  const args = { imports: [], sources: [] };
  const rest = [];
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    const next = () => argv[++i];
    if (a === '--out') args.out = next();
    else if (a === '--name') args.name = next();
    else if (a === '--import') args.imports.push(next());
    else if (a === '--screen') args.screen = next();
    else if (a === '--previous') args.previous = next();
    else if (a === '--sources') args.sources = next().split(',').filter(Boolean);
    else rest.push(a);
  }
  args.target = rest[0];
  return args;
}

export function printReport(r, target, out, name) {
  const lines = [`verify (Flutter) · ${target} · ${(r.duracion_ms / 1000).toFixed(1)} s`];
  for (const [w, m] of Object.entries(r.anchos)) lines.push(`  ${w} px: ${m.desborda ? `DESBORDA (${m.sobresalen.map((s) => s.selector).join(', ')})` : 'sin desbordamiento'}`);
  for (const [regla, n] of Object.entries(r.resumen.por_regla)) if (n && regla !== 'desbordamiento') lines.push(`  ${regla}: ${n}`);
  if (r.dato_sin_fuente && r.dato_sin_fuente.length) lines.push(`  dato-sin-fuente: ${r.dato_sin_fuente.join(', ')}`);
  if (r.prueba.estado !== 'ok') lines.push('  la prueba terminó con fallos ajenos al diseño: mira prueba.salida en el informe');
  lines.push(`  informe: ${join(out, `${name}-verify.json`)}`);
  console.log(lines.join('\n'));
}

async function main() {
  const argv = process.argv.slice(2);
  if (argv[0] === 'init') {
    const args = parseArgs(argv.slice(1));
    const root = flutterRoot(process.cwd());
    if (!root) {
      console.error('Ejecútalo desde un proyecto Flutter (no hay pubspec.yaml).');
      process.exit(1);
    }
    try {
      console.log(writeGoldenTest({ root, name: args.name, imports: args.imports, screen: args.screen }));
    } catch (e) {
      console.error(`verify-flutter: ${e.message}`);
      process.exit(1);
    }
    return;
  }
  const args = parseArgs(argv);
  if (!args.target || !args.out) {
    console.error('Uso: node verify-flutter.mjs <prueba.dart> --out <dir> [--name pantalla] [--previous verify.json] [--sources brief.md,prd.md]');
    process.exit(1);
  }
  try {
    const r = await verifyFlutter({ ...args, out: resolve(args.out) });
    printReport(r, args.target, resolve(args.out), args.name || Object.values(r.capturas)[0]?.replace(/-\d+\.png$/, '') || 'pantalla');
  } catch (e) {
    console.error(`verify-flutter: ${e.message}`);
    process.exit(e.code === 'NO_FLUTTER' ? 2 : 1);
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) main();
