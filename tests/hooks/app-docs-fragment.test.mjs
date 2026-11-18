/**
 * UC-12203 — el hook app-docs-fragment escribe la zona «roadmap» de app_prd.md.
 *
 * - AC-02: tras complete_uc del MCP remoto la zona queda con lo que manda el servidor.
 * - AC-04: solo escribe en la rama principal; en una rama de trabajo lo deja (no hay conflicto al
 *   fusionar: la zona sale del tablero).
 * - AC-05: en un satélite multirepo escribe la del orquestador y el satélite no guarda copia.
 * - FreeForm por fragmentos: calcula el cuerpo con su items.json. El cuerpo no llega al modelo.
 * Ejecutar: node --test tests/hooks/app-docs-fragment.test.mjs
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { render, rowsFromItems } from '../../.claude/hooks/lib/roadmap.mjs';

const repoRoot = resolve(fileURLToPath(import.meta.url), '../../..');
const HOOK = join(repoRoot, '.claude/hooks/app-docs-fragment.mjs');
const DOC = `# PRD

<!-- @specbox:zone start kind="auto" id="roadmap" auto_sync_on="complete_uc,move_uc,add_uc,delete_uc,mark_ac_batch" -->
## 5. Roadmap de US

| viejo |
<!-- @specbox:zone end -->

Fin
`;
const BODY = '## 5. Roadmap de US\n\n| US | Título | Estado | UCs |\n|----|--------|--------|-----|\n| US-01 | Pagos | done | 2/2 |';

function repo(dir, branch, files = {}) {
  mkdirSync(dir, { recursive: true });
  spawnSync('git', ['init', '-q', '-b', branch], { cwd: dir });
  for (const [rel, content] of Object.entries(files)) {
    mkdirSync(dirname(join(dir, rel)), { recursive: true });
    writeFileSync(join(dir, rel), typeof content === 'string' ? content : JSON.stringify(content));
  }
  return dir;
}

function hook(dir, tool, response) {
  const payload = { hook_event_name: 'PostToolUse', tool_name: `mcp__SpecBox-MCP__${tool}`, tool_input: {}, tool_response: response, cwd: dir };
  const r = spawnSync(process.execPath, [HOOK], { cwd: dir, input: JSON.stringify(payload), encoding: 'utf8' });
  return { code: r.status, out: r.stdout ? JSON.parse(r.stdout) : null };
}

const remote = (body) => [{ type: 'text', text: JSON.stringify(body) }];
const SYNC = { ok: true, document: 'doc/app/app_prd.md', zone: 'roadmap', roadmap_body: BODY };

test('en main, la zona queda con lo que manda el servidor y el cuerpo no llega al modelo (AC-02)', () => {
  const base = mkdtempSync(join(tmpdir(), 'app-docs-'));
  try {
    const dir = repo(join(base, 'p'), 'main', { 'doc/app/app_prd.md': DOC });
    const r = hook(dir, 'complete_uc', remote({ uc_id: 'UC-001', completed_at: 'x', app_docs_sync: SYNC }));
    assert.equal(r.code, 0);
    const doc = readFileSync(join(dir, 'doc/app/app_prd.md'), 'utf-8');
    assert.match(doc, /\| US-01 \| Pagos \| done \| 2\/2 \|/);
    assert.doesNotMatch(doc, /viejo/);
    assert.ok(doc.startsWith('# PRD') && doc.endsWith('Fin\n')); // lo de fuera de la zona no cambia
    assert.ok(!JSON.stringify(r.out.hookSpecificOutput.updatedToolOutput).includes('roadmap_body'));
  } finally {
    rmSync(base, { recursive: true, force: true });
  }
});

test('en una rama de trabajo no escribe: no hay conflicto al fusionar (AC-04)', () => {
  const base = mkdtempSync(join(tmpdir(), 'app-docs-'));
  try {
    const dir = repo(join(base, 'p'), 'feature/UC-1-x', { 'doc/app/app_prd.md': DOC });
    hook(dir, 'move_uc', remote({ uc_id: 'UC-001', new_status: 'review', app_docs_sync: SYNC }));
    assert.equal(readFileSync(join(dir, 'doc/app/app_prd.md'), 'utf-8'), DOC);
  } finally {
    rmSync(base, { recursive: true, force: true });
  }
});

test('en un satélite escribe la zona del orquestador; el satélite no guarda copia (AC-05)', () => {
  const base = mkdtempSync(join(tmpdir(), 'app-docs-'));
  try {
    const orq = repo(join(base, 'manager'), 'main', { 'doc/app/app_prd.md': DOC });
    const sat = repo(join(orq, 'repositorios', 'engine'), 'feature/UC-1-x', {
      '.claude/settings.local.json': { multirepo: { enabled: true, role: 'satellite', orchestrator: '../..' } },
    });
    hook(sat, 'complete_uc', remote({ uc_id: 'UC-001', app_docs_sync: SYNC }));
    assert.match(readFileSync(join(orq, 'doc/app/app_prd.md'), 'utf-8'), /US-01 \| Pagos/);
    assert.equal(existsSync(join(sat, 'doc/app/app_prd.md')), false);
  } finally {
    rmSync(base, { recursive: true, force: true });
  }
});

test('FreeForm por fragmentos: el hook calcula el cuerpo con su items.json', () => {
  const base = mkdtempSync(join(tmpdir(), 'app-docs-'));
  try {
    const items = [
      { id: 'us1', name: 'US-01: Pagos', labels: ['US'], state: 'in_progress', meta: { us_id: 'US-01' } },
      { id: 'uc1', name: 'UC-001: Cobrar', labels: ['UC'], state: 'done', parent_id: 'us1', meta: { uc_id: 'UC-001' } },
    ];
    const dir = repo(join(base, 'p'), 'main', { 'doc/app/app_prd.md': DOC, 'doc/tracking/items.json': items });
    hook(dir, 'mark_ac_batch', remote({ uc_id: 'UC-001', app_docs_sync: { ok: true, document: 'doc/app/app_prd.md', zone: 'roadmap', render: 'client' } }));
    const doc = readFileSync(join(dir, 'doc/app/app_prd.md'), 'utf-8');
    assert.ok(doc.includes(render(rowsFromItems(items))));
    assert.match(doc, /\| US-01 \| Pagos \| in_progress \| 1\/1 \|/);
  } finally {
    rmSync(base, { recursive: true, force: true });
  }
});

test('sin app_prd.md, con un fallo o con otra tool, no toca nada', () => {
  const base = mkdtempSync(join(tmpdir(), 'app-docs-'));
  try {
    const dir = repo(join(base, 'p'), 'main', { 'doc/app/app_prd.md': DOC });
    hook(dir, 'complete_uc', remote({ uc_id: 'UC-001', app_docs_sync: { ok: false, zone: 'roadmap', reason: 'x' } }));
    hook(dir, 'get_uc', remote({ uc_id: 'UC-001', app_docs_sync: SYNC }));
    assert.equal(readFileSync(join(dir, 'doc/app/app_prd.md'), 'utf-8'), DOC);
    const vacio = repo(join(base, 'q'), 'main');
    assert.equal(hook(vacio, 'complete_uc', remote({ app_docs_sync: SYNC })).code, 0);
  } finally {
    rmSync(base, { recursive: true, force: true });
  }
});
