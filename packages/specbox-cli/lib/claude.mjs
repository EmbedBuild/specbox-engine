/**
 * Configurar Claude Code para que envíe el token en cada conexión (UC-3901
 * AC-03): la entrada `SpecBox-MCP` (ámbito de usuario) pasa a ser
 * `{type: "http", url, headersHelper}`, y las demás entradas que apuntan al
 * mismo servidor (ámbito local de cada proyecto) reciben el mismo ayudante,
 * de modo que los proyectos ya configurados siguen funcionando sin pasos
 * manuales.
 *
 * Se usa la orden oficial `claude mcp` (remove + add-json), nunca se edita
 * `~/.claude.json` a mano: Claude Code lo reescribe mientras está abierto. Si
 * `claude` no está en el PATH, se devuelve la orden para ejecutarla a mano.
 */
import { existsSync, mkdirSync, readFileSync, realpathSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { join, posix, win32 } from "node:path";
import { SERVER_NAME, isLegacyMcpUrl, migrateMcpUrl, serverOrigins, specboxHome } from "./config.mjs";
import { runCommand } from "./store.mjs";

export function quoteArg(value) {
  return `"${String(value).replace(/"/g, '\\"')}"`;
}

/**
 * La ruta de Node que se graba en el ayudante. `process.execPath` es la ruta
 * real del binario, que en Homebrew lleva la versión
 * (`/opt/homebrew/Cellar/node/26.7.0/bin/node`) y desaparece con
 * `brew upgrade`; se prefiere la primera entrada del PATH que apunta a ese
 * mismo binario (`/opt/homebrew/bin/node`), que el gestor de paquetes mantiene
 * al actualizar. Si ninguna apunta a él, se usa `process.execPath`.
 */
export function stableNodePath({
  execPath = process.execPath,
  pathEnv = process.env.PATH ?? "",
  platform = process.platform,
  realpath = realpathSync,
  exists = existsSync,
} = {}) {
  const path = platform === "win32" ? win32 : posix;
  const binary = platform === "win32" ? "node.exe" : "node";
  let target;
  try {
    target = realpath(execPath);
  } catch {
    return execPath;
  }
  for (const dir of pathEnv.split(path.delimiter)) {
    if (!dir) continue;
    const candidate = path.join(dir, binary);
    try {
      if (exists(candidate) && realpath(candidate) === target) return candidate;
    } catch {
      // entrada del PATH rota o sin permisos: se ignora
    }
  }
  return execPath;
}

/** La orden que Claude Code ejecuta: node absoluto + ayudante absoluto. */
export function helperCommand(helperPath, nodePath = stableNodePath()) {
  return `${quoteArg(nodePath)} ${quoteArg(helperPath)}`;
}

/** Las dos rutas de una orden de `helperCommand`, o null si no tiene esa forma. */
export function helperPaths(cmd) {
  const m = /^"([^"]+)" "([^"]+)"$/.exec(String(cmd ?? ""));
  return m ? { node: m[1], helper: m[2] } : null;
}

function origin(url) {
  try {
    return new URL(url).origin;
  } catch {
    return null;
  }
}

/**
 * Entradas de `~/.claude.json` (usuario y locales) que apuntan al servidor de SpecBox, por
 * cualquiera de sus nombres (UC-5102: también el anterior, para mudarlas al de ahora).
 */
export function findSpecboxEntries(claudeJson, mcpUrl) {
  const targets = new Set(serverOrigins(mcpUrl));
  const matches = (entry) => entry && typeof entry.url === "string" && targets.has(origin(entry.url));
  const found = [];
  for (const [name, entry] of Object.entries(claudeJson?.mcpServers ?? {})) {
    if (matches(entry)) found.push({ scope: "user", name, entry, cwd: null });
  }
  for (const [project, config] of Object.entries(claudeJson?.projects ?? {})) {
    for (const [name, entry] of Object.entries(config?.mcpServers ?? {})) {
      if (matches(entry)) found.push({ scope: "local", name, entry, cwd: project });
    }
  }
  return found;
}

/**
 * La entrada con el ayudante, sin ninguna cabecera Authorization fija que lo contradiga, y
 * con el nombre de ahora del servidor si apuntaba a uno anterior (UC-5102).
 */
export function withHelper(entry, helperCmd) {
  const { headers, headersHelper: _old, ...rest } = entry ?? {};
  void _old;
  const kept = Object.fromEntries(Object.entries(headers ?? {}).filter(([k]) => k.toLowerCase() !== "authorization"));
  return {
    ...rest,
    ...(typeof rest.url === "string" ? { url: migrateMcpUrl(rest.url) } : {}),
    type: rest.type ?? "http",
    ...(Object.keys(kept).length ? { headers: kept } : {}),
    headersHelper: helperCmd,
  };
}

/** Una entrada para la copia de seguridad: igual, pero sin el valor de ninguna cabecera Authorization. */
export function redactEntry(entry) {
  const headers = entry?.headers;
  if (!headers) return entry;
  return {
    ...entry,
    headers: Object.fromEntries(Object.entries(headers).map(([k, v]) => [k, k.toLowerCase() === "authorization" ? "***" : v])),
  };
}

/**
 * UC-5102 AC-02: guarda lo que se va a cambiar (las entradas tal como estaban) en
 * ~/.specbox/backups/claude-mcp-<fecha>.json. Devuelve la ruta, o null si no pudo.
 */
export function saveEntriesBackup(entries, { dir = join(specboxHome(), "backups"), now = new Date() } = {}) {
  if (!entries.length) return null;
  try {
    mkdirSync(dir, { recursive: true, mode: 0o700 });
    const stamp = now.toISOString().replace(/[-:]/g, "").replace(/\.\d+Z$/, "Z");
    const file = join(dir, `claude-mcp-${stamp}.json`);
    const body = { saved_at: now.toISOString(), reason: "specbox: entradas de SpecBox-MCP antes de reconfigurarlas", entries };
    writeFileSync(file, `${JSON.stringify(body, null, 2)}\n`, { mode: 0o600 });
    return file;
  } catch {
    return null;
  }
}

export function configureClaudeCode({
  mcpUrl,
  helperCmd,
  run = runCommand,
  claudeJsonPath = join(homedir(), ".claude.json"),
  readFile = readFileSync,
  projectExists = existsSync,
  backup = saveEntriesBackup,
}) {
  const userEntry = JSON.stringify({ type: "http", url: mcpUrl, headersHelper: helperCmd });
  const manual = `claude mcp add-json ${SERVER_NAME} '${userEntry}' --scope user`;
  const probe = run("claude", ["--version"]);
  if (probe.error || probe.status === null) return { ok: false, reason: "claude_missing", manual };

  // Se lee antes de tocar nada: así la copia de seguridad guarda las entradas como estaban.
  let claudeJson = {};
  try {
    claudeJson = JSON.parse(readFile(claudeJsonPath, "utf8"));
  } catch {
    // sin ~/.claude.json no hay más entradas que migrar
  }
  const pending = findSpecboxEntries(claudeJson, mcpUrl).filter((found) => {
    if (found.scope === "user" && found.name === SERVER_NAME) return false;
    if (found.entry.headersHelper === helperCmd && !isLegacyMcpUrl(found.entry.url)) return false;
    return !(found.cwd && !projectExists(found.cwd)); // proyecto que ya no existe
  });
  const previousUser = claudeJson?.mcpServers?.[SERVER_NAME];
  const userChanges = previousUser && JSON.stringify(previousUser) !== userEntry;
  const backupFile = backup([
    ...(userChanges ? [{ scope: "user", name: SERVER_NAME, cwd: null, entry: redactEntry(previousUser) }] : []),
    ...pending.map((f) => ({ scope: f.scope, name: f.name, cwd: f.cwd, entry: redactEntry(f.entry) })),
  ]);

  run("claude", ["mcp", "remove", SERVER_NAME, "--scope", "user"]); // puede no existir
  const added = run("claude", ["mcp", "add-json", SERVER_NAME, userEntry, "--scope", "user"]);
  if (added.status !== 0) {
    return { ok: false, reason: "add_failed", detail: `${added.stderr}${added.stdout}`.trim(), manual };
  }

  const updated = [{ scope: "user", name: SERVER_NAME, cwd: null }];
  const failed = [];
  for (const found of pending) {
    const opts = found.cwd ? { cwd: found.cwd } : {};
    run("claude", ["mcp", "remove", found.name, "--scope", found.scope], opts);
    const res = run(
      "claude",
      ["mcp", "add-json", found.name, JSON.stringify(withHelper(found.entry, helperCmd)), "--scope", found.scope],
      opts,
    );
    (res.status === 0 ? updated : failed).push({ scope: found.scope, name: found.name, cwd: found.cwd });
  }
  return { ok: true, updated, failed, ...(backupFile ? { backup: backupFile } : {}) };
}

/**
 * ¿La entrada de usuario usa nuestro ayudante y este puede ejecutarse? (para
 * `specbox status` y la extensión). Si el Node grabado ya no existe (p. ej.
 * una versión que borró el gestor de paquetes), es `false`: la extensión
 * vuelve a configurar Claude Code en el siguiente arranque. También si la
 * entrada apunta a un nombre anterior del servidor (UC-5102): así la extensión
 * actualizada muda las entradas al nombre de ahora sin pasos manuales.
 */
export function claudeUsesHelper({
  claudeJsonPath = join(homedir(), ".claude.json"),
  readFile = readFileSync,
  exists = existsSync,
} = {}) {
  try {
    const entry = JSON.parse(readFile(claudeJsonPath, "utf8"))?.mcpServers?.[SERVER_NAME];
    if (isLegacyMcpUrl(entry?.url)) return false;
    const paths = helperPaths(entry?.headersHelper);
    return Boolean(paths && paths.helper.endsWith("mcp-headers.mjs") && exists(paths.node) && exists(paths.helper));
  } catch {
    return false;
  }
}
