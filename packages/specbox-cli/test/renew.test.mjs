// UC-3904 AC-03 — renovación automática desde 14 días antes de caducar, sin
// que dos sesiones renueven a la vez y sin perder el token si falla la red.
import assert from "node:assert/strict";
import { mkdtempSync, utimesSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { acquireLock, credentialFromResponse, renewCredential, renewDue } from "../lib/renew.mjs";
import { fileStore } from "../lib/store.mjs";

const ACCOUNT = "https://mcp.example/mcp";
const DAY = 86_400_000;
const now = Date.parse("2026-12-20T10:00:00Z");

function current(extra = {}) {
  return {
    token: "spbx_viejo",
    token_id: "old",
    expires_at: "2026-12-28T10:00:00.000Z",
    renew_after: "2026-12-14T10:00:00.000Z",
    device_name: "Mac",
    cloud_api: "https://api.example/api",
    ...extra,
  };
}

function serverReply(status, body = {}) {
  const calls = [];
  const fetchImpl = async (url, init) => {
    calls.push({ url, init });
    return { status, json: async () => body };
  };
  return { fetchImpl, calls };
}

const RENEWED = {
  access_token: "spbx_nuevo",
  token_id: "new",
  expires_at: "2027-03-20T10:00:00.000Z",
  renew_after: "2027-03-06T10:00:00.000Z",
  developer: { developer_id: "jesus", display_name: "Jesús", handle: "jesus" },
  device: { device_id: "d", device_name: "Mac", client: "claude-code" },
};

test("se renueva a partir de renew_after (o 14 días antes de caducar) y nunca si no caduca", () => {
  assert.equal(renewDue(current(), Date.parse("2026-12-13T10:00:00Z")), false);
  assert.equal(renewDue(current(), Date.parse("2026-12-14T10:00:00Z")), true);
  assert.equal(renewDue(current({ renew_after: null }), Date.parse("2026-12-14T10:00:01Z")), true);
  assert.equal(renewDue(current({ renew_after: null }), Date.parse("2026-12-14T09:59:59Z")), false);
  assert.equal(renewDue({ token: "x", expires_at: null }, now), false);
});

test("renueva con el token vigente y guarda el nuevo", async () => {
  const home = mkdtempSync(join(tmpdir(), "specbox-renew-"));
  const store = fileStore(home);
  store.write(ACCOUNT, current());
  const { fetchImpl, calls } = serverReply(200, RENEWED);
  const next = await renewCredential({ store, account: ACCOUNT, credential: current(), fetchImpl, lockDir: home });
  assert.equal(next.token, "spbx_nuevo");
  assert.equal(store.read(ACCOUNT).token, "spbx_nuevo");
  assert.equal(calls[0].url, "https://api.example/api/devices/renew");
  assert.equal(calls[0].init.headers.authorization, "Bearer spbx_viejo");
});

test("si otra sesión ya renovó (409 o credencial distinta), usa la guardada", async () => {
  const home = mkdtempSync(join(tmpdir(), "specbox-renew-"));
  const store = fileStore(home);
  store.write(ACCOUNT, credentialFromResponse(RENEWED, "https://api.example/api"));
  const { fetchImpl, calls } = serverReply(200, RENEWED);
  const got = await renewCredential({ store, account: ACCOUNT, credential: current(), fetchImpl, lockDir: home });
  assert.equal(got.token, "spbx_nuevo");
  assert.equal(calls.length, 0); // ni siquiera llama

  store.write(ACCOUNT, current());
  const conflict = serverReply(409, { code: "token_already_renewed" });
  const after = await renewCredential({ store, account: ACCOUNT, credential: current(), fetchImpl: conflict.fetchImpl, lockDir: home });
  assert.equal(after.token, "spbx_viejo");
});

test("un fallo de red o un 401 no rompe nada: sigue con el token vigente", async () => {
  const home = mkdtempSync(join(tmpdir(), "specbox-renew-"));
  const store = fileStore(home);
  store.write(ACCOUNT, current());
  const offline = async () => {
    throw new Error("ECONNREFUSED");
  };
  assert.equal((await renewCredential({ store, account: ACCOUNT, credential: current(), fetchImpl: offline, lockDir: home })).token, "spbx_viejo");
  const denied = serverReply(401, { code: "invalid_token" });
  assert.equal((await renewCredential({ store, account: ACCOUNT, credential: current(), fetchImpl: denied.fetchImpl, lockDir: home })).token, "spbx_viejo");
});

test("con el cerrojo tomado por otra sesión no renueva; un cerrojo abandonado se recupera", async () => {
  const home = mkdtempSync(join(tmpdir(), "specbox-renew-"));
  const store = fileStore(home);
  store.write(ACCOUNT, current());
  const release = acquireLock(home);
  assert.ok(release);
  const { fetchImpl, calls } = serverReply(200, RENEWED);
  const busy = await renewCredential({ store, account: ACCOUNT, credential: current(), fetchImpl, lockDir: home });
  assert.equal(busy.token, "spbx_viejo");
  assert.equal(calls.length, 0);
  release();

  writeFileSync(join(home, "renew.lock"), "");
  const old = new Date(Date.now() - 2 * 60_000);
  utimesSync(join(home, "renew.lock"), old, old);
  const recovered = await renewCredential({ store, account: ACCOUNT, credential: current(), fetchImpl, lockDir: home });
  assert.equal(recovered.token, "spbx_nuevo");
});

test("la credencial nueva conserva la API del panel con la que se obtuvo", () => {
  const cred = credentialFromResponse(RENEWED, "https://api.example/api");
  assert.equal(cred.cloud_api, "https://api.example/api");
  assert.equal(cred.device_name, "Mac");
  assert.equal(Date.parse(cred.expires_at) - Date.parse(cred.renew_after), 14 * DAY);
});
