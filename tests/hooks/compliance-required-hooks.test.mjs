/**
 * UC-7501 (US-75): /compliance exige los hooks que la plantilla de proyectos instala.
 *
 * .quality/scripts/audit-hooks.mjs deriva la lista de templates/settings.json.template más los
 * ayudantes de /implement, y los módulos de lib/ de lo que esos hooks importan. Antes era una lista
 * a mano que exigía hooks retirados en la 6.1.0 y no conocía los nuevos.
 *
 * Ejecutar: node --test tests/hooks/compliance-required-hooks.test.mjs
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { requiredHooks, requiredLibFiles } from '../../.quality/scripts/audit-hooks.mjs';

const repoRoot = resolve(fileURLToPath(import.meta.url), '../../..');
const hooks = requiredHooks(repoRoot);
const files = hooks.map((h) => h.file);

test('exige cada hook que registra la plantilla, y los ayudantes de /implement', () => {
  const template = readFileSync(join(repoRoot, 'templates/settings.json.template'), 'utf8');
  const wired = new Set([...template.matchAll(/\.claude\/hooks\/([a-z0-9-]+\.mjs)/g)].map((m) => m[1]));
  for (const file of wired) assert.ok(files.includes(file), file);
  for (const file of ['implement-checkpoint.mjs', 'implement-healing.mjs']) assert.ok(files.includes(file), file);
  assert.equal(new Set(files).size, files.length, 'sin repetidos');
});

test('no exige hooks retirados ni sustituidos', () => {
  for (const file of ['mcp-report.mjs', 'heartbeat-sender.mjs', 'branch-guard.mjs']) assert.ok(!files.includes(file), file);
  assert.ok(!requiredLibFiles(repoRoot).includes('http.mjs'), 'lib/http.mjs se retiró en la 6.1.0');
});

test('los que bloquean son críticos; los que avisan, no', () => {
  const critical = (f) => hooks.find((h) => h.file === f)?.critical;
  for (const f of ['quality-first-guard.mjs', 'spec-guard.mjs', 'no-bypass-guard.mjs', 'read-tracker.mjs']) assert.equal(critical(f), true, f);
  for (const f of ['session-start.mjs', 'pre-read-budget-guard.mjs', 'uc-lifecycle-guard.mjs']) assert.equal(critical(f), false, f);
  for (const h of hooks) assert.ok(h.desc, `${h.file} sin descripción`);
});

test('cada hook y cada módulo de lib/ exigidos existen en el engine', () => {
  for (const f of files) assert.ok(existsSync(join(repoRoot, '.claude/hooks', f)), f);
  const libs = requiredLibFiles(repoRoot);
  assert.ok(libs.includes('utils.mjs') && libs.includes('output.mjs'));
  for (const l of libs) assert.ok(existsSync(join(repoRoot, '.claude/hooks/lib', l)), `lib/${l}`);
});
