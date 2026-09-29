#!/usr/bin/env node
/**
 * changelog-security-check.mjs (v6.14.1 — US-43/UC-4302 AC-01)
 *
 * Una versión que incluye cambios de seguridad tiene que contarlo en su entrada
 * del CHANGELOG.md con una sección `### Security` que diga qué evita esa versión
 * a partir de ese momento, sin detalles explotables ni mención a su origen: sin
 * severidades, sin reportes y sin incidentes.
 *
 * Qué comprueba:
 *   1. Toma la entrada superior del CHANGELOG.md (`## [X.Y.Z] - ...`).
 *   2. Lista los commits de esa versión: desde la etiqueta de la entrada
 *      anterior (`v<anterior>`) hasta HEAD, o desde `--since <ref>`.
 *   3. Un commit es de seguridad si su mensaje habla de seguridad
 *      (SECURITY_KEYWORDS, en español o inglés) o toca la superficie sensible
 *      (SECURITY_PATHS). Los trailers (Co-Authored-By, Refs…) no cuentan.
 *   4. Con al menos un commit de seguridad, la entrada debe tener `### Security`
 *      (también vale `### Seguridad`) con contenido.
 *   5. Esa sección no puede nombrar severidades, incidentes, reportes, testers ni
 *      identificadores de vulnerabilidad (FORBIDDEN_TERMS).
 *
 * Uso:
 *   node .quality/scripts/changelog-security-check.mjs [--changelog <ruta>]
 *        [--since <ref>] [--commits-json <ruta>] [--json]
 *
 * `--commits-json` sustituye a git (pruebas): un array de {subject, body, files}.
 * Con `--json`, stdout lleva el resultado en JSON; el informe legible va a stderr.
 *
 * Salida: 0 conforme · 1 falta la sección, está vacía o dice lo que no debe ·
 * 2 error de uso o de git. Sin dependencias.
 */

import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

// Palabras que delatan un cambio de seguridad en el mensaje de un commit (ES/EN).
export const SECURITY_KEYWORDS = new RegExp(
  '\\b(' +
    [
      'security', 'seguridad', 'vulnerab\\w*', 'CVE-\\d+', 'GHSA-[\\w-]+',
      'tokens?', 'credencial\\w*', 'credentials?', 'secrets?', 'secretos?',
      'authenticat\\w*', 'authoriz\\w*', 'autentic\\w*', 'autoriz\\w*',
      'permis\\w*', 'privileg\\w*', 'RLS', 'inyecci[oó]n', 'injection', 'XSS', 'CSRF',
      'rate[ -]?limit\\w*', 'caduc\\w*', 'expir\\w*', 'revoc\\w*',
      'cifra\\w*', 'encrypt\\w*', 'degrad\\w*', 'downgrade\\w*',
      'divulgaci[oó]n', 'disclosure',
    ].join('|') +
    ')\\b',
  'i',
);

// Ficheros cuya modificación es, por sí sola, un cambio de seguridad.
export const SECURITY_PATHS = [
  'SECURITY.md',
  'Dockerfile',
  'docker-entrypoint.sh',
  'server/coordination/transport_auth.py',
  'server/coordination/abuse_guard.py',
  'server/coordination/identity.py',
  'server/coordination/scope.py',
  'server/coordination/access_log.py',
  'server/db/surface_check.py',
  'server/db/surface_allowlist.yaml',
  'vscode-extension/src/auth.ts',
  'vscode-extension/src/oauth.ts',
  'vscode-extension/src/secret-storage.ts',
  'packages/specbox-cli/lib/store.mjs',
  'packages/specbox-cli/lib/mcp-headers.mjs',
];

// Lo que la sección Security no puede decir (decisión del 2026-09-29): ni severidades,
// ni incidentes, ni reportes ni quién los hizo, ni identificadores de vulnerabilidad.
export const FORBIDDEN_TERMS =
  /\b(severidad|severity|cr[ií]tic[oa]s?|critical|brecha|breach|incidentes?|incidents?|testers?|report(e|es|ado|ada|ed)|CVE-\d+|GHSA-[\w-]+|exploit\w*|explot\w*)\b/i;

// Trailers de git ("Co-Authored-By: …", "Refs: …"): no describen el cambio.
const TRAILER = /^[A-Za-z][A-Za-z-]*:\s/;

const VERSION_HEADER = /^##\s+\[(\d+\.\d+\.\d+)\]/;
const SECTION_HEADER = /^###\s+(.+?)\s*$/;

/** Entrada superior del changelog: versión, versión anterior y cuerpo. */
export function topEntry(changelog) {
  const lines = changelog.split('\n');
  let start = -1;
  let version = null;
  for (let i = 0; i < lines.length; i++) {
    const match = lines[i].match(VERSION_HEADER);
    if (!match) continue;
    if (start === -1) {
      start = i;
      version = match[1];
      continue;
    }
    return { version, previous: match[1], body: lines.slice(start + 1, i).join('\n') };
  }
  if (start === -1) return null;
  return { version, previous: null, body: lines.slice(start + 1).join('\n') };
}

/** Sección Security de una entrada: {present, text}. */
export function securitySection(body) {
  let present = false;
  let inside = false;
  const collected = [];
  for (const line of body.split('\n')) {
    const header = line.match(SECTION_HEADER);
    if (header) {
      inside = /^(security|seguridad)$/i.test(header[1].trim());
      if (inside) present = true;
      continue;
    }
    if (inside) collected.push(line);
  }
  return { present, text: collected.join('\n').trim() };
}

/** Motivos por los que un commit cuenta como cambio de seguridad ([] si ninguno). */
export function classifyCommit(commit) {
  const reasons = [];
  const bodyLines = String(commit.body || '')
    .split('\n')
    .filter((line) => !TRAILER.test(line));
  const message = [String(commit.subject || ''), ...bodyLines].join('\n');
  const keyword = message.match(SECURITY_KEYWORDS);
  if (keyword) reasons.push(`mensaje: «${keyword[0]}»`);
  for (const file of commit.files || []) {
    if (SECURITY_PATHS.includes(file)) reasons.push(`fichero: ${file}`);
  }
  return reasons;
}

/** Veredicto puro: {ok, code, version, previous, security_commits, section_present, problems}. */
export function evaluate({ changelog, commits }) {
  const entry = topEntry(changelog);
  if (!entry) {
    return { ok: false, code: 2, problems: ['CHANGELOG.md no tiene ninguna entrada "## [X.Y.Z]"'] };
  }
  const securityCommits = commits
    .map((commit) => ({ ...commit, reasons: classifyCommit(commit) }))
    .filter((commit) => commit.reasons.length > 0);
  const section = securitySection(entry.body);
  const problems = [];

  if (securityCommits.length > 0 && !section.present) {
    problems.push(
      `la versión ${entry.version} incluye ${securityCommits.length} cambio(s) de seguridad ` +
        'y su entrada del CHANGELOG.md no tiene una sección "### Security"',
    );
  }
  if (section.present && !section.text) {
    problems.push('la sección "### Security" está vacía: tiene que contar qué evita esta versión');
  }
  if (section.present) {
    for (const line of section.text.split('\n')) {
      const bad = line.match(FORBIDDEN_TERMS);
      if (bad) {
        problems.push(
          `la sección Security menciona «${bad[0]}» (sin severidades, incidentes, reportes ni ` +
            `identificadores): ${line.trim()}`,
        );
      }
    }
  }

  return {
    ok: problems.length === 0,
    code: problems.length === 0 ? 0 : 1,
    version: entry.version,
    previous: entry.previous,
    security_commits: securityCommits.map((commit) => ({
      hash: commit.hash || '',
      subject: commit.subject,
      reasons: commit.reasons,
    })),
    section_present: section.present,
    problems,
  };
}

/** Commits de un rango, con sus ficheros, leídos de git. */
export function commitsFromGit(range, cwd) {
  const raw = execFileSync(
    'git',
    ['log', '--format=%x1e%H%x1f%s%x1f%b%x1f', '--name-only', range],
    { cwd, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 },
  );
  return raw
    .split('\x1e')
    .filter((record) => record.trim())
    .map((record) => {
      const [hash = '', subject = '', body = '', rest = ''] = record.split('\x1f');
      const files = rest.split('\n').map((line) => line.trim()).filter(Boolean);
      return { hash: hash.trim(), subject: subject.trim(), body, files };
    });
}

function parseArgs(argv) {
  const args = { json: false };
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--json') args.json = true;
    else if (arg === '--changelog' || arg === '--since' || arg === '--commits-json') {
      args[arg.slice(2)] = argv[++i];
    } else {
      throw new Error(`argumento desconocido: ${arg}`);
    }
  }
  return args;
}

function refExists(ref, cwd) {
  try {
    execFileSync('git', ['rev-parse', '-q', '--verify', `${ref}^{commit}`], { cwd, stdio: 'ignore' });
    return true;
  } catch {
    return false;
  }
}

export function main(argv, cwd = process.cwd()) {
  let args;
  try {
    args = parseArgs(argv);
  } catch (err) {
    console.error(`[changelog-security-check] ${err.message}`);
    return 2;
  }

  const changelogPath = resolve(cwd, args.changelog || 'CHANGELOG.md');
  if (!existsSync(changelogPath)) {
    console.error(`[changelog-security-check] no existe ${changelogPath}`);
    return 2;
  }
  const changelog = readFileSync(changelogPath, 'utf8');
  const entry = topEntry(changelog);
  if (!entry) {
    console.error('[changelog-security-check] CHANGELOG.md no tiene ninguna entrada "## [X.Y.Z]"');
    return 2;
  }

  let commits;
  let range;
  if (args['commits-json']) {
    commits = JSON.parse(readFileSync(resolve(cwd, args['commits-json']), 'utf8'));
    range = args['commits-json'];
  } else {
    const since = args.since || (entry.previous ? `v${entry.previous}` : null);
    if (!since) {
      console.error('[changelog-security-check] no hay versión anterior en el changelog; indica --since <ref>');
      return 2;
    }
    if (!refExists(since, cwd)) {
      console.error(`[changelog-security-check] la referencia ${since} no existe en este repositorio (¿falta la etiqueta?)`);
      return 2;
    }
    range = `${since}..HEAD`;
    try {
      commits = commitsFromGit(range, cwd);
    } catch (err) {
      console.error(`[changelog-security-check] git log falló: ${err.message}`);
      return 2;
    }
  }

  const result = evaluate({ changelog, commits });
  if (args.json) console.log(JSON.stringify(result, null, 2));

  console.error(
    `[changelog-security-check] versión ${result.version} (${range}): ` +
      `${commits.length} commit(s), ${result.security_commits.length} de seguridad`,
  );
  for (const commit of result.security_commits) {
    console.error(`  - ${commit.subject} — ${commit.reasons.join(', ')}`);
  }
  if (result.ok) {
    const state = result.section_present ? 'con sección Security' : 'sin cambios de seguridad, sección no exigida';
    console.error(`\n[changelog-security-check] OK — ${state}`);
    return 0;
  }
  for (const problem of result.problems) console.error(`  FAIL ${problem}`);
  console.error(`\n[changelog-security-check] FAIL — ${result.problems.length} problema(s)`);
  return result.code;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exit(main(process.argv.slice(2)));
}
