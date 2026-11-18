/**
 * lib/prd-locate.mjs — dónde está el PRD de una UC (UC-12211).
 *
 * Mismo orden que `find_prd_path` de server/prd_writer.py (una prueba lo compara):
 *   1. doc/prds/{feature}_prd.md o doc/prds/{feature}.md
 *   2. doc/prds/{us normalizada}_prd.md (US-01 → us_01)
 *   3. doc/prd/{feature}.md o doc/prd/{feature}/prd.md
 *   4. el único PRD que nombra la historia (doc/prd/*\/prd.md, doc/prd/*.md, doc/prds/*.md)
 *   5. el único fichero de doc/prds/
 * Devuelve la ruta relativa a `root`, o null.
 */

import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

const isFile = (path) => {
  try {
    return statSync(path).isFile();
  } catch {
    return false;
  }
};
const list = (dir) => {
  try {
    return readdirSync(dir).sort();
  } catch {
    return [];
  }
};

/** Todos los PRD del proyecto, en orden estable (rutas relativas). */
export function prdCandidates(root) {
  const out = [];
  for (const name of list(join(root, 'doc', 'prd'))) {
    if (isFile(join(root, 'doc', 'prd', name, 'prd.md'))) out.push(`doc/prd/${name}/prd.md`);
  }
  for (const name of list(join(root, 'doc', 'prd'))) {
    if (name.endsWith('.md') && isFile(join(root, 'doc', 'prd', name))) out.push(`doc/prd/${name}`);
  }
  for (const name of list(join(root, 'doc', 'prds'))) {
    if (name.endsWith('.md') && isFile(join(root, 'doc', 'prds', name))) out.push(`doc/prds/${name}`);
  }
  return out;
}

export function locatePrd({ root, feature = '', usId = '' } = {}) {
  const has = (rel) => existsSync(join(root, rel)) && isFile(join(root, rel));
  if (feature) {
    for (const rel of [`doc/prds/${feature}_prd.md`, `doc/prds/${feature}.md`]) if (has(rel)) return rel;
  }
  if (usId) {
    const rel = `doc/prds/${usId.toLowerCase().replace(/-/g, '_')}_prd.md`;
    if (has(rel)) return rel;
  }
  if (feature) {
    for (const rel of [`doc/prd/${feature}.md`, `doc/prd/${feature}/prd.md`]) if (has(rel)) return rel;
  }
  if (usId) {
    const word = new RegExp(`\\b${usId.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`);
    const named = prdCandidates(root).filter((rel) => {
      try {
        return word.test(readFileSync(join(root, rel), 'utf-8'));
      } catch {
        return false;
      }
    });
    if (named.length === 1) return named[0];
  }
  const prds = list(join(root, 'doc', 'prds')).filter((n) => n.endsWith('.md'));
  if (prds.length === 1) return `doc/prds/${prds[0]}`;
  return null;
}
