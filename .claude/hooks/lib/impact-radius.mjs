/**
 * lib/impact-radius.mjs — el radio de impacto de un commit (US-126 · UC-12606).
 *
 * Clasifica los ficheros de un commit por lo que tocan:
 *   - api_contract    contrato de API: openapi, .proto, schema.graphql, los globs del proyecto
 *                     (`impact.api_globs`) y, en los ficheros de `impact.signature_globs`, un cambio en
 *                     la firma de una función pública (sus parámetros), no en su cuerpo;
 *   - data_migration  migración de datos: carpetas `migrations/`, `.sql`, prisma y `impact.migration_globs`;
 *   - dependencies    manifiestos y lockfiles;
 *   - internal        el resto.
 * La clase del commit es la mayor que toca (contrato o migración > dependencias > interno), y cada
 * clase dice qué ficheros la decidieron. Puro: los contenidos los pasa quien llama.
 */

export const CLASSES = ['api_contract', 'data_migration', 'dependencies', 'internal'];
export const APPROVAL_CLASSES = new Set(['api_contract', 'data_migration']);
export const LABELS = {
  api_contract: 'contrato de API',
  data_migration: 'migración de datos',
  dependencies: 'dependencias',
  internal: 'código interno',
};

const DEFAULT_API = ['**/openapi*.yaml', '**/openapi*.yml', '**/openapi*.json', '**/*.proto', '**/schema.graphql'];
const DEFAULT_MIGRATION = ['**/migrations/**', '**/*.sql', 'supabase/migrations/**', 'prisma/schema.prisma'];
const DEPENDENCY_FILES = new Set([
  'package.json', 'package-lock.json', 'pnpm-lock.yaml', 'yarn.lock', 'pyproject.toml', 'uv.lock', 'poetry.lock',
  'pubspec.yaml', 'pubspec.lock', 'go.mod', 'go.sum', 'Cargo.toml', 'Cargo.lock', 'Gemfile', 'Gemfile.lock',
]);

function globTokens(pat) {
  const tokens = [];
  for (let i = 0; i < pat.length; ) {
    if (pat.startsWith('**', i)) {
      let j = i;
      while (pat[j] === '*') j += 1;
      if (pat[j] === '/') { if (tokens.at(-1) !== '**/') tokens.push('**/'); i = j + 1; }
      else { if (tokens.at(-1) !== '**') tokens.push('**'); i = j; }
    } else if (pat[i] === '*') { if (tokens.at(-1) !== '*' && tokens.at(-1) !== '**') tokens.push('*'); i += 1; }
    else { tokens.push(pat[i]); i += 1; }
  }
  return tokens;
}

/** ¿`s` entero casa con los tokens? Programación dinámica, sin vuelta atrás: tiempo tokens × largo. */
function globMatch(tokens, s) {
  const n = s.length;
  let next = new Array(n + 1).fill(false);
  next[n] = true;
  for (let t = tokens.length - 1; t >= 0; t -= 1) {
    const tok = tokens[t];
    const cur = new Array(n + 1).fill(false);
    if (tok === '**/') {
      let reach = false;
      for (let j = n - 1; j >= 0; j -= 1) { reach = (s[j] === '/' && next[j + 1]) || reach; cur[j] = next[j] || reach; }
      cur[n] = next[n];
    } else if (tok === '**') {
      cur[n] = next[n];
      for (let j = n - 1; j >= 0; j -= 1) cur[j] = next[j] || cur[j + 1];
    } else if (tok === '*') {
      cur[n] = next[n];
      for (let j = n - 1; j >= 0; j -= 1) cur[j] = next[j] || (s[j] !== '/' && cur[j + 1]);
    } else if (tok === '?') {
      for (let j = 0; j < n; j += 1) cur[j] = s[j] !== '/' && next[j + 1];
    } else {
      for (let j = 0; j < n; j += 1) cur[j] = s[j] === tok && next[j + 1];
    }
    next = cur;
  }
  return next[0];
}

/**
 * Un glob del proyecto, como en .gitignore → función. `**` cruza carpetas y `*` y `?` no; un patrón
 * sin «/» vale en cualquier carpeta, uno que empieza por «/» solo en la raíz, y un nombre cubre
 * también lo que hay dentro (`docs` es la carpeta). Mismas reglas que server/drift.py.
 */
export function globMatcher(pattern) {
  let pat = String(pattern || '').trim().replace(/\\/g, '/');
  const anchored = pat.startsWith('/');
  pat = pat.replace(/^\/+/, '');
  while (pat.startsWith('./')) pat = pat.slice(2);
  if (!pat) return () => false;
  if (pat.endsWith('/')) pat += '**';
  if (!anchored && !pat.replace(/\/$/, '').includes('/')) pat = `**/${pat}`;
  const variants = [globTokens(pat)];
  if (!pat.endsWith('**')) variants.push(globTokens(`${pat}/**`));
  return (path) => {
    const s = String(path);
    return variants.some((tokens) => globMatch(tokens, s));
  };
}

/** Las firmas de las funciones públicas de un fichero Python: {nombre: "parámetros -> retorno"}. */
export function pythonSignatures(source) {
  const out = {};
  const re = /^(?:async\s+)?def\s+([A-Za-z]\w*)\s*\(([\s\S]*?)\)\s*(->[^:\n]*)?:/gm;
  for (const m of String(source || '').matchAll(re)) {
    out[m[1]] = `${m[2].replace(/\s+/g, ' ').trim()}${m[3] ? ` ${m[3].replace(/\s+/g, ' ').trim()}` : ''}`;
  }
  return out;
}

/** Las funciones públicas cuya firma cambia (añadidas, quitadas o con otros parámetros). */
export function changedSignatures(before, after) {
  const a = pythonSignatures(before);
  const b = pythonSignatures(after);
  return [...new Set([...Object.keys(a), ...Object.keys(b)])].filter((name) => a[name] !== b[name]).sort();
}

/**
 * Clasifica un commit. `files`: sus rutas. `config`: {api_globs, migration_globs, signature_globs} del
 * proyecto. `versions(path)` → {before, after} (el texto en HEAD y en el commit) para los ficheros de
 * firmas; puede devolver null. Devuelve {class, label, needs_approval, classes: {clase: [{path, why}]}}.
 */
export function classifyCommit(files, config = {}, versions = () => null) {
  const list = (v) => (Array.isArray(v) ? v.filter((x) => typeof x === 'string' && x.trim()) : []);
  const api = [...DEFAULT_API, ...list(config.api_globs)].map(globMatcher);
  const migration = [...DEFAULT_MIGRATION, ...list(config.migration_globs)].map(globMatcher);
  const signatures = list(config.signature_globs).map(globMatcher);
  const classes = Object.fromEntries(CLASSES.map((c) => [c, []]));
  for (const raw of files) {
    const path = String(raw).replace(/\\/g, '/').replace(/^\.\//, '');
    if (!path) continue;
    const base = path.split('/').at(-1);
    if (api.some((m) => m(path))) classes.api_contract.push({ path, why: 'fichero de contrato' });
    else if (migration.some((m) => m(path))) classes.data_migration.push({ path, why: 'migración' });
    else if (DEPENDENCY_FILES.has(base) || /^requirements.*\.txt$/.test(base)) classes.dependencies.push({ path, why: 'manifiesto o lockfile' });
    else if (signatures.some((m) => m(path))) {
      const v = versions(path);
      const changed = v ? changedSignatures(v.before, v.after) : [];
      if (changed.length) classes.api_contract.push({ path, why: `firma de ${changed.slice(0, 5).join(', ')}` });
      else classes.internal.push({ path, why: 'sin cambios de firma' });
    } else classes.internal.push({ path, why: 'código interno' });
  }
  const top = CLASSES.find((c) => classes[c].length) ?? 'internal';
  return { class: top, label: LABELS[top], needs_approval: APPROVAL_CLASSES.has(top), classes };
}

/** La línea que va en el mensaje del hook: la clase y los ficheros que la decidieron. */
export function describe(result) {
  const deciding = result.classes[result.class] ?? [];
  const shown = deciding.slice(0, 5).map((f) => `${f.path} (${f.why})`).join(', ');
  const more = deciding.length > 5 ? ` y ${deciding.length - 5} más` : '';
  return `Radio de impacto: ${result.label}${shown ? ` — ${shown}${more}` : ''}.`;
}
