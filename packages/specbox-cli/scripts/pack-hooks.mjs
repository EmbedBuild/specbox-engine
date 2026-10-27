#!/usr/bin/env node
/**
 * UC-11201 — empaqueta los hooks del engine dentro del paquete `specbox`.
 *
 * Copia `.claude/hooks/*.mjs` y `.claude/hooks/lib/*.mjs` (sin pruebas) a
 * `<destino>/` y escribe al lado:
 *   - hooks-manifest.json: la versión y el sha256 de cada fichero publicado;
 *   - hooks-history.json: las huellas de cada fichero en las etiquetas vX.Y.Z
 *     desde la 6.20.0, para reconocer un hook sin retocar de un proyecto que
 *     no tiene registro (si el clon no tiene etiquetas, solo la versión actual);
 *   - settings-hooks.json: el bloque `hooks` de templates/settings.json.template.
 *
 * `npm pack` / `npm publish` lo ejecutan (prepack) y la extensión, al copiar la
 * CLI (copy-cli.mjs). La salida es generada: no se edita ni se versiona.
 *
 *   node scripts/pack-hooks.mjs [destino]   (por defecto <paquete>/hooks)
 */
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, readdirSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const PACKAGE_DIR = resolve(dirname(fileURLToPath(import.meta.url)), "..");
export const ENGINE_ROOT = resolve(PACKAGE_DIR, "..", "..");
export const HISTORY_SINCE = "6.20.0";

export function sha256(content) {
  return createHash("sha256").update(content).digest("hex");
}

const isHookFile = (name) => name.endsWith(".mjs") && !name.endsWith(".test.mjs") && name !== "test-hooks.mjs";

/** Las rutas (relativas a .claude/hooks) que reciben los proyectos. */
export function hookFiles(engineRoot = ENGINE_ROOT) {
  const base = join(engineRoot, ".claude", "hooks");
  const top = readdirSync(base).filter(isHookFile).sort();
  const lib = readdirSync(join(base, "lib")).filter(isHookFile).sort().map((n) => `lib/${n}`);
  return [...top, ...lib];
}

function semver(tag) {
  const m = /^v(\d+)\.(\d+)\.(\d+)$/.exec(tag);
  return m ? m.slice(1).map(Number) : null;
}

function atLeast(a, b) {
  for (let i = 0; i < 3; i += 1) if (a[i] !== b[i]) return a[i] > b[i];
  return true;
}

function git(engineRoot, args) {
  return execFileSync("git", ["-C", engineRoot, ...args], { encoding: "buffer", stdio: ["ignore", "pipe", "ignore"], maxBuffer: 64 * 1024 * 1024 });
}

/** {ruta: [sha256 publicados]} desde HISTORY_SINCE; {} si no hay etiquetas. */
export function hookHistory(engineRoot = ENGINE_ROOT, since = HISTORY_SINCE) {
  const floor = semver(`v${since}`);
  let tags = [];
  try {
    tags = git(engineRoot, ["tag", "-l", "v*"]).toString().split("\n").filter((t) => semver(t) && atLeast(semver(t), floor));
  } catch {
    return {};
  }
  const history = {};
  for (const tag of tags) {
    let paths = [];
    try {
      paths = git(engineRoot, ["ls-tree", "-r", "--name-only", tag, ".claude/hooks"]).toString().split("\n");
    } catch {
      continue;
    }
    for (const path of paths) {
      const rel = path.replace(/^\.claude\/hooks\//, "");
      const name = rel.split("/").pop();
      if (!path.startsWith(".claude/hooks/") || !isHookFile(name) || (rel.includes("/") && !rel.startsWith("lib/"))) continue;
      const hash = sha256(git(engineRoot, ["show", `${tag}:${path}`]));
      history[rel] ??= [];
      if (!history[rel].includes(hash)) history[rel].push(hash);
    }
  }
  return history;
}

export function packHooks(target = join(PACKAGE_DIR, "hooks"), { engineRoot = ENGINE_ROOT, version } = {}) {
  const pkgVersion = version ?? JSON.parse(readFileSync(join(PACKAGE_DIR, "package.json"), "utf8")).version;
  const files = {};
  rmSync(target, { recursive: true, force: true });
  mkdirSync(join(target, "lib"), { recursive: true });
  for (const rel of hookFiles(engineRoot)) {
    const content = readFileSync(join(engineRoot, ".claude", "hooks", rel));
    writeFileSync(join(target, rel), content);
    files[rel] = sha256(content);
  }
  const history = hookHistory(engineRoot);
  for (const [rel, hash] of Object.entries(files)) {
    history[rel] ??= [];
    if (!history[rel].includes(hash)) history[rel].push(hash);
  }
  const template = JSON.parse(readFileSync(join(engineRoot, "templates", "settings.json.template"), "utf8"));
  writeFileSync(join(target, "hooks-manifest.json"), `${JSON.stringify({ version: pkgVersion, files }, null, 2)}\n`);
  writeFileSync(join(target, "hooks-history.json"), `${JSON.stringify(history, null, 2)}\n`);
  writeFileSync(join(target, "settings-hooks.json"), `${JSON.stringify(template.hooks ?? {}, null, 2)}\n`);
  return { target, files: Object.keys(files).length, history: Object.keys(history).length };
}

if (process.argv[1] && existsSync(process.argv[1]) && import.meta.url === pathToFileURL(realpathSync(process.argv[1])).href) {
  const result = packHooks(process.argv[2] ? resolve(process.argv[2]) : undefined);
  // stderr: as prepack, stdout belongs to `npm pack --json` (the publish workflow parses it).
  process.stderr.write(`pack-hooks: ${result.files} hooks → ${result.target}\n`);
}
