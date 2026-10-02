// UC-5102 — la mudanza a mcp.specbox.build: nadie pierde la conexión.
//   - una credencial guardada con el nombre antiguo sirve para el nuevo (y se copia);
//   - las entradas de Claude Code con el nombre antiguo se reescriben, guardando copia;
//   - la extensión actualizada lo detecta y reconfigura sin pasos manuales.
// Sin red, sin Llavero y sin tocar ~/.specbox: almacén y copia de seguridad falsos.

import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  DEFAULT_MCP_URL,
  LEGACY_MCP_URLS,
  accountFor,
  isLegacyMcpUrl,
  legacyAccountsFor,
  migrateMcpUrl,
  serverOrigins,
} from "../lib/config.mjs";
import { withLegacyAccounts } from "../lib/store.mjs";
import { headersFor } from "../lib/mcp-headers.mjs";
import { claudeUsesHelper, configureClaudeCode, saveEntriesBackup } from "../lib/claude.mjs";

const NEW = "https://mcp.specbox.build/mcp";
const OLD = "https://mcp-specbox-engine.jpsdeveloper.com/mcp";
const HELPER = '"/usr/local/bin/node" "/Users/j/.specbox/bin/mcp-headers.mjs"';

/** Un almacén en memoria con la misma forma que los del sistema. */
function memoryStore(initial = {}) {
  const data = new Map(Object.entries(initial));
  const log = [];
  return {
    data,
    log,
    kind: "memory",
    read: (account) => data.get(account) ?? null,
    write: (account, credential) => (log.push(["write", account]), data.set(account, credential)),
    remove: (account) => (log.push(["remove", account]), data.delete(account)),
  };
}

test("AC-01: el nombre por defecto es mcp.specbox.build y el antiguo queda como anterior", () => {
  assert.equal(DEFAULT_MCP_URL, NEW);
  assert.deepEqual(LEGACY_MCP_URLS, [OLD]);
});

test("los dos nombres comparten credencial: la clave es siempre la del nombre nuevo", () => {
  assert.equal(accountFor(OLD), NEW);
  assert.equal(accountFor(`${OLD}/`), NEW);
  assert.equal(accountFor(NEW), NEW);
  assert.equal(accountFor("https://mi-servidor.example/mcp"), "https://mi-servidor.example/mcp");
  assert.deepEqual(legacyAccountsFor(NEW), [OLD]);
  assert.deepEqual(legacyAccountsFor("https://mi-servidor.example/mcp"), []);
});

test("solo el servidor de SpecBox tiene nombres anteriores; las URL se mudan conservando ruta y parámetros", () => {
  assert.equal(isLegacyMcpUrl(OLD), true);
  assert.equal(isLegacyMcpUrl("https://mcp-specbox-engine.jpsdeveloper.com/otra?x=1"), true);
  assert.equal(isLegacyMcpUrl(NEW), false);
  assert.equal(isLegacyMcpUrl(undefined), false);
  assert.equal(migrateMcpUrl(`${OLD}?a=1`), `${NEW}?a=1`);
  assert.equal(migrateMcpUrl("https://otro.example/mcp"), "https://otro.example/mcp");
  assert.deepEqual(serverOrigins(NEW), ["https://mcp.specbox.build", "https://mcp-specbox-engine.jpsdeveloper.com"]);
  assert.deepEqual(serverOrigins("https://mi-servidor.example/mcp"), ["https://mi-servidor.example"]);
});

test("una credencial guardada con el nombre antiguo se lee con el nuevo y se copia a él", () => {
  const inner = memoryStore({ [OLD]: { token: "spbx_viejo" } });
  const store = withLegacyAccounts(inner);
  assert.equal(store.read(NEW).token, "spbx_viejo");
  assert.equal(inner.data.get(NEW).token, "spbx_viejo", "se copia a la clave nueva");
  assert.equal(inner.data.get(OLD).token, "spbx_viejo", "la antigua se queda para una instalación sin actualizar");
  assert.equal(store.read("https://otro.example/mcp"), null);
});

test("con credencial en la clave nueva no se mira la antigua; cerrar sesión borra las dos", () => {
  const inner = memoryStore({ [NEW]: { token: "spbx_nuevo" }, [OLD]: { token: "spbx_viejo" } });
  const store = withLegacyAccounts(inner);
  assert.equal(store.read(NEW).token, "spbx_nuevo");
  store.remove(NEW);
  assert.equal(inner.data.size, 0);
});

test("el ayudante de cabeceras manda el token por los dos nombres, aunque la credencial sea de antes", async () => {
  for (const url of [OLD, NEW]) {
    const store = withLegacyAccounts(memoryStore({ [OLD]: { token: "spbx_viejo", expires_at: null } }));
    assert.deepEqual(await headersFor({ env: { CLAUDE_CODE_MCP_SERVER_URL: url }, store }), { Authorization: "Bearer spbx_viejo" }, url);
  }
});

/** `claude` falso: apunta las órdenes y siempre responde bien. */
function claudeRun() {
  const calls = [];
  return { calls, run: (cmd, args, opts = {}) => (calls.push({ args, cwd: opts.cwd ?? null }), { status: 0, stdout: "", stderr: "", error: null }) };
}

test("AC-02: reescribe al nombre nuevo las entradas del antiguo (usuario y proyectos) y guarda copia de lo que cambia", () => {
  const claudeJson = {
    mcpServers: { "SpecBox-MCP": { type: "http", url: OLD, headersHelper: HELPER } },
    projects: {
      "/p/uno": { mcpServers: { "specbox-engine": { type: "http", url: OLD, headersHelper: HELPER } } },
      "/p/dos": { mcpServers: { "SpecBox-MCP": { type: "http", url: OLD, headers: { Authorization: "Bearer fijo" } } } },
      "/p/ya": { mcpServers: { "SpecBox-MCP": { type: "http", url: NEW, headersHelper: HELPER } } },
      "/p/otro": { mcpServers: { stripe: { type: "http", url: "https://mcp.stripe.com" } } },
    },
  };
  const saved = [];
  const { run, calls } = claudeRun();
  const result = configureClaudeCode({
    mcpUrl: NEW,
    helperCmd: HELPER,
    run,
    readFile: () => JSON.stringify(claudeJson),
    projectExists: () => true,
    backup: (entries) => (saved.push(...entries), "/tmp/copia.json"),
  });
  assert.equal(result.ok, true);
  assert.equal(result.backup, "/tmp/copia.json");
  assert.deepEqual(result.updated.map((u) => [u.scope, u.name, u.cwd]), [
    ["user", "SpecBox-MCP", null],
    ["local", "specbox-engine", "/p/uno"],
    ["local", "SpecBox-MCP", "/p/dos"],
  ]);
  const added = calls.filter((c) => c.args[1] === "add-json").map((c) => [c.cwd, JSON.parse(c.args[3]).url]);
  assert.deepEqual(added, [[null, NEW], ["/p/uno", NEW], ["/p/dos", NEW]]);
  assert.ok(!calls.some((c) => c.cwd === "/p/ya" || c.cwd === "/p/otro"), "lo que ya está bien o no es SpecBox no se toca");
  // La copia guarda las entradas como estaban, sin el valor de ningún token fijo.
  assert.deepEqual(saved.map((e) => [e.scope, e.cwd, e.entry.url]), [["user", null, OLD], ["local", "/p/uno", OLD], ["local", "/p/dos", OLD]]);
  assert.equal(saved[2].entry.headers.Authorization, "***");
  assert.ok(!JSON.stringify(saved).includes("Bearer fijo"));
});

test("la copia de seguridad se escribe con permisos privados y sin nada que copiar no se crea", () => {
  const dir = mkdtempSync(join(tmpdir(), "specbox-backup-"));
  try {
    assert.equal(saveEntriesBackup([], { dir }), null);
    const file = saveEntriesBackup([{ scope: "user", name: "SpecBox-MCP", cwd: null, entry: { url: OLD } }], { dir, now: new Date("2026-10-02T11:00:00Z") });
    assert.equal(file, join(dir, "claude-mcp-20261002T110000Z.json"));
    assert.equal(JSON.parse(readFileSync(file, "utf8")).entries[0].entry.url, OLD);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("AC-02: la extensión actualizada ve que hay que reconfigurar si la entrada apunta al nombre antiguo", () => {
  const dir = mkdtempSync(join(tmpdir(), "specbox-claude-"));
  try {
    const claudeJsonPath = join(dir, ".claude.json");
    const exists = () => true;
    writeFileSync(claudeJsonPath, JSON.stringify({ mcpServers: { "SpecBox-MCP": { type: "http", url: OLD, headersHelper: HELPER } } }));
    assert.equal(claudeUsesHelper({ claudeJsonPath, exists }), false);
    writeFileSync(claudeJsonPath, JSON.stringify({ mcpServers: { "SpecBox-MCP": { type: "http", url: NEW, headersHelper: HELPER } } }));
    assert.equal(claudeUsesHelper({ claudeJsonPath, exists }), true);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
