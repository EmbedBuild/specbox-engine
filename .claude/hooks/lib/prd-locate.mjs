/**
 * lib/prd-locate.mjs — dónde está el PRD de una UC (UC-12211, UC-12219).
 *
 * Mismo orden que `find_prd_path` de server/prd_writer.py (una prueba lo compara):
 *   1. doc/prds/{feature}_prd.md o doc/prds/{feature}.md
 *   2. doc/prds/{us normalizada}_prd.md (US-01 → us_01)
 *   3. doc/prd/{feature}.md o la carpeta de la feature: doc/prd/{feature}/prd.md, PRD.md o
 *      {feature}_prd.md
 *   4. el único PRD que define la historia (un encabezado o una línea «>» la nombra), o si no, el
 *      único que la nombra (prdCandidates)
 *   5. el único fichero de doc/prds/
 * Devuelve la ruta relativa a `root` con el nombre que tiene en disco (un disco que no distingue
 * mayúsculas también «encuentra» PRD.md al pedir prd.md, y el hook la compara con los ficheros
 * de la PR), o null.
 */

import { readdirSync, readFileSync, statSync } from 'node:fs';
import { basename, dirname, join } from 'node:path';

const isFile = (path) => {
  try {
    return statSync(path).isFile();
  } catch {
    return false;
  }
};
/** Las entradas de `dir` tal como están en disco, ordenadas; [] si no existe. */
const names = (dir) => {
  try {
    return readdirSync(dir).sort();
  } catch {
    return [];
  }
};
/** `rel` si existe un fichero con ese nombre exacto (mayúsculas incluidas). */
const exact = (root, rel) => {
  const full = join(root, rel);
  return names(dirname(full)).includes(basename(full)) && isFile(full) ? rel : null;
};

/** Todos los PRD del proyecto, en orden estable (rutas relativas, nombres como en disco). */
export function prdCandidates(root) {
  const out = [];
  const prdDir = join(root, 'doc', 'prd');
  for (const folder of names(prdDir)) {
    const inside = names(join(prdDir, folder));
    for (const name of ['prd.md', 'PRD.md', `${folder}_prd.md`]) {
      if (inside.includes(name) && isFile(join(prdDir, folder, name))) out.push(`doc/prd/${folder}/${name}`);
    }
  }
  for (const [dir, rel] of [[prdDir, 'doc/prd'], [join(root, 'doc', 'prds'), 'doc/prds']]) {
    for (const name of names(dir)) {
      if (name.endsWith('.md') && isFile(join(dir, name))) out.push(`${rel}/${name}`);
    }
  }
  return out;
}

export function locatePrd({ root, feature = '', usId = '' } = {}) {
  const first = (rels) => rels.map((rel) => exact(root, rel)).find(Boolean) ?? null;
  if (feature) {
    const found = first([`doc/prds/${feature}_prd.md`, `doc/prds/${feature}.md`]);
    if (found) return found;
  }
  if (usId) {
    const found = exact(root, `doc/prds/${usId.toLowerCase().replace(/-/g, '_')}_prd.md`);
    if (found) return found;
  }
  if (feature) {
    const found = first([
      `doc/prd/${feature}.md`,
      `doc/prd/${feature}/prd.md`,
      `doc/prd/${feature}/PRD.md`,
      `doc/prd/${feature}/${feature}_prd.md`,
    ]);
    if (found) return found;
  }
  if (usId) {
    const word = new RegExp(`\\b${usId.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`);
    const texts = prdCandidates(root).map((rel) => {
      try {
        return [rel, readFileSync(join(root, rel), 'utf-8')];
      } catch {
        return [rel, ''];
      }
    });
    // El que define la historia (un encabezado o una línea «>» la nombra) gana al que solo la cita.
    const defining = texts.filter(([, text]) => text.split('\n').some((line) => /^\s*[#>]/.test(line) && word.test(line)));
    if (defining.length === 1) return defining[0][0];
    const named = texts.filter(([, text]) => word.test(text));
    if (named.length === 1) return named[0][0];
  }
  const prds = names(join(root, 'doc', 'prds')).filter((n) => n.endsWith('.md') && isFile(join(root, 'doc', 'prds', n)));
  if (prds.length === 1) return `doc/prds/${prds[0]}`;
  return null;
}
