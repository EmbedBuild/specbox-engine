/**
 * `specbox drift` — la puerta de desviación del CI local (US-126 · UC-12602).
 *
 * Junta lo que cambia la rama frente a su base: los ficheros (sin los borrados), las UC de la rama
 * (asuntos de los commits y nombre de la rama; si no hay ninguna, el marcador de UC activa), los
 * planes de esas UC leídos del orquestador (en multirepo, no de una copia en el satélite), las
 * dependencias que añaden sus manifiestos y las exclusiones del proyecto. Se lo pasa a la tool
 * `get_drift_report` del MCP con la identidad del dispositivo (la de `specbox login`) y enseña el
 * informe: cada fichero con la UC que lo reclama o «sin UC», las dependencias sin declarar, lo
 * excluido y las UC cerradas que toca.
 *
 * Termina con 1 solo si la medida `drift_gate` del tablero está en «block» y hay ficheros sin UC o
 * dependencias sin declarar; en «warn» enseña el informe y termina con 0. Sin tablero, sin
 * identidad o sin respuesta del MCP no comprueba nada, lo dice y termina con 0.
 */
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { basename, isAbsolute, join, resolve } from "node:path";

/** Prefijos de rama que no llevan UC por diseño (dependencias, documentación, CI, versiones). */
export const DEFAULT_SKIP_PREFIXES = ["dependabot/", "deps/", "docs/", "ci/", "release/"];
const UC_ID = /\bUC-\d+[a-z]?\b/gi;
const MAX_PLAN_FILES = 20;
const MAX_PLAN_BYTES = 400_000;

// ── Git ────────────────────────────────────────────────────────────────

function git(root, args) {
  return execFileSync("git", ["-C", root, ...args], { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"], maxBuffer: 32 * 1024 * 1024 });
}

function gitOr(root, args, fallback = "") {
  try {
    return git(root, args);
  } catch {
    return fallback;
  }
}

/** La base de la comparación: la pedida, o origin/main, o main. null si no existe ninguna. */
export function resolveBase(root, wanted) {
  for (const ref of [wanted, "origin/main", "main", "origin/master", "master"].filter(Boolean)) {
    if (gitOr(root, ["rev-parse", "--verify", "--quiet", `${ref}^{commit}`]).trim()) return ref;
  }
  return null;
}

export function changedFiles(root, base) {
  return gitOr(root, ["diff", "--name-only", "--diff-filter=d", `${base}...HEAD`])
    .split("\n").map((l) => l.trim()).filter(Boolean);
}

/** Las UC de la rama: asuntos de los commits y nombre de la rama; si no hay, el marcador de UC activa. */
export function branchUcs(root, base, branch) {
  const found = new Set();
  const subjects = gitOr(root, ["log", "--format=%s", `${base}..HEAD`]);
  for (const text of [subjects, branch]) for (const m of String(text || "").matchAll(UC_ID)) found.add(m[0].toUpperCase());
  const source = found.size ? "commits y rama" : "marcador";
  if (!found.size) {
    try {
      const marker = JSON.parse(readFileSync(join(root, ".quality", "active_uc.json"), "utf8"));
      if (typeof marker?.uc_id === "string" && /^UC-\d+[a-z]?$/i.test(marker.uc_id)) found.add(marker.uc_id.toUpperCase());
    } catch {
      // sin marcador
    }
  }
  return { ucs: [...found], source: found.size ? source : "ninguna" };
}

// ── Configuración del proyecto ─────────────────────────────────────────

function readJson(path) {
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch {
    return null;
  }
}

function boardOf(root) {
  let boardId = "";
  let backendType = "";
  let freeformRoot = "";
  let orchestrator = "";
  for (const file of [".claude/project-config.json", ".claude/settings.local.json"]) {
    const config = readJson(join(root, file));
    if (!config) continue;
    boardId ||= config.boardId || config.board_id || "";
    backendType ||= config.backend_type || "";
    freeformRoot ||= config.freeform_root_absolute || "";
    const mr = config.multirepo;
    if (mr?.enabled && mr?.role === "satellite" && typeof mr.orchestrator === "string") orchestrator = mr.orchestrator;
    const sb = config.specbox;
    if (sb && typeof sb === "object") {
      backendType ||= sb.backend_type || "";
      boardId ||= sb.board_id || sb.project_id || sb.native_project_id || sb.trello_board_id || "";
      freeformRoot ||= sb.freeform_root_absolute || "";
    }
  }
  return { boardId, backendType, freeformRoot, orchestrator };
}

/**
 * El tablero de la puerta. En un satélite, el del orquestador (su tablero, sus planes): la
 * configuración de tablero que tenga el satélite no cuenta (UC-12602 AC-06).
 */
export function resolveBoard(root) {
  const own = boardOf(root);
  if (!own.orchestrator) return { ...own, root, orchestratorRoot: root, satellite: false };
  const orchestratorRoot = isAbsolute(own.orchestrator) ? own.orchestrator : resolve(root, own.orchestrator);
  if (!existsSync(orchestratorRoot)) {
    return { boardId: "", backendType: "", freeformRoot: "", root, orchestratorRoot, satellite: true, missingOrchestrator: true };
  }
  const orch = boardOf(orchestratorRoot);
  return { ...orch, root, orchestratorRoot, satellite: true };
}

/** «owner/nombre» del remoto origin (GitHub por https o ssh), o null. */
export function repoOf(root) {
  const url = gitOr(root, ["remote", "get-url", "origin"]).trim();
  const m = url.match(/[/:]([A-Za-z0-9_.-]+)\/([A-Za-z0-9_.-]+?)(?:\.git)?\/?$/);
  return m ? `${m[1]}/${m[2]}` : null;
}

/** El nombre del satélite de este repo en el orquestador (multirepo.satellites), o null. */
export function satelliteOf(board) {
  if (!board.satellite) return null;
  const satellites = readJson(join(board.orchestratorRoot, ".claude", "settings.local.json"))?.multirepo?.satellites;
  if (!satellites || typeof satellites !== "object") return null;
  for (const [name, entry] of Object.entries(satellites)) {
    if (typeof entry?.path === "string" && resolve(board.orchestratorRoot, entry.path) === resolve(board.root)) return name;
  }
  return null;
}

/** `drift` (o `specbox.drift`) del `.claude/settings.json` del repo: exclusiones y prefijos de rama sin UC. */
export function driftSettings(root) {
  const json = readJson(join(root, ".claude", "settings.json")) ?? {};
  const settings = json.specbox?.drift ?? json.drift ?? {};
  const list = (v) => (Array.isArray(v) ? v.filter((x) => typeof x === "string" && x.trim()) : null);
  return { exclude: list(settings.exclude) ?? [], skipPrefixes: list(settings.skip_branch_prefixes) ?? DEFAULT_SKIP_PREFIXES };
}

/** Los planes del orquestador que nombran alguna UC de la rama: {ruta relativa: texto}. */
export function plansFor(orchestratorRoot, ucs) {
  const dir = join(orchestratorRoot, "doc", "plans");
  const out = {};
  if (!ucs.length || !existsSync(dir)) return out;
  let total = 0;
  for (const name of readdirSync(dir).filter((n) => n.endsWith(".md")).sort()) {
    let text;
    try {
      text = readFileSync(join(dir, name), "utf8");
    } catch {
      continue;
    }
    const named = new Set([...text.matchAll(UC_ID)].map((m) => m[0].toUpperCase()));
    if (!ucs.some((u) => named.has(u))) continue;
    if (Object.keys(out).length >= MAX_PLAN_FILES || total + text.length > MAX_PLAN_BYTES) break;
    out[`doc/plans/${name}`] = text;
    total += text.length;
  }
  return out;
}

// ── Dependencias nuevas ────────────────────────────────────────────────

const MANIFESTS = { "package.json": "npm", "pyproject.toml": "pypi", "pubspec.yaml": "pub", "go.mod": "go" };

function npmNames(text) {
  const data = (() => {
    try {
      return JSON.parse(text);
    } catch {
      return null;
    }
  })();
  if (!data || typeof data !== "object") return new Set();
  const keys = ["dependencies", "devDependencies", "peerDependencies", "optionalDependencies"];
  return new Set(keys.flatMap((k) => (data[k] && typeof data[k] === "object" ? Object.keys(data[k]) : [])));
}

function pyNames(text) {
  const out = new Set();
  let table = "";
  let inArray = false;
  for (const raw of String(text).split("\n")) {
    const line = raw.replace(/#.*$/, "").trim();
    const header = line.match(/^\[+([^\]]+)\]+$/);
    if (header) {
      table = header[1].trim();
      inArray = false;
      continue;
    }
    const isDepTable = table === "project.optional-dependencies" || table === "dependency-groups";
    const start = line.match(/^([A-Za-z0-9_.-]+)\s*=\s*\[(.*)$/);
    if (start && ((table === "project" && start[1] === "dependencies") || (table === "tool.uv" && start[1] === "dev-dependencies") || isDepTable)) {
      inArray = !start[2].includes("]");
      for (const m of start[2].matchAll(/["']([^"']+)["']/g)) out.add(m[1]);
      continue;
    }
    if (inArray) {
      for (const m of line.matchAll(/["']([^"']+)["']/g)) out.add(m[1]);
      if (line.includes("]")) inArray = false;
    }
  }
  return new Set([...out].map((spec) => spec.split(/[\s\[<>=!~;,(]/)[0]).filter(Boolean));
}

function pubNames(text) {
  const out = new Set();
  let section = "";
  for (const raw of String(text).split("\n")) {
    if (/^\S/.test(raw)) section = raw.replace(/:.*$/, "").trim();
    const m = raw.match(/^ {2}([A-Za-z0-9_]+)\s*:/);
    if (m && (section === "dependencies" || section === "dev_dependencies")) out.add(m[1]);
  }
  return out;
}

function goNames(text) {
  const out = new Set();
  let block = false;
  for (const raw of String(text).split("\n")) {
    const line = raw.replace(/\/\/.*$/, "").trim();
    if (/^require\s*\($/.test(line)) block = true;
    else if (block && line === ")") block = false;
    else if (block && line) out.add(line.split(/\s+/)[0]);
    else {
      const single = line.match(/^require\s+(\S+)\s+\S+/);
      if (single) out.add(single[1]);
    }
  }
  return out;
}

const PARSERS = { npm: npmNames, pypi: pyNames, pub: pubNames, go: goNames };

/** Las dependencias que la rama añade a sus manifiestos: [{ecosystem, name, manifest}]. */
export function addedDependencies(root, base, files) {
  const out = [];
  for (const path of files) {
    const ecosystem = MANIFESTS[basename(path)];
    if (!ecosystem) continue;
    const before = PARSERS[ecosystem](gitOr(root, ["show", `${base}:${path}`]));
    const after = PARSERS[ecosystem](gitOr(root, ["show", `HEAD:${path}`]));
    for (const name of after) if (!before.has(name)) out.push({ ecosystem, name, manifest: path });
  }
  return out;
}

// ── MCP ────────────────────────────────────────────────────────────────

function messageOf(text, type, id) {
  if ((type || "").includes("text/event-stream")) {
    for (const line of String(text).split("\n")) {
      if (!line.startsWith("data:")) continue;
      try {
        const m = JSON.parse(line.slice(5).trim());
        if (m && m.id === id) return m;
      } catch {
        // una línea que no es JSON
      }
    }
    return null;
  }
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

/** Llama a una tool del MCP (initialize, initialized y tools/call) y devuelve su JSON. Lanza un Error corto. */
export async function callTool({ url, headers = {}, name, args = {}, timeoutMs = 20_000, fetchImpl = fetch }) {
  const control = new AbortController();
  const clock = setTimeout(() => control.abort(), timeoutMs);
  const send = async (body, session) => {
    const h = { "Content-Type": "application/json", Accept: "application/json, text/event-stream", ...headers };
    if (session) h["mcp-session-id"] = session;
    const res = await fetchImpl(url, { method: "POST", headers: h, body: JSON.stringify(body), signal: control.signal });
    const text = res.status === 202 || res.status === 204 ? "" : await res.text();
    return {
      status: res.status,
      session: res.headers.get("mcp-session-id") || session,
      message: body.id === undefined ? null : messageOf(text, res.headers.get("content-type"), body.id),
    };
  };
  try {
    const init = await send({
      jsonrpc: "2.0", id: 1, method: "initialize",
      params: { protocolVersion: "2025-06-18", capabilities: {}, clientInfo: { name: "specbox-drift", version: "1" } },
    });
    if (init.status >= 400 || !init.message?.result) throw new Error(`initialize ${init.status}`);
    await send({ jsonrpc: "2.0", method: "notifications/initialized" }, init.session);
    const r = await send({ jsonrpc: "2.0", id: 2, method: "tools/call", params: { name, arguments: args } }, init.session);
    if (r.status >= 400 || !r.message) throw new Error(`tools/call ${r.status}`);
    if (r.message.error) throw new Error(`tools/call ${r.message.error.code ?? "error"}`);
    const result = r.message.result || {};
    const text = result.content?.find?.((c) => c.type === "text")?.text;
    if (result.isError) throw new Error(String(text || "la tool respondió con un error").slice(0, 160));
    if (result.structuredContent) return result.structuredContent;
    try {
      return text ? JSON.parse(text) : {};
    } catch {
      return { text };
    }
  } catch (err) {
    if (err?.name === "AbortError") throw new Error(`sin respuesta en ${Math.round(timeoutMs / 1000)} s`);
    throw new Error(String(err?.message ?? err).slice(0, 160));
  } finally {
    clearTimeout(clock);
  }
}

// ── El informe ─────────────────────────────────────────────────────────

/** El informe en texto, para la persona y para el registro del CI. */
export function formatReport(report, context) {
  const lines = [];
  lines.push(`Puerta de desviación · rama ${context.branch} frente a ${context.base}`);
  lines.push(`UC de la rama (${context.ucSource}): ${report.uc_ids?.length ? report.uc_ids.join(", ") : "ninguna"}`);
  if (context.satellite) lines.push(`Tablero y planes del orquestador: ${context.orchestratorRoot} (${context.boardId})`);
  else lines.push(`Tablero: ${context.boardId}`);
  const plans = report.plans ?? [];
  lines.push(plans.length ? `Planes: ${plans.map((p) => `${p.path} (contrato ${p.contract_version})`).join(", ")}` : "Planes: ninguno");
  if (report.board && report.board !== "leído") lines.push(`Tablero: ${report.board}`);
  for (const note of report.notes ?? []) lines.push(`Nota: ${note}`);
  if (report.unknown_ucs?.length) lines.push(`UC que el tablero no tiene: ${report.unknown_ucs.join(", ")}`);
  lines.push("");
  lines.push("Ficheros:");
  for (const f of report.files ?? []) {
    if (f.excluded_by) lines.push(`  ${f.path} — excluido (${f.excluded_by})`);
    else if (f.claimed_by?.length) lines.push(`  ${f.path} — ${f.claimed_by.join(", ")} (${f.source === "plan+receipt" ? "plan y recibo" : f.source === "plan" ? "plan" : "recibo"})`);
    else lines.push(`  ${f.path} — sin UC${f.planned_for?.length ? ` (el plan lo prevé para ${f.planned_for.join(", ")})` : ""}`);
  }
  if (!(report.files ?? []).length) lines.push("  (la rama no cambia ficheros)");
  lines.push("");
  lines.push(`Exclusiones del proyecto (specbox.drift.exclude): ${report.exclude?.length ? report.exclude.join(", ") : "ninguna"}`);
  const deps = report.dependencies ?? {};
  if (deps.added?.length) {
    lines.push(`Dependencias nuevas: ${deps.added.map((d) => `${d.ecosystem}:${d.name}`).join(", ")}`);
    if (deps.undeclared?.length) {
      lines.push(`  Sin declarar en el plan («## Dependencias nuevas»): ${deps.undeclared.map((d) => `${d.ecosystem}:${d.name} (${d.manifest})`).join(", ")}`);
    }
  }
  for (const t of report.closed_touches ?? []) lines.push(`Aviso: ${t.proposal}`);
  if (report.closed_without_files) lines.push(`(${report.closed_without_files} UC cerradas sin lista de ficheros no avisan)`);
  lines.push("");
  const unclaimed = report.unclaimed?.length ?? 0;
  const undeclared = deps.undeclared?.length ?? 0;
  lines.push(
    report.ok
      ? "Resultado: cada fichero tiene su UC y no hay dependencias sin declarar."
      : `Resultado: ${unclaimed} fichero(s) sin UC, ${undeclared} dependencia(s) sin declarar · medida drift_gate en «${report.mode}».`,
  );
  return lines.join("\n");
}

function summaryLine(state, text) {
  return `${state}: ${text}`;
}

// ── La orden ───────────────────────────────────────────────────────────

/**
 * Ejecuta la puerta y devuelve el código de salida. `opts`: {root, base, json, summaryFile, mcpUrl}.
 * `deps` inyecta `print`, `env`, `fetchImpl`, `headersFor` y `now` para las pruebas.
 */
export async function runDrift(opts, deps = {}) {
  const print = deps.print ?? ((line) => process.stdout.write(`${line}\n`));
  const env = deps.env ?? process.env;
  const root = opts.root;
  const finish = (code, state, text, extra = {}) => {
    if (opts.summaryFile) {
      try {
        writeFileSync(opts.summaryFile, `${summaryLine(state, text)}\n`);
      } catch {
        // sin resumen: el registro tiene el informe
      }
    }
    if (opts.json) print(JSON.stringify({ state, message: text, ...extra }));
    else print(text);
    return code;
  };

  const base = resolveBase(root, opts.base);
  if (!base) return finish(0, "saltado", `No hay rama base con la que comparar (${opts.base || "origin/main"}): la puerta no se ejecuta.`);
  const branch = gitOr(root, ["rev-parse", "--abbrev-ref", "HEAD"]).trim() || "HEAD";
  const settings = driftSettings(root);
  const prefix = settings.skipPrefixes.find((p) => branch.startsWith(p));
  if (prefix) {
    return finish(0, "saltado", `La rama ${branch} no lleva UC por diseño (prefijo «${prefix}», specbox.drift.skip_branch_prefixes: ${settings.skipPrefixes.join(", ")}): fuera de la puerta.`);
  }
  const board = resolveBoard(root);
  if (board.missingOrchestrator) {
    return finish(0, "saltado", `El repositorio es satélite, pero su orquestador (${board.orchestratorRoot}) no está en este equipo: la puerta no se ejecuta.`);
  }
  if (!board.boardId && !board.backendType) {
    return finish(0, "saltado", "El proyecto no tiene tablero (no es spec-driven): la puerta no se ejecuta.");
  }
  const files = changedFiles(root, base);
  if (!files.length) return finish(0, "ok", `La rama ${branch} no cambia ficheros frente a ${base}.`);
  const { ucs, source } = branchUcs(root, base, branch);
  const args = {
    board_id: board.boardId,
    backend_type: board.backendType,
    files,
    uc_ids: ucs,
    plan_contents: plansFor(board.orchestratorRoot, ucs),
    dependencies_added: addedDependencies(root, base, files),
    exclude: settings.exclude,
  };
  const repo = repoOf(root);
  const satellite = satelliteOf(board);
  if (repo) args.repo = repo;
  if (satellite) args.satellite = satellite;
  if (board.backendType === "freeform") {
    const tracking = board.freeformRoot || join(board.orchestratorRoot, "doc", "tracking");
    try {
      args.items_content = readFileSync(join(tracking, "items.json"), "utf8");
    } catch {
      return finish(0, "saltado", `El tablero FreeForm no está en este equipo (${join(tracking, "items.json")}): la puerta no se ejecuta.`);
    }
    try {
      args.policy_content = readFileSync(join(tracking, "policy.json"), "utf8");
    } catch {
      // sin política: «warn»
    }
  }

  const url = opts.mcpUrl || env.SPECBOX_MCP_URL || "https://mcp.specbox.build/mcp";
  let headers = {};
  try {
    headers = (await deps.headersFor?.({ env: { ...env, CLAUDE_CODE_MCP_SERVER_URL: url } })) ?? {};
  } catch {
    headers = {};
  }
  if (board.backendType === "native" && !headers.Authorization) {
    return finish(0, "saltado", "Este equipo no tiene la identidad de SpecBox para leer el tablero: ejecuta `specbox login`. La puerta no se ejecuta.");
  }
  let report;
  try {
    report = await callTool({ url, headers, name: "get_drift_report", args, fetchImpl: deps.fetchImpl ?? fetch });
  } catch (err) {
    return finish(0, "saltado", `El MCP de SpecBox no respondió (${err.message}): la puerta no se ejecuta.`);
  }
  if (!report?.success) {
    return finish(0, "saltado", `El MCP no dio el informe (${report?.code ?? report?.error ?? "sin respuesta"}): la puerta no se ejecuta.`);
  }
  const text = formatReport(report, { branch, base, ucSource: source, satellite: board.satellite, orchestratorRoot: board.orchestratorRoot, boardId: board.boardId });
  const unclaimed = report.unclaimed?.length ?? 0;
  const undeclared = report.dependencies?.undeclared?.length ?? 0;
  const brief = report.ok
    ? `${files.length} fichero(s) con su UC`
    : `${unclaimed} sin UC, ${undeclared} dependencia(s) sin declarar (drift_gate: ${report.mode})`;
  if (opts.summaryFile) {
    try {
      writeFileSync(opts.summaryFile, `${summaryLine(report.ok ? "ok" : report.mode === "block" ? "fallo" : "aviso", brief)}\n`);
    } catch {
      // sin resumen
    }
  }
  if (opts.json) print(JSON.stringify({ state: report.ok ? "ok" : report.mode, branch, base, report }));
  else print(text);
  return !report.ok && report.mode === "block" ? 1 : 0;
}
