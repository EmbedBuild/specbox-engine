// UC-12602 — `specbox drift`: la puerta de desviación del CI local. La orden junta lo que cambia
// la rama (ficheros, UC, planes del orquestador, dependencias, exclusiones), llama a
// get_drift_report del MCP y termina con 1 solo si la medida drift_gate está en «block».
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { run } from "../bin/specbox.mjs";
import { addedDependencies, branchUcs, resolveBoard, runDrift } from "../lib/drift.mjs";

function write(root, rel, content) {
  mkdirSync(dirname(join(root, rel)), { recursive: true });
  writeFileSync(join(root, rel), typeof content === "string" ? content : JSON.stringify(content, null, 2));
}

function git(root, ...args) {
  return execFileSync("git", ["-C", root, ...args], { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
}

/** Un repo con main y una rama de la UC que cambia un fichero y añade una dependencia npm. */
function repoWithBranch(branch = "feat/UC-701-cobros") {
  const root = mkdtempSync(join(tmpdir(), "drift-"));
  git(root, "init", "-q", "-b", "main");
  git(root, "config", "user.email", "t@t.t");
  git(root, "config", "user.name", "t");
  write(root, ".claude/project-config.json", { boardId: "Acme/cobros", backend_type: "native" });
  write(root, ".claude/settings.json", { drift: { exclude: ["docs/**"] } });
  write(root, "package.json", { name: "x", dependencies: { lodash: "^4" } });
  write(root, "doc/plans/US-07-cobros_plan.md", "### Fase 1: Base\n**Criterios:** UC-701 AC-01\n**Ficheros:** server/a.py\n");
  write(root, "doc/plans/US-08-otra_plan.md", "### Fase 1\n**Criterios:** UC-801 AC-01\n");
  git(root, "add", "-A");
  git(root, "commit", "-q", "-m", "base");
  git(root, "checkout", "-q", "-b", branch);
  write(root, "server/a.py", "x = 1\n");
  write(root, "docs/x.md", "nota\n");
  write(root, "package.json", { name: "x", dependencies: { lodash: "^4", zod: "^3" } });
  git(root, "add", "-A");
  git(root, "commit", "-q", "-m", "feat(UC-701): cobrar");
  return root;
}

/** Un MCP falso: initialize, initialized y tools/call, que devuelve `report` y guarda lo que recibe. */
function fakeMcp(report) {
  const calls = [];
  const fetchImpl = async (_url, init) => {
    const body = JSON.parse(init.body);
    const respond = (payload, status = 200) => ({
      status,
      headers: { get: (h) => (h === "mcp-session-id" ? "s1" : h === "content-type" ? "application/json" : null) },
      text: async () => JSON.stringify(payload),
    });
    if (body.method === "initialize") return respond({ jsonrpc: "2.0", id: body.id, result: { serverInfo: {} } });
    if (body.method === "notifications/initialized") return { status: 202, headers: { get: () => null }, text: async () => "" };
    calls.push(body.params);
    return respond({ jsonrpc: "2.0", id: body.id, result: { structuredContent: report } });
  };
  return { fetchImpl, calls };
}

const REPORT = (over = {}) => ({
  success: true, board: "leído", mode: "warn", uc_ids: ["UC-701"], plans: [{ path: "doc/plans/US-07-cobros_plan.md", contract_version: 1 }],
  files: [{ path: "server/a.py", claimed_by: ["UC-701"], source: "plan" }, { path: "package.json", claimed_by: [], source: null }],
  unclaimed: ["package.json"], exclude: ["docs/**"], excluded: ["docs/x.md"],
  dependencies: { added: [{ ecosystem: "npm", name: "zod", manifest: "package.json" }], undeclared: [{ ecosystem: "npm", name: "zod", manifest: "package.json" }] },
  closed_touches: [], closed_without_files: 0, ok: false, ...over,
});

const deps = (mcp, out, extra = {}) => ({
  print: (l) => out.push(l),
  env: {},
  fetchImpl: mcp.fetchImpl,
  headersFor: async () => ({ Authorization: "Bearer t" }),
  ...extra,
});

test("AC-01/AC-02/AC-03/AC-04: junta la rama y enseña cada fichero, las dependencias y las exclusiones", async () => {
  const root = repoWithBranch();
  try {
    const mcp = fakeMcp(REPORT());
    const out = [];
    const summary = join(root, "resumen.txt");
    const code = await runDrift({ root, base: "main", summaryFile: summary }, deps(mcp, out));
    assert.equal(code, 0); // «warn»: enseña el informe y termina con 0 (AC-08)
    const [call] = mcp.calls;
    assert.equal(call.name, "get_drift_report");
    assert.deepEqual(call.arguments.files.sort(), ["docs/x.md", "package.json", "server/a.py"]);
    assert.deepEqual(call.arguments.uc_ids, ["UC-701"]);
    assert.deepEqual(Object.keys(call.arguments.plan_contents), ["doc/plans/US-07-cobros_plan.md"]); // solo el de su UC
    assert.deepEqual(call.arguments.dependencies_added, [{ ecosystem: "npm", name: "zod", manifest: "package.json" }]);
    assert.deepEqual(call.arguments.exclude, ["docs/**"]);
    assert.equal(call.arguments.board_id, "Acme/cobros");
    const text = out.join("\n");
    assert.match(text, /server\/a\.py — UC-701 \(plan\)/);
    assert.match(text, /package\.json — sin UC/);
    assert.match(text, /Exclusiones del proyecto \(specbox\.drift\.exclude\): docs\/\*\*/);
    assert.match(text, /Sin declarar en el plan .*npm:zod/);
    assert.match(readFileSync(summary, "utf8"), /^aviso: 1 sin UC, 1 dependencia/);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("AC-01/AC-08: en «block» con ficheros sin UC termina con 1; sin desvíos, con 0", async () => {
  const root = repoWithBranch();
  try {
    const out = [];
    assert.equal(await runDrift({ root, base: "main" }, deps(fakeMcp(REPORT({ mode: "block" })), out)), 1);
    assert.equal(await runDrift({ root, base: "main" }, deps(fakeMcp(REPORT({ mode: "block", ok: true, unclaimed: [], dependencies: { added: [], undeclared: [] } })), [])), 0);
    // Por la CLI, con --json.
    const json = [];
    const code = await run(["drift", "--base", "main", "--json", "--project", root], {
      print: (l) => json.push(l), env: {}, fetchImpl: fakeMcp(REPORT({ mode: "block" })).fetchImpl,
      headersFor: async () => ({ Authorization: "Bearer t" }), store: { read: () => null, kind: "memory" },
    });
    assert.equal(code, 1);
    assert.equal(JSON.parse(json.at(-1)).state, "block");
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("AC-07: una rama sin UC por diseño queda fuera por su prefijo, configurable", async () => {
  const root = repoWithBranch("dependabot/npm/zod-3");
  try {
    const out = [];
    const mcp = fakeMcp(REPORT());
    assert.equal(await runDrift({ root, base: "main" }, deps(mcp, out)), 0);
    assert.equal(mcp.calls.length, 0);
    assert.match(out.join("\n"), /no lleva UC por diseño \(prefijo «dependabot\/»/);
    write(root, ".claude/settings.json", { drift: { skip_branch_prefixes: ["bots/"] } });
    const again = fakeMcp(REPORT());
    await runDrift({ root, base: "main" }, deps(again, []));
    assert.equal(again.calls.length, 1); // con otros prefijos, «dependabot/» ya no se salta
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("AC-08: sin tablero, sin identidad o sin MCP no comprueba, lo dice y termina con 0", async () => {
  const root = repoWithBranch();
  try {
    const out = [];
    assert.equal(await runDrift({ root, base: "main" }, deps(fakeMcp(REPORT()), out, { headersFor: async () => ({}) })), 0);
    assert.match(out.at(-1), /specbox login/);
    const down = { fetchImpl: async () => { throw new Error("ECONNREFUSED"); } };
    assert.equal(await runDrift({ root, base: "main" }, deps(down, out)), 0);
    assert.match(out.at(-1), /no respondió/);
    rmSync(join(root, ".claude", "project-config.json"));
    assert.equal(await runDrift({ root, base: "main" }, deps(fakeMcp(REPORT()), out)), 0);
    assert.match(out.at(-1), /no tiene tablero/);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("AC-06: en un satélite, el tablero y los planes son los del orquestador, no los de la copia", async () => {
  const orch = mkdtempSync(join(tmpdir(), "drift-orch-"));
  const root = repoWithBranch();
  try {
    write(orch, ".claude/project-config.json", { boardId: "Acme/orquestador", backend_type: "native" });
    write(orch, ".claude/settings.local.json", { multirepo: { enabled: true, role: "orchestrator", satellites: { motor: { path: root } } } });
    write(orch, "doc/plans/US-07-real_plan.md", "### Fase 1\n**Criterios:** UC-701 AC-01\n**Ficheros:** server/a.py\n");
    write(root, ".claude/settings.local.json", { multirepo: { enabled: true, role: "satellite", orchestrator: orch } });
    const board = resolveBoard(root);
    assert.equal(board.boardId, "Acme/orquestador");
    const mcp = fakeMcp(REPORT());
    const out = [];
    await runDrift({ root, base: "main" }, deps(mcp, out));
    const args = mcp.calls[0].arguments;
    assert.equal(args.board_id, "Acme/orquestador");
    assert.deepEqual(Object.keys(args.plan_contents), ["doc/plans/US-07-real_plan.md"]); // no la copia del satélite
    assert.equal(args.satellite, "motor");
    assert.match(out.join("\n"), /Tablero y planes del orquestador/);
    write(root, ".claude/settings.local.json", { multirepo: { enabled: true, role: "satellite", orchestrator: "../no-existe" } });
    const missing = [];
    assert.equal(await runDrift({ root, base: "main" }, deps(fakeMcp(REPORT()), missing)), 0);
    assert.match(missing.at(-1), /orquestador .* no está en este equipo/);
  } finally {
    rmSync(root, { recursive: true, force: true });
    rmSync(orch, { recursive: true, force: true });
  }
});

test("las UC salen de los commits y de la rama; sin ninguna, del marcador; y las dependencias de cada manifiesto", () => {
  const root = repoWithBranch("feat/sin-uc");
  try {
    git(root, "commit", "-q", "--allow-empty", "-m", "fix(UC-702): otra cosa");
    assert.deepEqual(branchUcs(root, "main", "feat/UC-703-x").ucs.sort(), ["UC-701", "UC-702", "UC-703"]);
    const bare = mkdtempSync(join(tmpdir(), "drift-bare-"));
    git(bare, "init", "-q", "-b", "main");
    write(bare, ".quality/active_uc.json", { uc_id: "UC-9" });
    assert.deepEqual(branchUcs(bare, "HEAD", "main"), { ucs: ["UC-9"], source: "marcador" });
    rmSync(bare, { recursive: true, force: true });

    write(root, "pyproject.toml", '[project]\nname = "x"\ndependencies = [\n  "httpx>=0.27",\n  "Rapid_Fuzz[speed]",\n]\n[dependency-groups]\ndev = ["pytest"]\n');
    write(root, "go.mod", "module x\n\nrequire (\n\tgithub.com/a/b v1.0.0\n)\n");
    write(root, "pubspec.yaml", "name: x\ndependencies:\n  http: ^1.0.0\ndev_dependencies:\n  test: any\n");
    git(root, "add", "-A");
    git(root, "commit", "-q", "-m", "deps");
    const added = addedDependencies(root, "main", ["pyproject.toml", "go.mod", "pubspec.yaml", "package.json"]);
    assert.deepEqual(added.map((d) => `${d.ecosystem}:${d.name}`).sort(), [
      "go:github.com/a/b", "npm:zod", "pub:http", "pub:test", "pypi:Rapid_Fuzz", "pypi:httpx", "pypi:pytest",
    ]);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});
