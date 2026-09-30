// UC-3904 AC-02/AC-03 y UC-3901 AC-03 — el ayudante que ejecuta Claude Code,
// el flujo de `specbox login` y la configuración de Claude Code.
import assert from "node:assert/strict";
import { existsSync, mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import {
  claudeUsesHelper,
  configureClaudeCode,
  findSpecboxEntries,
  helperCommand,
  helperPaths,
  stableNodePath,
  withHelper,
} from "../lib/claude.mjs";
import { accountFor } from "../lib/config.mjs";
import { deviceId, hostLabel, machineId } from "../lib/device.mjs";
import { RUNTIME_FILES, installHelper } from "../lib/install.mjs";
import { LoginError, deviceLogin } from "../lib/login.mjs";
import { headersFor } from "../lib/mcp-headers.mjs";
import { fileStore } from "../lib/store.mjs";

const MCP = "https://mcp.example/mcp";
const ACCOUNT = accountFor(MCP);
const TOKEN_BODY = {
  access_token: "spbx_deldispositivo",
  token_id: "t1",
  expires_at: "2026-12-28T10:00:00.000Z",
  renew_after: "2026-12-14T10:00:00.000Z",
  developer: { developer_id: "jesus", display_name: "Jesús Pérez", handle: "jesusperezdeveloper" },
  device: { device_id: "d".repeat(64), device_name: "Jesús Pérez · Mac · Claude Code", client: "claude-code" },
  replaced_token_ids: [],
};

// ── Ayudante de cabeceras ─────────────────────────────────────────────

test("sin credencial el ayudante devuelve {} (conexión sin token)", async () => {
  const store = fileStore(mkdtempSync(join(tmpdir(), "specbox-h-")));
  assert.deepEqual(await headersFor({ env: { CLAUDE_CODE_MCP_SERVER_URL: MCP }, store }), {});
});

test("con credencial devuelve la cabecera del servidor que pide Claude Code", async () => {
  const home = mkdtempSync(join(tmpdir(), "specbox-h-"));
  const store = fileStore(home);
  store.write(ACCOUNT, { token: "spbx_a", expires_at: "2027-01-01T00:00:00Z", renew_after: "2026-12-18T00:00:00Z" });
  store.write("https://otro.example/mcp", { token: "spbx_otro" });
  const headers = await headersFor({
    env: { CLAUDE_CODE_MCP_SERVER_URL: `${MCP}/`, SPECBOX_HOME: home },
    store,
    now: Date.parse("2026-10-01T00:00:00Z"),
    fetchImpl: async () => assert.fail("no toca renovar"),
  });
  assert.deepEqual(headers, { Authorization: "Bearer spbx_a" });
});

test("cuando toca, renueva antes de devolver la cabecera", async () => {
  const home = mkdtempSync(join(tmpdir(), "specbox-h-"));
  const store = fileStore(home);
  store.write(ACCOUNT, { token: "spbx_viejo", expires_at: "2026-12-28T10:00:00Z", renew_after: "2026-12-14T10:00:00Z", cloud_api: "https://api.example/api" });
  const headers = await headersFor({
    env: { CLAUDE_CODE_MCP_SERVER_URL: MCP, SPECBOX_HOME: home },
    store,
    now: Date.parse("2026-12-20T00:00:00Z"),
    fetchImpl: async () => ({ status: 200, json: async () => TOKEN_BODY }),
  });
  assert.deepEqual(headers, { Authorization: "Bearer spbx_deldispositivo" });
  assert.equal(store.read(ACCOUNT).token, "spbx_deldispositivo");
});

// ── Dispositivo ───────────────────────────────────────────────────────

test("el id del dispositivo es estable por máquina y cliente y no revela la máquina", () => {
  const a = deviceId("claude-code", { machine: "UUID-1" });
  assert.match(a, /^[0-9a-f]{64}$/);
  assert.equal(a, deviceId("claude-code", { machine: "UUID-1" }));
  assert.notEqual(a, deviceId("cursor", { machine: "UUID-1" }));
  assert.notEqual(a, deviceId("claude-code", { machine: "UUID-2" }));
  assert.ok(!a.includes("UUID"));
});

test("sin id de máquina se usa uno aleatorio guardado en ~/.specbox/device-id", () => {
  const home = mkdtempSync(join(tmpdir(), "specbox-dev-"));
  const first = deviceId("claude-code", { home, machine: null });
  assert.equal(first, deviceId("claude-code", { home, machine: null }));
  assert.ok(existsSync(join(home, "device-id")));
});

test("lee el id de máquina de cada sistema", () => {
  const darwin = machineId({ platform: "darwin", run: () => '  "IOPlatformUUID" = "ABC-123"\n' });
  assert.equal(darwin, "ABC-123");
  const win = machineId({ platform: "win32", run: () => "    MachineGuid    REG_SZ    9f-guid\r\n" });
  assert.equal(win, "9f-guid");
  const linux = machineId({ platform: "linux", readFile: () => "abc123\n" });
  assert.equal(linux, "abc123");
  assert.equal(machineId({ platform: "linux", readFile: () => { throw new Error("no"); } }), null);
});

test("el nombre del ordenador se limpia y se recorta a 80 caracteres", () => {
  assert.equal(hostLabel("MacBook-Pro-de-Jesus.local"), "MacBook-Pro-de-Jesus");
  assert.equal(hostLabel("a\u0007b"), "ab");
  assert.equal(hostLabel("x".repeat(100)).length, 80);
  assert.equal(hostLabel(""), "ordenador");
});

// ── specbox login (código de un solo uso) ─────────────────────────────

function flow(...replies) {
  const calls = [];
  const fetchImpl = async (url, init) => {
    calls.push({ url, body: JSON.parse(init.body) });
    const [status, body] = replies.shift();
    return { status, json: async () => body };
  };
  return { fetchImpl, calls };
}

test("espera la confirmación, respeta slow_down y guarda el token sin enseñarlo", async () => {
  const store = fileStore(mkdtempSync(join(tmpdir(), "specbox-l-")));
  const { fetchImpl, calls } = flow(
    [200, { device_code: "spbxd_x", user_code: "KQ7M-4TZP", verification_uri_complete: "https://p/device?code=KQ7M-4TZP", expires_in: 600, interval: 5 }],
    [400, { error: "authorization_pending" }],
    [400, { error: "slow_down" }],
    [200, TOKEN_BODY],
  );
  const waits = [];
  let shown = null;
  let clock = 0;
  const cred = await deviceLogin({
    cloudApi: "https://api.example/api",
    account: ACCOUNT,
    store,
    device: { device_id: "d".repeat(64), host: "Mac", client: "claude-code" },
    fetchImpl,
    sleep: async (ms) => {
      waits.push(ms);
      clock += ms;
    },
    now: () => clock,
    onCode: (code) => {
      shown = code.user_code;
    },
  });
  assert.equal(shown, "KQ7M-4TZP");
  assert.deepEqual(waits, [5000, 5000, 10000]);
  assert.deepEqual(calls[0].body, { device_id: "d".repeat(64), host: "Mac", client: "claude-code" });
  assert.deepEqual(calls[1].body, { device_code: "spbxd_x" });
  assert.equal(cred.token, "spbx_deldispositivo");
  assert.equal(store.read(ACCOUNT).token, "spbx_deldispositivo");
});

test("rechazado en el navegador, caducado o sin respuesta a tiempo → LoginError con motivo", async () => {
  const base = { cloudApi: "https://api.example/api", account: ACCOUNT, device: {}, sleep: async () => {} };
  const code = [200, { device_code: "spbxd_x", user_code: "X", expires_in: 600, interval: 1 }];
  for (const [reply, expected] of [
    [[400, { error: "access_denied" }], "denied"],
    [[400, { error: "expired_token" }], "expired"],
    [[409, { error: "device_limit" }], "device_limit"], // UC-3902 AC-04
    [[400, { error: "invalid_grant" }], "expired"],
  ]) {
    const store = fileStore(mkdtempSync(join(tmpdir(), "specbox-l-")));
    await assert.rejects(
      deviceLogin({ ...base, store, fetchImpl: flow(code, reply).fetchImpl }),
      (err) => err instanceof LoginError && err.code === expected,
    );
    assert.equal(store.read(ACCOUNT), null);
  }
  let clock = 0;
  const pending = async (url) => (url.endsWith("/device/code")
    ? { status: 200, json: async () => ({ device_code: "spbxd_x", user_code: "X", expires_in: 3, interval: 1 }) }
    : { status: 400, json: async () => ({ error: "authorization_pending" }) });
  await assert.rejects(
    deviceLogin({ ...base, store: fileStore(mkdtempSync(join(tmpdir(), "specbox-l-"))), fetchImpl: pending, sleep: async (ms) => { clock += ms; }, now: () => clock }),
    (err) => err.code === "expired",
  );
});

// ── Claude Code ───────────────────────────────────────────────────────

function claudeRun({ missing = false } = {}) {
  const calls = [];
  const run = (cmd, args, opts = {}) => {
    calls.push({ cmd, args, cwd: opts.cwd ?? null });
    if (missing) return { status: null, stdout: "", stderr: "", error: Object.assign(new Error("x"), { code: "ENOENT" }) };
    return { status: 0, stdout: "", stderr: "", error: null };
  };
  return { run, calls };
}

test("configura SpecBox-MCP con el ayudante y migra las entradas locales que apuntan al mismo servidor", () => {
  const helper = helperCommand("/Users/j/.specbox/bin/mcp-headers.mjs", "/usr/local/bin/node");
  assert.equal(helper, '"/usr/local/bin/node" "/Users/j/.specbox/bin/mcp-headers.mjs"');
  const claudeJson = {
    mcpServers: { "SpecBox-MCP": { type: "http", url: MCP } },
    projects: {
      "/p/uno": { mcpServers: { "specbox-engine": { type: "http", url: MCP, headers: { Authorization: "Bearer viejo", "X-Otra": "1" } } } },
      "/p/borrado": { mcpServers: { "specbox-engine": { type: "http", url: MCP } } },
      "/p/otro": { mcpServers: { stripe: { type: "stdio", command: "x" } } },
    },
  };
  const { run, calls } = claudeRun();
  const result = configureClaudeCode({
    mcpUrl: MCP,
    helperCmd: helper,
    run,
    claudeJsonPath: "/fake/.claude.json",
    readFile: () => JSON.stringify(claudeJson),
    projectExists: (p) => p !== "/p/borrado",
  });
  assert.equal(result.ok, true);
  assert.deepEqual(result.updated.map((u) => [u.scope, u.name, u.cwd]), [
    ["user", "SpecBox-MCP", null],
    ["local", "specbox-engine", "/p/uno"],
  ]);
  const addUser = calls.find((c) => c.args[1] === "add-json" && c.args[5] === "user");
  assert.deepEqual(JSON.parse(addUser.args[3]), { type: "http", url: MCP, headersHelper: helper });
  const addLocal = calls.find((c) => c.args[1] === "add-json" && c.cwd === "/p/uno");
  assert.deepEqual(JSON.parse(addLocal.args[3]), { type: "http", url: MCP, headers: { "X-Otra": "1" }, headersHelper: helper });
  assert.ok(!calls.some((c) => c.cwd === "/p/borrado"));
});

test("sin la orden claude devuelve la orden exacta para ejecutarla a mano", () => {
  const { run } = claudeRun({ missing: true });
  const result = configureClaudeCode({ mcpUrl: MCP, helperCmd: "h", run, readFile: () => "{}" });
  assert.equal(result.ok, false);
  assert.equal(result.reason, "claude_missing");
  assert.match(result.manual, /^claude mcp add-json SpecBox-MCP '\{"type":"http","url":"https:\/\/mcp\.example\/mcp","headersHelper":"h"\}' --scope user$/);
});

test("findSpecboxEntries solo encuentra entradas del mismo servidor; withHelper quita el Authorization fijo", () => {
  const found = findSpecboxEntries({ mcpServers: { a: { url: "https://otro/mcp" }, b: { url: `${MCP}` } } }, MCP);
  assert.deepEqual(found.map((f) => f.name), ["b"]);
  assert.deepEqual(withHelper({ type: "sse", url: MCP, headers: { authorization: "x" } }, "h"), { type: "sse", url: MCP, headersHelper: "h" });
});

test("el ayudante graba la ruta de Node del PATH que sobrevive a `brew upgrade`, no la versionada", () => {
  const cellar = "/opt/homebrew/Cellar/node/26.7.0/bin/node";
  const links = { "/usr/bin/node": "/usr/bin/node", "/opt/homebrew/bin/node": cellar, [cellar]: cellar };
  const realpath = (p) => {
    if (!(p in links)) throw Object.assign(new Error("ENOENT"), { code: "ENOENT" });
    return links[p];
  };
  const exists = (p) => p in links;
  const base = { execPath: cellar, platform: "darwin", realpath, exists };
  // /usr/bin/node es otro Node: no vale aunque vaya antes en el PATH
  assert.equal(stableNodePath({ ...base, pathEnv: "/nada:/usr/bin:/opt/homebrew/bin" }), "/opt/homebrew/bin/node");
  // si ninguna entrada del PATH apunta al Node en uso, se queda la ruta real
  assert.equal(stableNodePath({ ...base, pathEnv: "/usr/bin" }), cellar);
  assert.equal(stableNodePath({ ...base, pathEnv: "" }), cellar);
  // Windows: node.exe y separador ;
  const exe = "C:\\Program Files\\nodejs\\node.exe";
  assert.equal(
    stableNodePath({ execPath: exe, platform: "win32", pathEnv: "C:\\Windows;C:\\Program Files\\nodejs", realpath: (p) => p, exists: (p) => p === exe }),
    exe,
  );
});

test("status solo da por bueno el ayudante si su Node y su script siguen existiendo", () => {
  const helper = helperCommand("/Users/j/.specbox/bin/mcp-headers.mjs", "/opt/homebrew/Cellar/node/26.7.0/bin/node");
  assert.deepEqual(helperPaths(helper), { node: "/opt/homebrew/Cellar/node/26.7.0/bin/node", helper: "/Users/j/.specbox/bin/mcp-headers.mjs" });
  assert.equal(helperPaths("node ayudante.mjs"), null);
  const readFile = () => JSON.stringify({ mcpServers: { "SpecBox-MCP": { type: "http", url: MCP, headersHelper: helper } } });
  assert.equal(claudeUsesHelper({ readFile, exists: () => true }), true);
  // `brew upgrade` borró esa versión de Node: la extensión reconfigura en el siguiente arranque
  assert.equal(claudeUsesHelper({ readFile, exists: (p) => !p.includes("/Cellar/") }), false);
  assert.equal(claudeUsesHelper({ readFile: () => JSON.stringify({ mcpServers: { "SpecBox-MCP": { url: MCP } } }), exists: () => true }), false);
  assert.equal(claudeUsesHelper({ readFile: () => "{no es json", exists: () => true }), false);
});

test("instala el ayudante y sus módulos en ~/.specbox/bin como ESM", () => {
  const home = mkdtempSync(join(tmpdir(), "specbox-i-"));
  const helper = installHelper(home, { version: "6.14.0" });
  assert.equal(helper, join(home, "bin", "mcp-headers.mjs"));
  for (const file of RUNTIME_FILES) assert.ok(existsSync(join(home, "bin", file)));
  const pkg = JSON.parse(readFileSync(join(home, "bin", "package.json"), "utf8"));
  assert.deepEqual(pkg, { private: true, type: "module", specbox_helper_version: "6.14.0" });
});
