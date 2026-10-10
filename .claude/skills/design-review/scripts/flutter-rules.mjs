#!/usr/bin/env node
// /design-review verify para Flutter (US-91 · UC-9104): reglas deterministas sobre el código Dart.
//
// Uso: node flutter-rules.mjs <fichero.dart | carpeta> [...]   → JSON con los hallazgos
//
// Lo que se mide en un navegador con estilos computados, en Flutter se lee en el código: estas
// reglas marcan lo que deja un control por debajo de 48 dp, lo que anula la escala de texto del
// sistema y el movimiento que se sale de la rúbrica. Cada hallazgo lleva fichero, línea y columna.

import { readFileSync, readdirSync, statSync } from 'node:fs';
import { extname, join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

export const FLUTTER_RULES = ['area-pulsacion', 'escala-texto', 'movimiento', 'movimiento-reducido', 'material3', 'emoji-icono'];

const MIN_TAP = 48;
const MAX_MS = 300;
const TAPPABLE = /\b(IconButton|InkWell|InkResponse|GestureDetector|TextButton|ElevatedButton|OutlinedButton|FilledButton|FloatingActionButton|Checkbox|Radio|Switch|Chip|ActionChip|FilterChip|ChoiceChip|PopupMenuButton|ListTile)\b/;
const ANIMATED = /\b(AnimationController|Animated[A-Z]\w*|TweenAnimationBuilder|Hero)\b|\.animate\(/;
const EMOJI = /\p{Extended_Pictographic}/u;

/** Hallazgos de un fichero Dart. Ignora comentarios de línea y respeta `// design-review:ignore`. */
export function scanDart(source, file = '') {
  const lines = String(source).split('\n');
  const code = lines.map((l) => l.replace(/\/\/.*$/, ''));
  const out = [];
  const add = (regla, i, col, detalle) => {
    if (/design-review:ignore/.test(lines[i])) return;
    out.push({ regla, fichero: file, linea: i + 1, columna: col + 1, detalle, fragmento: lines[i].trim().slice(0, 120) });
  };
  const near = (i, before, after) => code.slice(Math.max(0, i - before), i + after + 1).join('\n');
  const each = (re, i, fn) => {
    for (const m of code[i].matchAll(re)) fn(m);
  };

  for (let i = 0; i < code.length; i++) {
    // Áreas táctiles por debajo de 48 dp.
    each(/MaterialTapTargetSize\.shrinkWrap/g, i, (m) => add('area-pulsacion', i, m.index, 'MaterialTapTargetSize.shrinkWrap: el área táctil baja de 48 dp'));
    each(/VisualDensity\.(compact|comfortable)|VisualDensity\(\s*(horizontal|vertical):\s*-/g, i, (m) =>
      add('area-pulsacion', i, m.index, `${m[0].replace(/\($/, '')}: reduce el área táctil del control`));
    each(/constraints:\s*(const\s+)?BoxConstraints\(\s*\)/g, i, (m) =>
      add('area-pulsacion', i, m.index, 'BoxConstraints() vacío: el control pierde el mínimo de 48 dp'));
    each(/BoxConstraints(?:\.tightFor)?\(([^)]*)\)/g, i, (m) => {
      const small = [...m[1].matchAll(/(minWidth|minHeight|width|height):\s*(\d+(?:\.\d+)?)/g)].filter((x) => Number(x[2]) < MIN_TAP);
      if (small.length && TAPPABLE.test(near(i, 8, 8))) add('area-pulsacion', i, m.index, `${small.map((x) => `${x[1]}: ${x[2]}`).join(', ')}: un control pulsable por debajo de 48 dp`);
    });
    each(/SizedBox\(([^)]*)/g, i, (m) => {
      const head = near(i, 0, 3);
      const small = [...head.slice(head.indexOf('SizedBox(')).split(/child:/)[0].matchAll(/(width|height):\s*(\d+(?:\.\d+)?)/g)].filter((x) => Number(x[2]) < MIN_TAP);
      // Solo cuenta el widget que es su hijo directo, no lo que venga después.
      const child = (head.split(/child:/)[1] || '').match(/^\s*(?:const\s+)?([A-Z]\w*)/)?.[1] || '';
      if (small.length && TAPPABLE.test(child)) add('area-pulsacion', i, m.index, `SizedBox ${small.map((x) => `${x[1]}: ${x[2]}`).join(', ')} alrededor de un control pulsable`);
    });

    // Escala de texto anulada.
    each(/TextScaler\.noScaling|MediaQuery\.withNoTextScaling|textScaleFactor:\s*1(?:\.0)?\b|TextScaler\.linear\(\s*1(?:\.0)?\s*\)/g, i, (m) =>
      add('escala-texto', i, m.index, `${m[0]}: el texto no respeta el tamaño que elige la persona en el sistema`));

    // Movimiento: duraciones de más de 300 ms y curvas que no responden.
    each(/duration:\s*(?:const\s+)?Duration\(\s*(milliseconds|seconds):\s*(\d+)/g, i, (m) => {
      const ms = Number(m[2]) * (m[1] === 'seconds' ? 1000 : 1);
      if (ms > MAX_MS) add('movimiento', i, m.index, `duración de ${ms} ms (máximo ${MAX_MS} en una respuesta al usuario)`);
    });
    each(/Curves\.easeIn\b(?!Out)|Curves\.(bounce\w*|elastic\w*)/g, i, (m) =>
      add('movimiento', i, m.index, m[0] === 'Curves.easeIn' ? 'Curves.easeIn: una respuesta al usuario empieza rápido (easeOut), nunca lenta' : `${m[0]}: movimiento decorativo`));

    // Material 3 apagado.
    each(/useMaterial3:\s*false/g, i, (m) => add('material3', i, m.index, 'useMaterial3: false: el sistema da por hecho Material 3'));

    // Emoji como icono: un literal corto con un pictograma, dentro de Text o como icono.
    each(/(?:Text|icon:\s*(?:const\s+)?Text)\(\s*['"]([^'"]{1,4})['"]/g, i, (m) => {
      if ([...m[1]].some((ch) => EMOJI.test(ch) && !['©', '®', '™'].includes(ch))) add('emoji-icono', i, m.index, `«${m[1]}» como icono`);
    });
  }

  // Animaciones sin mirar si la persona pidió menos movimiento.
  const firstAnimation = code.findIndex((l) => ANIMATED.test(l));
  if (firstAnimation >= 0 && !/disableAnimations|accessibleNavigation/.test(code.join('\n'))) {
    add('movimiento-reducido', firstAnimation, code[firstAnimation].search(ANIMATED), 'anima sin consultar MediaQuery.disableAnimationsOf: no respeta el movimiento reducido');
  }
  return out;
}

/** Ficheros .dart de una lista de ficheros o carpetas (sin generados ni pruebas). */
export function dartFiles(paths) {
  const files = [];
  const walk = (p) => {
    const st = statSync(p);
    if (st.isDirectory()) {
      for (const name of readdirSync(p)) if (!name.startsWith('.') && name !== 'build') walk(join(p, name));
    } else if (extname(p) === '.dart' && !/\.(g|freezed)\.dart$|_test\.dart$/.test(p)) {
      files.push(p);
    }
  };
  for (const p of paths) walk(resolve(p));
  return files;
}

export function scanPaths(paths, root = process.cwd()) {
  return dartFiles(paths).flatMap((f) => scanDart(readFileSync(f, 'utf8'), f.startsWith(`${root}/`) ? f.slice(root.length + 1) : f));
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  const paths = process.argv.slice(2);
  if (!paths.length) {
    console.error('Uso: node flutter-rules.mjs <fichero.dart | carpeta> [...]');
    process.exit(1);
  }
  console.log(JSON.stringify(scanPaths(paths), null, 2));
}
