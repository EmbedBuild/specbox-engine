#!/usr/bin/env node
/**
 * scope.mjs — ¿sigue siendo pequeño el arreglo? (US-127 · UC-12701 AC-04)
 *
 * /fix lo ejecuta antes del commit del arreglo. Junta los ficheros que el arreglo cambia frente a la
 * rama base (lo ya commiteado y lo pendiente de los ficheros con seguimiento, también lo añadido con
 * `git add`), los cuenta sin sus pruebas, `.quality/` ni `doc/tracking/`, y clasifica todos menos
 * `.quality/` y `doc/tracking/` con la misma regla que el hook del radio de impacto
 * (`.claude/hooks/lib/impact-radius.mjs`, con los `impact` de la rama base): una prueba no cuenta
 * para el límite, pero un `spec/openapi.yaml` sigue siendo un contrato. Los ficheros nuevos sin
 * añadir no cuentan (pueden ser notas ajenas al arreglo): salen en `untracked`. Un renombrado cuenta
 * como dos ficheros. El arreglo deja de ser de /fix con más de 5 ficheros, un contrato de API o una
 * migración de datos.
 *
 * Uso: node scope.mjs [--base <ref>] [--limit 5]
 * Escribe un JSON: {base, count, limit, files, excluded, untracked, class, classes, stop, reasons}.
 * Sale con 0 aunque `stop` sea true (lo decide la skill); con 2 si no está en un repositorio git.
 */

import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync, realpathSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

export const DEFAULT_LIMIT = 5;
/** Pruebas del arreglo: carpetas y nombres de prueba de los stacks del engine. */
const TEST_PATH = /(^|\/)(tests?|__tests__|spec|e2e|integration_test)\/|\.(test|spec)\.[cm]?[jt]sx?$|(^|\/)test_[^/]*\.py$|_test\.(py|go|dart)$/;
/** `doc/spec/` es el documento de comportamiento (UC-12605), no una carpeta de pruebas. */
const NOT_A_TEST = /(^|\/)doc\/spec\//;
const NEVER_COUNTED = [/^\.quality\//, /^doc\/tracking\//];
export const ENGINE_RECORD = 'registro del engine';

/** ¿Este fichero no cuenta para el límite? Devuelve el motivo, o null si cuenta. */
export function excludedBecause(path) {
  if (NEVER_COUNTED.some((re) => re.test(path))) return ENGINE_RECORD;
  if (TEST_PATH.test(path) && !NOT_A_TEST.test(path)) return 'prueba del arreglo';
  return null;
}

/** Lo que se clasifica con la regla del radio de impacto: todo menos el registro del engine. */
export const classifiable = (files) => [...new Set(files)].filter((path) => excludedBecause(path) !== ENGINE_RECORD);

/** La decisión: pura, para las pruebas. `classified` es lo que devuelve classifyCommit sobre `classifiable(files)`. */
export function decide(files, classified, limit = DEFAULT_LIMIT) {
  const counted = [];
  const excluded = [];
  for (const path of [...new Set(files)].sort()) {
    const why = excludedBecause(path);
    if (why) excluded.push({ path, why });
    else counted.push(path);
  }
  const reasons = [];
  if (counted.length > limit) reasons.push(`toca ${counted.length} ficheros (el límite de /fix es ${limit}, sin contar sus pruebas)`);
  const contract = classified?.classes?.api_contract ?? [];
  const migration = classified?.classes?.data_migration ?? [];
  if (contract.length) reasons.push(`toca un contrato de API: ${contract.map((f) => `${f.path} (${f.why})`).join(', ')}`);
  if (migration.length) reasons.push(`toca una migración de datos: ${migration.map((f) => f.path).join(', ')}`);
  return {
    count: counted.length,
    limit,
    files: counted,
    excluded,
    class: classified?.class ?? 'internal',
    classes: Object.fromEntries(Object.entries(classified?.classes ?? {}).map(([c, list]) => [c, list.map((f) => f.path)])),
    stop: reasons.length > 0,
    reasons,
  };
}

const git = (cwd, args, raw = false) => {
  try {
    const out = execFileSync('git', ['-c', 'core.quotePath=false', ...args], {
      cwd, encoding: 'utf-8', stdio: ['ignore', 'pipe', 'ignore'], maxBuffer: 64 * 1024 * 1024,
    });
    return raw ? out : out.trim();
  } catch {
    return '';
  }
};
const list0 = (text) => String(text || '').split('\0').filter(Boolean);

/** La rama base: la que se pide, la del remoto por defecto, o main/master. */
function baseRef(cwd, asked) {
  if (asked) return asked;
  const remoteHead = git(cwd, ['rev-parse', '--abbrev-ref', 'origin/HEAD']);
  for (const ref of [...(remoteHead && remoteHead !== 'origin/HEAD' ? [remoteHead] : []), 'origin/main', 'origin/master', 'main', 'master']) {
    if (git(cwd, ['rev-parse', '--verify', '-q', ref])) return ref;
  }
  return null;
}

/** Los `impact` de la rama base, como el hook: una rama no afloja su propia regla. */
function impactConfig(cwd, base) {
  const text = git(cwd, ['show', `${base}:.claude/settings.json`]);
  try {
    const json = JSON.parse(text);
    const impact = json?.specbox?.impact ?? json?.impact;
    return impact && typeof impact === 'object' ? impact : {};
  } catch {
    return {};
  }
}

/** El clasificador del proyecto o, si no lo tiene, el del engine que trae esta skill. */
async function loadClassifier(root) {
  const own = join(root, '.claude', 'hooks', 'lib', 'impact-radius.mjs');
  const here = dirname(realpathSync(fileURLToPath(import.meta.url)));
  const engine = resolve(here, '..', '..', '..', 'hooks', 'lib', 'impact-radius.mjs');
  const managed = join(process.env.HOME || '', '.specbox', 'specbox-engine', '.claude', 'hooks', 'lib', 'impact-radius.mjs');
  for (const candidate of [own, engine, managed]) {
    if (existsSync(candidate)) return (await import(pathToFileURL(candidate).href)).classifyCommit;
  }
  return null;
}

async function main(argv) {
  const arg = (name) => {
    const i = argv.indexOf(name);
    return i >= 0 ? argv[i + 1] : undefined;
  };
  const root = git(process.cwd(), ['rev-parse', '--show-toplevel']);
  if (!root) {
    process.stdout.write(`${JSON.stringify({ error: 'not_a_git_repo', stop: true, reasons: ['no estás en un repositorio git'] })}\n`);
    return 2;
  }
  const foundBase = baseRef(root, arg('--base'));
  const base = foundBase || 'HEAD';
  const limit = Number(arg('--limit')) > 0 ? Number(arg('--limit')) : DEFAULT_LIMIT;
  const files = [
    ...(foundBase ? list0(git(root, ['diff', '--name-only', '-z', '--no-renames', `${base}...HEAD`], true)) : []),
    ...list0(git(root, ['diff', '--name-only', '-z', '--no-renames', 'HEAD'], true)),
  ];
  const untracked = list0(git(root, ['ls-files', '--others', '--exclude-standard', '-z'], true)).sort();
  const classify = await loadClassifier(root);
  const versions = (path) => ({
    before: git(root, ['show', `${base}:${path}`], true),
    after: existsSync(join(root, path)) ? readFileSync(join(root, path), 'utf-8') : '',
  });
  const classified = classify ? classify(classifiable(files), impactConfig(root, base), versions) : null;
  const result = { base, ...decide(files, classified, limit), untracked };
  const notices = [];
  if (!foundBase) {
    notices.push('Sin rama base (no hay origin/HEAD, main ni master): solo cuenta lo pendiente, no lo ya '
      + 'commiteado. Mide otra vez con --base <rama principal>.');
  }
  if (!classify) notices.push('Sin el clasificador del radio de impacto: solo se cuentan los ficheros.');
  if (untracked.length) {
    notices.push(`${untracked.length} ficheros nuevos sin añadir no cuentan: si alguno es del arreglo, `
      + 'añádelo con git add y mide otra vez.');
  }
  if (notices.length) result.notice = notices.join(' ');
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
  return 0;
}

if (process.argv[1] && realpathSync(process.argv[1]) === realpathSync(fileURLToPath(import.meta.url))) {
  main(process.argv.slice(2)).then((code) => process.exit(code));
}
