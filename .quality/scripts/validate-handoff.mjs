#!/usr/bin/env node
/**
 * validate-handoff.mjs — Validates a .quality/handoff.md against doc/specs/handoff-spec.md
 *
 * Usage:
 *   node .quality/scripts/validate-handoff.mjs <path>
 *
 * Exit:
 *   0 — valid
 *   1 — invalid (first failure printed to stderr)
 */

import { readFileSync, existsSync } from 'fs';

const REQUIRED_FRONTMATTER_FIELDS = [
  'generated_at',
  'generator',
  'schema_version',
  'project',
  'session_id',
  'trigger',
  'ttl_minutes',
  'branch',
  'active_uc',
];

const REQUIRED_SECTIONS = [
  '## State snapshot',
  '## What this session did',
  '## Decisions taken (with key)',
  '## Open questions',
  '## Hot files (top N by edits this session)',
  '## Next concrete step',
  '## Pointers para la próxima sesión',
];

const VALID_TRIGGERS = ['manual', 'auto-pre-compact', 'session-end'];
const SCHEMA_VERSION = 1;
const MAX_CHARS = 14000;

function fail(msg) {
  console.error(`[INVALID] ${msg}`);
  process.exit(1);
}

function parseFrontmatter(content) {
  if (!content.startsWith('---\n')) {
    fail('missing frontmatter (file does not start with "---")');
  }
  const end = content.indexOf('\n---\n', 4);
  if (end === -1) fail('frontmatter not closed (no second "---" delimiter)');
  const fm = content.slice(4, end);
  const body = content.slice(end + 5);
  const obj = {};
  for (const line of fm.split('\n')) {
    if (!line.trim()) continue;
    const colon = line.indexOf(':');
    if (colon === -1) continue;
    const key = line.slice(0, colon).trim();
    let val = line.slice(colon + 1).trim();
    if (val === 'null') val = null;
    else if (/^-?\d+$/.test(val)) val = Number(val);
    obj[key] = val;
  }
  return { fm: obj, body };
}

function main() {
  const path = process.argv[2];
  if (!path) fail('Usage: validate-handoff.mjs <path>');
  if (!existsSync(path)) fail(`file not found: ${path}`);

  const content = readFileSync(path, 'utf-8');
  if (content.length > MAX_CHARS) {
    fail(`file too large: ${content.length} chars (max ${MAX_CHARS})`);
  }

  const { fm, body } = parseFrontmatter(content);

  for (const f of REQUIRED_FRONTMATTER_FIELDS) {
    if (!(f in fm)) fail(`missing frontmatter field: ${f}`);
  }

  if (fm.schema_version !== SCHEMA_VERSION) {
    fail(`schema_version must be ${SCHEMA_VERSION}, got ${fm.schema_version}`);
  }

  if (!VALID_TRIGGERS.includes(fm.trigger)) {
    fail(`invalid trigger "${fm.trigger}", must be one of ${VALID_TRIGGERS.join(', ')}`);
  }

  if (typeof fm.ttl_minutes !== 'number' || fm.ttl_minutes <= 0) {
    fail(`ttl_minutes must be positive number, got ${fm.ttl_minutes}`);
  }

  for (const section of REQUIRED_SECTIONS) {
    if (!body.includes(section)) fail(`missing section: ${section}`);
  }

  const generatedAt = new Date(fm.generated_at);
  if (Number.isNaN(generatedAt.getTime())) {
    fail(`invalid generated_at: ${fm.generated_at}`);
  }
  const ageMin = (Date.now() - generatedAt.getTime()) / 60000;
  const stale = ageMin > fm.ttl_minutes;

  console.log(`[VALID] ${path}`);
  console.log(`        project=${fm.project} branch=${fm.branch} active_uc=${fm.active_uc}`);
  console.log(`        age=${Math.round(ageMin)}min ttl=${fm.ttl_minutes}min ${stale ? '[STALE]' : '[FRESH]'}`);
  process.exit(0);
}

main();
