#!/usr/bin/env node
// check-mcp-hosts.mjs — los dos nombres del servidor MCP responden igual (UC-5101 AC-02).
//
// Uso:
//   node scripts/check-mcp-hosts.mjs                       sin token (lo que corre en CI cada semana)
//   node scripts/check-mcp-hosts.mjs --with-device-token   además, sesión con el token de este
//                                                          ordenador (ayudante ~/.specbox/bin/mcp-headers.mjs)
//   node scripts/check-mcp-hosts.mjs --json
//   Sale con 1 si los nombres no responden igual o algo esperado falla.
//
// Para cada nombre: /health (estado y versión), `initialize` con un token inválido, sin token
// y, si hay token, con token. Se exige:
//   - salud «ok» y la misma versión en todos;
//   - un token inválido se rechaza (401) en todos;
//   - sin token, la misma respuesta en todos: 200 durante la gracia, 401 después (UC-3901);
//   - con token, sesión abierta (200 y mcp-session-id) en todos.
// El token nunca se imprime.

import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

/** El nombre nuevo primero; el antiguo sigue respondiendo sin fecha de retirada (UC-5101 AC-02). */
export const MCP_HOSTS = ["https://mcp.specbox.build", "https://mcp-specbox-engine.jpsdeveloper.com"];

const INITIALIZE = JSON.stringify({
  jsonrpc: "2.0",
  id: 1,
  method: "initialize",
  params: { protocolVersion: "2025-06-18", capabilities: {}, clientInfo: { name: "check-mcp-hosts", version: "1" } },
});

async function initialize(host, authorization, fetchImpl) {
  const headers = { "Content-Type": "application/json", Accept: "application/json, text/event-stream" };
  if (authorization) headers.Authorization = authorization;
  try {
    const res = await fetchImpl(`${host}/mcp`, { method: "POST", headers, body: INITIALIZE });
    let error = null;
    if (res.status >= 400) {
      try {
        error = (await res.json())?.error ?? null;
      } catch {
        // cuerpo no JSON: basta con el estado
      }
    }
    return { status: res.status, session: Boolean(res.headers.get("mcp-session-id")), error };
  } catch (err) {
    return { status: null, session: false, error: err.cause?.code ?? err.message };
  }
}

/** Lo que responde un nombre. `authorization` es la cabecera completa, o null si no hay token. */
export async function probeHost(host, { authorization = null, fetchImpl = fetch } = {}) {
  let health;
  try {
    const res = await fetchImpl(`${host}/health`);
    const body = await res.json();
    health = { status: res.status, ok: body?.status === "ok", version: body?.version ?? null };
  } catch (err) {
    health = { status: null, ok: false, version: null, error: err.cause?.code ?? err.message };
  }
  return {
    host,
    health,
    invalidToken: await initialize(host, "Bearer token-invalido-check-mcp-hosts", fetchImpl),
    noToken: await initialize(host, null, fetchImpl),
    withToken: authorization ? await initialize(host, authorization, fetchImpl) : null,
  };
}

/** Los problemas de un conjunto de respuestas (vacío = los nombres responden igual). Pura. */
export function compareHosts(results) {
  const problems = [];
  for (const r of results) {
    if (!r.health.ok) problems.push(`${r.host}: /health no responde «ok» (${r.health.status ?? r.health.error})`);
    if (r.invalidToken.status !== 401) {
      problems.push(`${r.host}: un token inválido no se rechaza (${r.invalidToken.status ?? r.invalidToken.error})`);
    }
    if (r.withToken && !(r.withToken.status === 200 && r.withToken.session)) {
      problems.push(`${r.host}: con token no abre sesión (${r.withToken.status ?? r.withToken.error})`);
    }
  }
  const versions = new Set(results.map((r) => r.health.version));
  if (versions.size > 1) problems.push(`versiones distintas: ${results.map((r) => `${r.host} ${r.health.version}`).join(", ")}`);
  const noToken = new Set(results.map((r) => `${r.noToken.status}/${r.noToken.session}`));
  if (noToken.size > 1) {
    problems.push(`sin token responden distinto: ${results.map((r) => `${r.host} ${r.noToken.status}`).join(", ")}`);
  }
  return problems;
}

/**
 * La cabecera Authorization del ayudante que usa Claude Code en este ordenador, o null.
 * Se pregunta por cada nombre hasta que uno tenga credencial (antes de UC-5102 la credencial
 * solo existe para el nombre antiguo).
 */
export function deviceAuthorization({
  helper = join(homedir(), ".specbox", "bin", "mcp-headers.mjs"),
  hosts = MCP_HOSTS,
  run = spawnSync,
} = {}) {
  if (!existsSync(helper)) return null;
  for (const host of hosts) {
    const res = run(process.execPath, [helper], {
      encoding: "utf8",
      timeout: 15_000,
      env: { ...process.env, CLAUDE_CODE_MCP_SERVER_URL: `${host}/mcp` },
    });
    try {
      const auth = JSON.parse(res.stdout || "{}").Authorization;
      if (auth) return auth;
    } catch {
      // salida inesperada del ayudante: se prueba el siguiente nombre
    }
  }
  return null;
}

function cell(r) {
  return r ? `${r.status ?? r.error}${r.session ? " +sesión" : ""}` : "—";
}

async function main(argv) {
  const withToken = argv.includes("--with-device-token");
  const authorization = withToken ? deviceAuthorization() : null;
  if (withToken && !authorization) {
    console.error("✖ --with-device-token: este ordenador no tiene token de dispositivo (specbox login).");
    return 1;
  }
  const results = [];
  for (const host of MCP_HOSTS) results.push(await probeHost(host, { authorization }));
  const problems = compareHosts(results);

  if (argv.includes("--json")) {
    console.log(JSON.stringify({ ok: problems.length === 0, problems, results }, null, 2));
  } else {
    for (const r of results) {
      console.log(
        `${r.host}\n  salud ${r.health.ok ? "ok" : "MAL"} ${r.health.version ?? ""} · token inválido ${cell(r.invalidToken)}` +
          ` · sin token ${cell(r.noToken)} · con token ${cell(r.withToken)}`,
      );
    }
    for (const p of problems) console.log(`✖ ${p}`);
    console.log(problems.length ? "\nLos nombres NO responden igual." : "\n✓ Los dos nombres responden igual.");
    if (!withToken) console.log("  (sin --with-device-token no se prueba la sesión con token)");
  }
  return problems.length ? 1 : 0;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) process.exitCode = await main(process.argv.slice(2));
