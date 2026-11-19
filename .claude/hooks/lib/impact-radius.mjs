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

export const DEFAULT_API = [
  '**/openapi*.yaml', '**/openapi*.yml', '**/openapi*.json',
  '**/swagger*.yaml', '**/swagger*.yml', '**/swagger*.json',
  '**/*.proto', '**/schema*.graphql', '**/*.graphqls',
];
export const DEFAULT_MIGRATION = [
  '**/migrations/**', '**/alembic/versions/**', '**/db/migrate/**', '**/*.sql', '**/schema.prisma',
];
/** Lo que nunca es una migración: la documentación, las semillas y los datos de prueba. */
const DOC_FILE = /\.(md|markdown|txt|rst)$/i;
const SEED_OR_FIXTURE = /(^|\/)(seeds?|fixtures?|tests?|__tests__|spec)\/|(^|\/)seed[^/]*$/i;
export const notMigration = (path) => DOC_FILE.test(path) || SEED_OR_FIXTURE.test(path);
/** Funciones públicas que no son contrato por convención: los registros de tools y los `*_impl`. */
export const DEFAULT_SIGNATURE_IGNORE = ['register_*', '*_impl'];
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

/** El código Python sin docstrings, cadenas ni comentarios (para que un `def` en un texto no cuente). */
function stripPython(source) {
  let out = '';
  const src = String(source || '');
  for (let i = 0; i < src.length; ) {
    const ch = src[i];
    if (ch === '#') {
      while (i < src.length && src[i] !== '\n') i += 1;
      continue;
    }
    if (ch === '"' || ch === "'") {
      const triple = src.startsWith(ch.repeat(3), i);
      const quote = triple ? ch.repeat(3) : ch;
      let j = i + quote.length;
      while (j < src.length && !src.startsWith(quote, j)) {
        if (src[j] === '\\') j += 1;
        else if (!triple && src[j] === '\n') break;
        j += 1;
      }
      // Una cadena se queda como «""» (sus saltos de línea, para no mover las líneas).
      const body = src.slice(i, Math.min(j + quote.length, src.length));
      out += `${quote}${'\n'.repeat((body.match(/\n/g) || []).length)}${quote}`;
      i = j + quote.length;
      continue;
    }
    out += ch;
    i += 1;
  }
  return out;
}

const nameIgnored = (name, ignore) =>
  ignore.some((pat) => {
    const p = String(pat);
    if (p.startsWith('*') && p.endsWith('*') && p.length > 1) return name.includes(p.slice(1, -1));
    if (p.endsWith('*')) return name.startsWith(p.slice(0, -1));
    if (p.startsWith('*')) return name.endsWith(p.slice(1));
    return name === p;
  });

/**
 * Las firmas de las funciones públicas de un fichero Python: {nombre: "parámetros -> retorno"}.
 * Cuentan las de nivel de módulo, los métodos de una clase y las tools anidadas en `register_*()`;
 * un auxiliar definido dentro de otra función no es contrato. Cada una se identifica por su nombre y
 * el de quien la contiene («Clase.metodo», «register_x.tool»), nunca por su orden. Paréntesis
 * contados de verdad (un valor por defecto «"):"» no corta la firma), sin docstrings ni comentarios
 * y sin la coma final: reformatear no es cambiar el contrato.
 */
export function pythonSignatures(source, ignore = DEFAULT_SIGNATURE_IGNORE) {
  const code = stripPython(source);
  const out = {};
  const stack = [];
  const head = /^([ \t]*)(?:(?:async[ \t]+)?(def)|(class))[ \t]+([A-Za-z_]\w*)/gm;
  for (const m of code.matchAll(head)) {
    const indent = m[1].replace(/\t/g, '    ').length;
    const kind = m[2] ? 'def' : 'class';
    const name = m[4];
    while (stack.length && stack.at(-1).indent >= indent) stack.pop();
    const parent = stack.at(-1);
    stack.push({ indent, kind, name });
    if (kind !== 'def' || name.startsWith('_') || nameIgnored(name, ignore)) continue;
    if (parent && !(parent.kind === 'class' || /^register_/.test(parent.name))) continue;
    let j = code.indexOf('(', m.index + m[0].length);
    if (j < 0) continue;
    let depth = 1;
    const startParams = j + 1;
    for (j += 1; j < code.length && depth > 0; j += 1) {
      if ('([{'.includes(code[j])) depth += 1;
      else if (')]}'.includes(code[j])) depth -= 1;
    }
    const params = code.slice(startParams, j - 1).replace(/\s+/g, ' ').replace(/,\s*$/, '').trim();
    const colon = code.indexOf(':', j);
    const ret = /->\s*(.+)$/s.exec(code.slice(j, colon >= 0 ? colon : j))?.[1]?.replace(/\s+/g, ' ').trim();
    let key = parent ? `${parent.name}.${name}` : name;
    for (let n = 2; key in out; n += 1) key = `${parent ? `${parent.name}.` : ''}${name}#${n}`;
    out[key] = `${params}${ret ? ` -> ${ret}` : ''}`;
  }
  return out;
}

/** Las funciones públicas cuya firma cambia (añadidas, quitadas o con otros parámetros). */
export function changedSignatures(before, after, ignore = DEFAULT_SIGNATURE_IGNORE) {
  const a = pythonSignatures(before, ignore);
  const b = pythonSignatures(after, ignore);
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
  const ignore = [...DEFAULT_SIGNATURE_IGNORE, ...list(config.signature_ignore)];
  const classes = Object.fromEntries(CLASSES.map((c) => [c, []]));
  for (const raw of files) {
    const path = String(raw).replace(/\\/g, '/').replace(/^\.\//, '');
    if (!path) continue;
    const base = path.split('/').at(-1);
    if (api.some((m) => m(path))) classes.api_contract.push({ path, why: 'fichero de contrato' });
    else if (!notMigration(path) && migration.some((m) => m(path))) classes.data_migration.push({ path, why: 'migración' });
    else if (DEPENDENCY_FILES.has(base) || /^requirements.*\.txt$/.test(base)) classes.dependencies.push({ path, why: 'manifiesto o lockfile' });
    else if (signatures.some((m) => m(path))) {
      const v = versions(path);
      const changed = v ? changedSignatures(v.before, v.after, ignore) : [];
      if (changed.length) classes.api_contract.push({ path, why: `firma de ${changed.slice(0, 5).join(', ')}` });
      else classes.internal.push({ path, why: 'sin cambios de firma' });
    } else classes.internal.push({ path, why: 'código interno' });
  }
  const top = CLASSES.find((c) => classes[c].length) ?? 'internal';
  // Todas las clases que piden aprobación, con sus ficheros: la persona tiene que ver todo lo que aprueba.
  const deciding = [...APPROVAL_CLASSES].flatMap((c) => classes[c]);
  return { class: top, label: LABELS[top], needs_approval: APPROVAL_CLASSES.has(top), classes, deciding };
}

/** La línea que va en el mensaje del hook: cada clase que pide aprobación (o la clase) y sus ficheros. */
export function describe(result) {
  const show = (files) => {
    const listed = files.slice(0, 8).map((f) => `${f.path} (${f.why})`).join(', ');
    return files.length > 8 ? `${listed} y ${files.length - 8} más` : listed;
  };
  const approval = [...APPROVAL_CLASSES].filter((c) => result.classes[c]?.length);
  if (approval.length) {
    return `Radio de impacto: ${approval.map((c) => `${LABELS[c]} — ${show(result.classes[c])}`).join('; ')}.`;
  }
  const files = result.classes[result.class] ?? [];
  return `Radio de impacto: ${result.label}${files.length ? ` — ${show(files)}` : ''}.`;
}
