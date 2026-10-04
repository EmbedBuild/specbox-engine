/**
 * UC-7201 (US-72): un proyecto activa los mismos hooks que el engine.
 *
 * templates/settings.json.template (lo que reciben los proyectos al hacer onboard_project o
 * upgrade_project) y .claude/settings.json del engine registran los mismos hooks, con el mismo
 * evento, matcher, condición y tiempo; cada hook registrado existe; y cada hook de .claude/hooks que
 * no se registra figura en NOT_WIRED con su motivo. Un hook nuevo sin decidir hace fallar la prueba.
 *
 * Ejecutar: node --test tests/hooks/settings-template.test.mjs
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = resolve(fileURLToPath(import.meta.url), '../../..');
const hooksDir = join(repoRoot, '.claude/hooks');

/** Hooks que solo activa el engine, con su motivo. Hoy ninguno: los proyectos llevan todos. */
const ENGINE_ONLY = {};

/** Hooks que existen y no se registran en ningún settings, con su motivo. */
const NOT_WIRED = {
  'branch-guard': 'sustituido: spec-guard ya bloquea escribir código en main o master',
  'implement-checkpoint': 'lo llama la skill /implement al cerrar cada fase',
  'implement-healing': 'lo llama la skill /implement para registrar cada reparación',
  'post-implement-validate': 'manual: compara la baseline de calidad después de /implement',
  'test-hooks': 'es el script de pruebas de los hooks, no un hook',
};

/** Cada registro de hook: «evento | matcher | condición | nombre | tiempo». */
function registrations(path) {
  const settings = JSON.parse(readFileSync(join(repoRoot, path), 'utf8'));
  const out = [];
  for (const [event, groups] of Object.entries(settings.hooks ?? {})) {
    for (const group of groups) {
      for (const hook of group.hooks ?? []) {
        const name = hook.command?.match(/\.claude\/hooks\/([a-z0-9-]+)\.mjs/)?.[1];
        if (!name) continue;
        out.push({ key: [event, group.matcher ?? '*', hook.if ?? '', name, hook.timeout].join(' | '), name });
      }
    }
  }
  return out;
}

const engine = registrations('.claude/settings.json');
const template = registrations('templates/settings.json.template');
const names = (regs) => new Set(regs.map((r) => r.name));
const hookFiles = readdirSync(hooksDir)
  .filter((f) => f.endsWith('.mjs'))
  .map((f) => f.slice(0, -'.mjs'.length));

test('la plantilla registra cada hook del engine con el mismo evento, matcher, condición y tiempo', () => {
  const expected = engine.filter((r) => !(r.name in ENGINE_ONLY)).map((r) => r.key).sort();
  assert.deepEqual(template.map((r) => r.key).sort(), expected);
});

test('los siete hooks que faltaban (US-72) están en la plantilla', () => {
  const inTemplate = names(template);
  for (const name of [
    'session-start',
    'pre-read-budget-guard',
    'context-budget-guard',
    'file-ownership-guard',
    'freeform-path-guard',
    'pre-prd-discovery-check',
    'app-docs-sync-guard',
  ]) {
    assert.ok(inTemplate.has(name), name);
  }
});

test('cada hook registrado existe en .claude/hooks', () => {
  for (const name of new Set([...names(engine), ...names(template)])) {
    assert.ok(existsSync(join(hooksDir, `${name}.mjs`)), `${name}.mjs`);
  }
});

test('cada hook de .claude/hooks está registrado o en NOT_WIRED con su motivo', () => {
  const wired = new Set([...names(engine), ...names(template)]);
  const undecided = hookFiles.filter((name) => !wired.has(name) && !(name in NOT_WIRED));
  assert.deepEqual(undecided, [], 'regístralo en los dos settings o añádelo a NOT_WIRED con su motivo');
  for (const name of Object.keys(NOT_WIRED)) {
    assert.ok(hookFiles.includes(name), `NOT_WIRED nombra ${name}, que ya no existe`);
    assert.ok(!wired.has(name), `${name} está registrado: sácalo de NOT_WIRED`);
  }
  for (const name of Object.keys(ENGINE_ONLY)) {
    assert.ok(names(engine).has(name) && !names(template).has(name), `ENGINE_ONLY: ${name}`);
  }
});
