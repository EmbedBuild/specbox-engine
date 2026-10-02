// Pruebas de scripts/check-mcp-hosts.mjs (UC-5101 AC-02) con un fetch falso: no tocan la red.
//   node --test scripts/check-mcp-hosts.test.mjs

import { test } from "node:test";
import assert from "node:assert/strict";
import { compareHosts, MCP_HOSTS, probeHost } from "./check-mcp-hosts.mjs";

const NEW = "https://mcp.example.test";
const OLD = "https://old-mcp.example.test";

/** Un servidor falso: versión, qué hace sin token y qué token es válido. */
function fakeServer({ version = "6.18.0", noTokenStatus = 200, validToken = "Bearer bueno" } = {}) {
  return async (url, init = {}) => {
    const headers = new Headers(init.headers ?? {});
    if (url.endsWith("/health")) return Response.json({ status: "ok", version });
    const auth = headers.get("authorization");
    let status = auth ? (auth === validToken ? 200 : 401) : noTokenStatus;
    const out = new Headers(status === 200 ? { "mcp-session-id": "s1" } : {});
    return new Response(JSON.stringify(status === 200 ? { result: {} } : { error: auth ? "invalid_token" : "token_required" }), {
      status,
      headers: out,
    });
  };
}

async function probeBoth(fetches, authorization = null) {
  return [await probeHost(NEW, { fetchImpl: fetches[0], authorization }), await probeHost(OLD, { fetchImpl: fetches[1], authorization })];
}

test("el nombre nuevo va primero y el antiguo sigue en la lista", () => {
  assert.deepEqual(MCP_HOSTS, ["https://mcp.specbox.build", "https://mcp-specbox-engine.jpsdeveloper.com"]);
});

test("dos nombres del mismo servidor responden igual, en la gracia y después", async () => {
  for (const noTokenStatus of [200, 401]) {
    const results = await probeBoth([fakeServer({ noTokenStatus }), fakeServer({ noTokenStatus })], "Bearer bueno");
    assert.deepEqual(compareHosts(results), [], `sin token = ${noTokenStatus}`);
    assert.equal(results[0].withToken.session, true);
  }
});

test("versiones distintas: un nombre apunta a otro despliegue", async () => {
  const problems = compareHosts(await probeBoth([fakeServer({ version: "6.18.0" }), fakeServer({ version: "6.17.1" })]));
  assert.match(problems.join("\n"), /versiones distintas/);
});

test("sin token, uno acepta y el otro rechaza: no responden igual", async () => {
  const problems = compareHosts(await probeBoth([fakeServer({ noTokenStatus: 401 }), fakeServer({ noTokenStatus: 200 })]));
  assert.match(problems.join("\n"), /sin token responden distinto/);
});

test("un token inválido que entra es un fallo aunque los dos coincidan", async () => {
  const lax = async (url, init) =>
    url.endsWith("/health") ? Response.json({ status: "ok", version: "6.18.0" }) : new Response("{}", { status: 200, headers: { "mcp-session-id": "s" } });
  const problems = compareHosts(await probeBoth([lax, lax]));
  assert.equal(problems.filter((p) => /token inválido no se rechaza/.test(p)).length, 2);
});

test("con token: si un nombre no abre sesión, falla", async () => {
  const problems = compareHosts(await probeBoth([fakeServer(), fakeServer({ validToken: "Bearer otro" })], "Bearer bueno"));
  assert.match(problems.join("\n"), new RegExp(`${OLD.replace(/\./g, "\\.")}: con token no abre sesión`));
});

test("un nombre que no responde se informa, no rompe la comprobación", async () => {
  const down = async () => {
    throw Object.assign(new Error("fetch failed"), { cause: { code: "ENOTFOUND" } });
  };
  const problems = compareHosts(await probeBoth([fakeServer(), down]));
  assert.match(problems.join("\n"), /\/health no responde «ok» \(ENOTFOUND\)/);
});
