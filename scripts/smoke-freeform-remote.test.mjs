// Pruebas de scripts/smoke-freeform-remote.mjs (UC-11012) con un MCP falso: no tocan la red.
//   node --test scripts/smoke-freeform-remote.test.mjs

import { test } from "node:test";
import assert from "node:assert/strict";
import { problems, runFlow, toolPayload } from "./smoke-freeform-remote.mjs";

const HOST = "https://mcp.example.test";
const NOTICE = "\n⚠️ From 2026-10-30, the SpecBox remote server only accepts connections with an account.";

/** Respuestas correctas de cada tool, como las da el servidor en modo contenido. */
const GOOD = {
  set_auth_token: { success: true, mode: "content_only" },
  setup_board: { board_id: "ff-1", items_content: "[]\n" },
  import_spec: { created: { us: 1, uc: 1, ac: 1 }, items_content: "[1]" },
  find_next_uc: { uc_id: "UC-001" },
  start_uc: { uc_id: "UC-001", items_content: "[2]" },
  mark_ac: { passed: true, items_content: "[3]" },
  get_uc: { uc_id: "UC-001", status: "in_progress", acceptance_criteria: [{ id: "AC-01", done: true }] },
};

/** Un MCP falso. `override` cambia la respuesta de una tool; `seen` guarda lo recibido. */
function fakeMcp({ override = {}, sse = false, seen = [] } = {}) {
  return async (url, init = {}) => {
    const body = JSON.parse(init.body);
    seen.push({ headers: new Headers(init.headers), body });
    if (body.method === "notifications/initialized") return new Response("", { status: 202 });
    let reply;
    if (body.method === "initialize") {
      reply = { jsonrpc: "2.0", id: body.id, result: { serverInfo: { version: "6.29.1" } } };
    } else {
      const name = body.params.name;
      const out = override[name] ?? { text: JSON.stringify(GOOD[name]) + NOTICE };
      reply = { jsonrpc: "2.0", id: body.id, result: { content: [{ type: "text", text: out.text }], isError: Boolean(out.isError) } };
    }
    const text = sse ? `event: message\ndata: ${JSON.stringify(reply)}\n\n` : JSON.stringify(reply);
    return new Response(text, { status: 200, headers: { "mcp-session-id": "s1" } });
  };
}

test("el recorrido completo pasa por las seis tools y no da problemas", async () => {
  for (const sse of [false, true]) {
    const seen = [];
    const result = await runFlow(HOST, { fetchImpl: fakeMcp({ sse, seen }) });
    assert.equal(result.ok, true, JSON.stringify(result.steps));
    assert.deepEqual(problems([result]), []);
    const tools = seen.filter((s) => s.body.method === "tools/call").map((s) => s.body.params.name);
    assert.deepEqual(tools, ["set_auth_token", "setup_board", "import_spec", "find_next_uc", "start_uc", "mark_ac", "get_uc"]);
  }
});

test("cada llamada lleva el items.json que devolvió la anterior", async () => {
  const seen = [];
  await runFlow(HOST, { fetchImpl: fakeMcp({ seen }) });
  const items = Object.fromEntries(
    seen.filter((s) => s.body.method === "tools/call").map((s) => [s.body.params.name, s.body.params.arguments.items_content]),
  );
  assert.equal(items.setup_board, undefined, "setup_board se llama sin items_content, como en /app-init");
  assert.equal(items.import_spec, "[]\n");
  assert.equal(items.find_next_uc, "[1]");
  assert.equal(items.mark_ac, "[2]");
  assert.equal(items.get_uc, "[3]");
});

test("una tool que falla para el recorrido y el problema dice qué tool y qué error", async () => {
  const broken = { setup_board: { text: "Error calling tool 'setup_board': 'NoneType' object has no attribute 'mkdir'", isError: true } };
  const result = await runFlow(HOST, { fetchImpl: fakeMcp({ override: broken }) });
  assert.equal(result.ok, false);
  assert.equal(result.steps.at(-1).tool, "setup_board", "no sigue después del fallo");
  assert.deepEqual(problems([result]), [`${HOST}: setup_board → Error calling tool 'setup_board': 'NoneType' object has no attribute 'mkdir'`]);
});

test("un error dentro del JSON y un estado inesperado también cuentan como fallo", async () => {
  const rejected = { set_auth_token: { text: JSON.stringify({ error: "FREEFORM_REMOTE_DISK_MODE_REJECTED" }) } };
  assert.match(problems([await runFlow(HOST, { fetchImpl: fakeMcp({ override: rejected }) })])[0], /set_auth_token → FREEFORM_REMOTE/);

  const notMarked = { get_uc: { text: JSON.stringify({ status: "in_progress", acceptance_criteria: [{ done: false }] }) } };
  assert.match(problems([await runFlow(HOST, { fetchImpl: fakeMcp({ override: notMarked }) })])[0], /get_uc → AC-01 no aparece marcado/);
});

test("con token, cada petición lo envía y ningún problema lo muestra", async () => {
  const seen = [];
  const leaky = { setup_board: { text: "fallo con el token secreto-de-prueba dentro", isError: true } };
  const result = await runFlow(HOST, { authorization: "Bearer secreto-de-prueba", fetchImpl: fakeMcp({ override: leaky, seen }) });
  assert.ok(seen.every((s) => s.headers.get("authorization") === "Bearer secreto-de-prueba"));
  assert.ok(!problems([result])[0].includes("secreto-de-prueba"));
  assert.match(problems([result])[0], /\*\*\*/);
});

test("un 401 del transporte se ve en el primer paso", async () => {
  const fetch401 = async () => new Response(JSON.stringify({ error: "token_required" }), { status: 401 });
  const result = await runFlow(HOST, { fetchImpl: fetch401 });
  assert.equal(result.steps[0].tool, "initialize");
  assert.match(result.steps[0].error, /HTTP 401/);
});

test("toolPayload quita el aviso de la gracia", () => {
  assert.deepEqual(toolPayload('{"a":1}' + NOTICE), { a: 1 });
  assert.deepEqual(toolPayload('{"a":1}'), { a: 1 });
  assert.equal(toolPayload("Error calling tool"), null);
});
