#!/usr/bin/env node
// smoke-freeform-remote.mjs — el flujo FreeForm funciona en el MCP de producción (UC-11012).
//
// Uso:
//   node scripts/smoke-freeform-remote.mjs                       sin token (solo hasta el fin de la gracia de UC-3901)
//   node scripts/smoke-freeform-remote.mjs --with-device-token   con el token de este ordenador
//                                                                (ayudante ~/.specbox/bin/mcp-headers.mjs)
//   node scripts/smoke-freeform-remote.mjs --json
//   Sale con 1 si una tool falla en algún nombre del MCP.
//
// En cada nombre abre una sesión FreeForm sin disco (modo contenido, UC-3801) y recorre lo que hace un
// proyecto nuevo: setup_board, import_spec, find_next_uc, start_uc, mark_ac y get_uc, pasando el
// items.json de una llamada a la siguiente como hace el cliente. El servidor no guarda nada.
// Es la comprobación que faltó para que setup_board (UC-11004) no llegara roto a un usuario.
// El token nunca se imprime.

import { fileURLToPath } from "node:url";
import { deviceAuthorization, MCP_HOSTS } from "./check-mcp-hosts.mjs";

const BOARD = "humo-freeform";

const SPEC = {
  user_stories: [
    {
      us_id: "US-01",
      name: "Prueba de humo de FreeForm",
      hours: 1,
      screens: "",
      description: "Board de prueba: el servidor no lo guarda",
      use_cases: [
        {
          uc_id: "UC-001",
          name: "Registrar una solicitud",
          actor: "Cliente",
          hours: 1,
          screens: "",
          acceptance_criteria: ["La solicitud aparece en la lista con su fecha"],
        },
      ],
    },
  ],
};

/** El JSON de la respuesta de una tool, sin el aviso que el servidor añade detrás en la gracia. */
export function toolPayload(text) {
  const notice = text.indexOf("\n⚠");
  try {
    return JSON.parse(notice >= 0 ? text.slice(0, notice) : text);
  } catch {
    return null;
  }
}

function redact(text, authorization) {
  const secret = authorization?.replace(/^Bearer\s+/i, "");
  return secret ? String(text).replaceAll(secret, "***") : String(text);
}

/** Una sesión MCP por HTTP: guarda el mcp-session-id y entiende respuestas JSON o SSE. */
class Session {
  constructor(host, authorization, fetchImpl) {
    this.url = `${host}/mcp`;
    this.authorization = authorization;
    this.fetchImpl = fetchImpl;
    this.id = null;
    this.nextId = 1;
  }

  async send(method, params, { notification = false } = {}) {
    const headers = { "Content-Type": "application/json", Accept: "application/json, text/event-stream" };
    if (this.authorization) headers.Authorization = this.authorization;
    if (this.id) headers["mcp-session-id"] = this.id;
    const body = notification ? { jsonrpc: "2.0", method, params } : { jsonrpc: "2.0", id: this.nextId++, method, params };
    const res = await this.fetchImpl(this.url, { method: "POST", headers, body: JSON.stringify(body) });
    this.id = res.headers.get("mcp-session-id") ?? this.id;
    const text = await res.text();
    if (notification) return null;
    if (res.status !== 200) throw new Error(`HTTP ${res.status} ${text.slice(0, 160)}`);
    const data = text.split("\n").find((line) => line.startsWith("data:"));
    return JSON.parse(data ? data.slice(5) : text);
  }

  /** Llama a una tool: devuelve su JSON o lanza con el error que dio. */
  async tool(name, args) {
    const reply = await this.send("tools/call", { name, arguments: args });
    if (reply.error) throw new Error(reply.error.message ?? JSON.stringify(reply.error));
    const text = (reply.result?.content ?? []).map((c) => c.text ?? "").join("\n");
    if (reply.result?.isError) throw new Error(text.slice(0, 300));
    const payload = toolPayload(text);
    if (!payload) throw new Error(`respuesta que no es JSON: ${text.slice(0, 160)}`);
    if (payload.error) throw new Error(String(payload.error).slice(0, 300));
    return payload;
  }
}

/** Recorre el flujo en un nombre. Se para en el primer paso que falla: los siguientes dependen de él. */
export async function runFlow(host, { authorization = null, fetchImpl = fetch } = {}) {
  const session = new Session(host, authorization, fetchImpl);
  const steps = [];
  let items = "";

  const step = async (name, fn) => {
    const started = Date.now();
    try {
      await fn();
      steps.push({ tool: name, ok: true, ms: Date.now() - started });
      return true;
    } catch (err) {
      steps.push({ tool: name, ok: false, ms: Date.now() - started, error: redact(err.cause?.code ?? err.message, authorization) });
      return false;
    }
  };
  const keep = (payload) => {
    if (typeof payload.items_content !== "string") throw new Error("no devuelve items_content");
    items = payload.items_content;
  };

  const flow = [
    ["initialize", async () => {
      await session.send("initialize", {
        protocolVersion: "2025-06-18",
        capabilities: {},
        clientInfo: { name: "smoke-freeform-remote", version: "1" },
      });
      await session.send("notifications/initialized", {}, { notification: true });
    }],
    ["set_auth_token", () => session.tool("set_auth_token", { api_key: "freeform", token: "", backend_type: "freeform" })],
    ["setup_board", async () => keep(await session.tool("setup_board", { board_name: BOARD }))],
    ["import_spec", async () => keep(await session.tool("import_spec", { board_id: BOARD, spec: SPEC, items_content: items }))],
    ["find_next_uc", async () => {
      const next = await session.tool("find_next_uc", { board_id: BOARD, items_content: items });
      if (next.uc_id !== "UC-001") throw new Error(`propone ${next.uc_id ?? "ninguna"} en vez de UC-001`);
    }],
    ["start_uc", async () => keep(await session.tool("start_uc", { board_id: BOARD, uc_id: "UC-001", items_content: items }))],
    ["mark_ac", async () => keep(await session.tool("mark_ac", {
      board_id: BOARD, uc_id: "UC-001", ac_id: "AC-01", passed: true, evidence: "prueba de humo", items_content: items,
    }))],
    ["get_uc", async () => {
      const uc = await session.tool("get_uc", { board_id: BOARD, uc_id: "UC-001", items_content: items });
      if (uc.status !== "in_progress") throw new Error(`estado ${uc.status} en vez de in_progress`);
      if (!uc.acceptance_criteria?.[0]?.done) throw new Error("AC-01 no aparece marcado");
    }],
  ];
  for (const [name, fn] of flow) {
    if (!(await step(name, fn))) break;
  }
  return { host, ok: steps.length === flow.length && steps.every((s) => s.ok), steps };
}

/** Los fallos de un conjunto de recorridos (vacío = todo responde). Pura. */
export function problems(results) {
  return results.flatMap((r) => r.steps.filter((s) => !s.ok).map((s) => `${r.host}: ${s.tool} → ${s.error}`));
}

async function main(argv) {
  const withToken = argv.includes("--with-device-token");
  const authorization = withToken ? deviceAuthorization() : null;
  if (withToken && !authorization) {
    console.error("✖ --with-device-token: este ordenador no tiene token de dispositivo (specbox login).");
    return 1;
  }
  const results = [];
  for (const host of MCP_HOSTS) results.push(await runFlow(host, { authorization }));
  const found = problems(results);

  if (argv.includes("--json")) {
    console.log(JSON.stringify({ ok: found.length === 0, problems: found, results }, null, 2));
  } else {
    for (const r of results) {
      console.log(`${r.host}\n  ${r.steps.map((s) => `${s.tool} ${s.ok ? "ok" : "FALLO"} ${s.ms} ms`).join(" · ")}`);
    }
    for (const p of found) console.log(`✖ ${p}`);
    console.log(found.length ? "\nEl flujo FreeForm FALLA en producción." : "\n✓ El flujo FreeForm responde en los dos nombres.");
    if (!withToken) console.log("  (sin --with-device-token: desde el fin de la gracia, el MCP rechaza la sesión sin token)");
  }
  return found.length ? 1 : 0;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) process.exitCode = await main(process.argv.slice(2));
