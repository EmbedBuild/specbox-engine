// `specbox login | status | logout` de punta a punta con el panel simulado.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { parseArgs, run } from "../bin/specbox.mjs";
import { accountFor } from "../lib/config.mjs";
import { fileStore } from "../lib/store.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const MCP = "https://mcp-specbox-engine.jpsdeveloper.com/mcp";
const TOKEN_BODY = {
  access_token: "spbx_deldispositivo",
  token_id: "t1",
  expires_at: "2026-12-28T10:00:00.000Z",
  renew_after: "2026-12-14T10:00:00.000Z",
  developer: { developer_id: "jesus", display_name: "Jesús Pérez", handle: "jesusperezdeveloper" },
  device: { device_id: "d".repeat(64), device_name: "Jesús Pérez · Mac · Claude Code", client: "claude-code" },
  replaced_token_ids: [],
};

function harness(routes) {
  const out = [];
  const home = mkdtempSync(join(tmpdir(), "specbox-cli-"));
  const store = fileStore(home);
  const calls = [];
  const deps = {
    env: { LANG: "es_ES.UTF-8", SPECBOX_HOME: home },
    print: (line) => out.push(line),
    printErr: (line) => out.push(`ERR ${line}`),
    store,
    deviceId: "d".repeat(64),
    host: "Mac",
    sleep: async () => {},
    openUrl: (url) => out.push(`OPEN ${url}`),
    installHelper: () => join(home, "bin", "mcp-headers.mjs"),
    nodePath: "/usr/bin/node",
    claudeJsonPath: join(home, "no-existe.json"),
    runCommand: (cmd, args) => {
      calls.push([cmd, ...args]);
      return { status: 0, stdout: "", stderr: "", error: null };
    },
    fetchImpl: async (url, init = {}) => {
      calls.push([init.method ?? "GET", url]);
      const [status, body] = routes(url, init);
      return { status, json: async () => body };
    },
  };
  return { deps, out, store, calls, home };
}

test("parseArgs entiende la orden y las opciones", () => {
  assert.deepEqual(parseArgs(["login", "--no-browser", "--server", "https://s/mcp"]), {
    command: "login",
    server: "https://s/mcp",
    cloud: null,
    browser: false,
  });
  assert.equal(parseArgs(["--version"]).command, "version");
});

test("login: enseña el enlace y el código, abre el navegador, guarda el token y configura Claude Code", async () => {
  let polls = 0;
  const h = harness((url) => {
    if (url.endsWith("/device/code")) {
      return [200, { device_code: "spbxd_x", user_code: "KQ7M-4TZP", verification_uri_complete: "https://cloud.specbox.build/device?code=KQ7M-4TZP", expires_in: 600, interval: 5 }];
    }
    polls += 1;
    return polls < 2 ? [400, { error: "authorization_pending" }] : [200, TOKEN_BODY];
  });
  const code = await run(["login"], h.deps);
  assert.equal(code, 0);
  const text = h.out.join("\n");
  assert.match(text, /KQ7M-4TZP/);
  assert.match(text, /OPEN https:\/\/cloud\.specbox\.build\/device\?code=KQ7M-4TZP/);
  assert.match(text, /Conectado como @jesusperezdeveloper/);
  assert.match(text, /Claude Code configurado: SpecBox-MCP/);
  assert.ok(!text.includes("spbx_deldispositivo"), "el token no se enseña nunca");
  assert.equal(h.store.read(accountFor(MCP)).token, "spbx_deldispositivo");
  const add = h.calls.find((c) => c[0] === "claude" && c[2] === "add-json");
  assert.deepEqual(JSON.parse(add[4]), {
    type: "http",
    url: MCP,
    headersHelper: `"/usr/bin/node" "${join(h.home, "bin", "mcp-headers.mjs")}"`,
  });
});

test("status: cuenta, dispositivo, caducidad y validez comprobada con el panel", async () => {
  const h = harness((url) => (url.endsWith("/whoami") ? [200, {}] : [404, {}]));
  h.store.write(accountFor(MCP), { token: "spbx_x", cloud_api: "https://api.example/api", ...TOKEN_BODY, device_name: TOKEN_BODY.device.device_name });
  assert.equal(await run(["status"], h.deps), 0);
  const text = h.out.join("\n");
  assert.match(text, /@jesusperezdeveloper \(Jesús Pérez\)/);
  assert.match(text, /válido ✓/);
  assert.deepEqual(h.calls[0], ["GET", "https://api.example/api/whoami"]);
});

test("status sin conexión pide specbox login; con token revocado lo dice y sale con 1", async () => {
  const empty = harness(() => [200, {}]);
  assert.equal(await run(["status"], empty.deps), 1);
  assert.match(empty.out.join("\n"), /specbox login/);

  const revoked = harness(() => [401, {}]);
  revoked.store.write(accountFor(MCP), { token: "spbx_x", device_name: "Mac", expires_at: null });
  assert.equal(await run(["status"], revoked.deps), 1);
  assert.match(revoked.out.join("\n"), /caducado o revocado/);
});

test("logout: desconecta en el panel con su propio token y borra la credencial local", async () => {
  const h = harness((url) => (url.endsWith("/devices/logout") ? [200, {}] : [404, {}]));
  h.store.write(accountFor(MCP), { token: "spbx_x", device_name: "Mac", cloud_api: "https://api.example/api" });
  assert.equal(await run(["logout"], h.deps), 0);
  assert.deepEqual(h.calls[0], ["POST", "https://api.example/api/devices/logout"]);
  assert.equal(h.store.read(accountFor(MCP)), null);
  assert.match(h.out.join("\n"), /Dispositivo desconectado: «Mac»/);
});

test("el binario responde a --version y --help", () => {
  const bin = join(HERE, "..", "bin", "specbox.mjs");
  assert.match(execFileSync(process.execPath, [bin, "--version"], { encoding: "utf8" }), /^\d+\.\d+\.\d+/);
  assert.match(execFileSync(process.execPath, [bin, "--help"], { encoding: "utf8", env: { ...process.env, LANG: "en_US" } }), /Usage: specbox/);
});

// ── Órdenes internas para la extensión de VSCode (JSON por stdin/stdout) ──

function internal(h, command, input = {}) {
  return run([command], { ...h.deps, readInput: async () => input });
}

test("_device da el mismo dispositivo que specbox login", async () => {
  const h = harness(() => [200, {}]);
  assert.equal(await internal(h, "_device"), 0);
  assert.deepEqual(JSON.parse(h.out.at(-1)), { device_id: "d".repeat(64), host: "Mac", client: "claude-code" });
});

test("_connect guarda la credencial de la extensión y configura Claude Code; _status nunca devuelve el token", async () => {
  const h = harness(() => [200, {}]);
  const credential = {
    token: "spbx_delaextension",
    token_id: "t9",
    expires_at: "2026-12-28T10:00:00.000Z",
    renew_after: "2026-12-14T10:00:00.000Z",
    device_id: "d".repeat(64),
    device_name: "Jesús · Mac · Claude Code",
    client: "claude-code",
    developer: { developer_id: "jesus", display_name: "jesusperezdeveloper", handle: "jesusperezdeveloper" },
  };
  assert.equal(await internal(h, "_connect", { credential }), 0);
  const connected = JSON.parse(h.out.at(-1));
  assert.equal(connected.ok, true);
  assert.equal(connected.claude.ok, true);
  assert.ok(!h.out.at(-1).includes("spbx_delaextension"));
  assert.equal(h.store.read(accountFor(MCP)).token, "spbx_delaextension");

  assert.equal(await internal(h, "_status"), 0);
  const status = JSON.parse(h.out.at(-1));
  assert.equal(status.connected, true);
  assert.equal(status.device_name, "Jesús · Mac · Claude Code");
  assert.match(status.token_sha, /^[0-9a-f]{16}$/);
  assert.ok(!h.out.at(-1).includes("spbx_delaextension"));
});

test("_adopt obtiene un token de dispositivo con el que ya tenía la extensión (sin revocarlo) y lo conecta", async () => {
  let sent;
  const h = harness((url, init) => {
    sent = { url, auth: init.headers.authorization, body: JSON.parse(init.body) };
    return [200, TOKEN_BODY];
  });
  assert.equal(await internal(h, "_adopt", { token: "spbx_anterior", issued_via: "vscode" }), 0);
  const res = JSON.parse(h.out.at(-1));
  assert.equal(res.ok, true);
  assert.equal(res.token, "spbx_deldispositivo"); // la extensión lo guarda en su SecretStorage
  assert.equal(sent.url, "https://api-cloud.specbox.build/api/devices/adopt");
  assert.equal(sent.auth, "Bearer spbx_anterior");
  assert.deepEqual(sent.body, { device_id: "d".repeat(64), host: "Mac", client: "claude-code", issued_via: "vscode" });
  assert.equal(h.store.read(accountFor(MCP)).token, "spbx_deldispositivo");

  const bad = harness(() => [401, {}]);
  assert.equal(await internal(bad, "_adopt", { token: "spbx_revocado" }), 1);
  assert.equal(JSON.parse(bad.out.at(-1)).reason, "invalid_token");
  assert.equal(bad.store.read(accountFor(MCP)), null);

  // UC-3902 AC-04 — la cuenta ya tiene cinco dispositivos: el motivo llega tal
  // cual para que la extensión diga dónde desconectar uno; nada se guarda.
  const full = harness(() => [409, { code: "device_limit", message: "Too many devices." }]);
  assert.equal(await internal(full, "_adopt", { token: "spbx_anterior" }), 1);
  assert.equal(JSON.parse(full.out.at(-1)).reason, "device_limit");
  assert.equal(full.store.read(accountFor(MCP)), null);

  const other = harness(() => [409, { code: "token_already_renewed" }]);
  assert.equal(await internal(other, "_adopt", { token: "spbx_anterior" }), 1);
  assert.equal(JSON.parse(other.out.at(-1)).reason, "conflict");
});

test("_renew devuelve el token vigente y renueva cuando toca", async () => {
  const idle = harness(() => [200, {}]);
  assert.equal(await internal(idle, "_renew"), 0);
  assert.deepEqual(JSON.parse(idle.out.at(-1)), { connected: false });

  const h = harness(() => [200, TOKEN_BODY]);
  h.store.write(accountFor(MCP), {
    token: "spbx_viejo",
    expires_at: "2020-01-10T00:00:00Z",
    renew_after: "2020-01-01T00:00:00Z",
    cloud_api: "https://api.example/api",
  });
  assert.equal(await internal(h, "_renew"), 0);
  const res = JSON.parse(h.out.at(-1));
  assert.equal(res.renewed, true);
  assert.equal(res.token, "spbx_deldispositivo");
});

test("_disconnect desconecta en el panel y borra la credencial", async () => {
  const h = harness((url) => (url.endsWith("/devices/logout") ? [200, {}] : [404, {}]));
  h.store.write(accountFor(MCP), { token: "spbx_x", cloud_api: "https://api.example/api" });
  assert.equal(await internal(h, "_disconnect"), 0);
  assert.deepEqual(JSON.parse(h.out.at(-1)), { ok: true, remote: true, had_credential: true });
  assert.equal(h.store.read(accountFor(MCP)), null);
});

test("una orden interna desconocida falla con JSON", async () => {
  const h = harness(() => [200, {}]);
  assert.equal(await internal(h, "_nope"), 1);
  assert.deepEqual(JSON.parse(h.out.at(-1)), { ok: false, reason: "unknown_command" });
});
