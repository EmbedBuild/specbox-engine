// UC-3904 AC-02 — el token queda en el almacén seguro del sistema y nunca
// viaja como argumento de un proceso.
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, statSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { SERVICE, createStore, decode, encode, fileStore } from "../lib/store.mjs";

const ACCOUNT = "https://mcp.example/mcp";
const CRED = { token: "spbx_secretoSecreto", expires_at: "2026-12-28T10:00:00.000Z", device_name: "Jesús · Mac · Claude Code" };

function recorder(responses = {}) {
  const calls = [];
  const run = (cmd, args, opts = {}) => {
    calls.push({ cmd, args, opts });
    const key = `${cmd} ${args[0]}`;
    const res = typeof responses[key] === "function" ? responses[key](opts) : responses[key];
    return { status: 0, stdout: "", stderr: "", error: null, ...res };
  };
  return { run, calls };
}

test("la credencial se codifica en base64 (sin comillas ni espacios que escapar)", () => {
  const encoded = encode(CRED);
  assert.match(encoded, /^[A-Za-z0-9+/=]+$/);
  assert.deepEqual(decode(encoded), CRED);
  assert.equal(decode(""), null);
  assert.equal(decode("no-es-base64-json"), null);
});

test("macOS: escribe en el Llavero por stdin (security -i) y el token no aparece en ningún argumento", () => {
  const { run, calls } = recorder({ "security find-generic-password": { stdout: `${encode(CRED)}\n` } });
  const store = createStore({ platform: "darwin", run, home: "/unused" });
  store.write(ACCOUNT, CRED);
  assert.equal(store.kind, "keychain");
  const write = calls[0];
  assert.deepEqual(write.args, ["-i"]);
  assert.match(write.opts.input, new RegExp(`^add-generic-password -U -s "${SERVICE}" -a "${ACCOUNT}" -w [A-Za-z0-9+/=]+\\n$`));
  assert.deepEqual(store.read(ACCOUNT), CRED);
  for (const call of calls) assert.ok(!call.args.join(" ").includes(CRED.token));
});

test("macOS: una credencial que no existe (salida 44) es null", () => {
  const { run } = recorder({ "security find-generic-password": { status: 44 } });
  assert.equal(createStore({ platform: "darwin", run, home: "/unused" }).read(ACCOUNT), null);
});

test("Linux: Secret Service por stdin; si no está (ENOENT), cae al fichero 0600", () => {
  const home = mkdtempSync(join(tmpdir(), "specbox-store-"));
  const { run, calls } = recorder({
    "secret-tool store": { error: Object.assign(new Error("nope"), { code: "ENOENT" }), status: null },
    "secret-tool lookup": { error: Object.assign(new Error("nope"), { code: "ENOENT" }), status: null },
  });
  const store = createStore({ platform: "linux", run, home });
  store.write(ACCOUNT, CRED);
  assert.equal(store.kind, "file");
  assert.equal(calls[0].opts.input, encode(CRED));
  assert.deepEqual(store.read(ACCOUNT), CRED);
  const file = join(home, "credentials.json");
  if (process.platform !== "win32") assert.equal(statSync(file).mode & 0o777, 0o600);
  assert.ok(!readFileSync(file, "utf8").includes(CRED.token)); // en base64, nunca en claro
  store.remove(ACCOUNT);
  assert.equal(store.read(ACCOUNT), null);
});

test("Linux con Secret Service: la credencial se guarda allí", () => {
  const saved = {};
  const { run } = recorder({
    "secret-tool store": (opts) => {
      saved.value = opts.input;
      return {};
    },
    "secret-tool lookup": () => ({ stdout: saved.value ?? "", status: saved.value ? 0 : 1 }),
  });
  const store = createStore({ platform: "linux", run, home: mkdtempSync(join(tmpdir(), "specbox-store-")) });
  store.write(ACCOUNT, CRED);
  assert.equal(store.kind, "secret-service");
  assert.deepEqual(store.read(ACCOUNT), CRED);
});

test("Windows: DPAPI del usuario con PowerShell, el secreto por stdin y el fichero por variable de entorno", () => {
  const { run, calls } = recorder();
  const store = createStore({ platform: "win32", run, home: mkdtempSync(join(tmpdir(), "specbox-store-")) });
  store.write(ACCOUNT, CRED);
  const call = calls[0];
  assert.equal(call.cmd, "powershell");
  assert.ok(call.args.at(-1).includes("ProtectedData]::Protect"));
  assert.equal(call.opts.input, encode(CRED));
  assert.match(call.opts.env.SPECBOX_CRED_FILE, /credentials[\\/][0-9a-f]{32}\.dpapi$/);
  assert.ok(!call.args.join(" ").includes(CRED.token));
});

test("el fichero guarda una credencial por servidor", () => {
  const store = fileStore(mkdtempSync(join(tmpdir(), "specbox-store-")));
  store.write("https://a/mcp", { token: "a" });
  store.write("https://b/mcp", { token: "b" });
  assert.equal(store.read("https://a/mcp").token, "a");
  assert.equal(store.read("https://b/mcp").token, "b");
});
