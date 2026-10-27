/**
 * UC-11201 — actualizar los hooks de un proyecto sin pisar lo que se cambió en local.
 *
 * Cada proyecto ejecuta su copia de los hooks (`node .claude/hooks/<hook>.mjs`).
 * El paquete trae los hooks publicados con su huella (hooks-manifest.json) y las
 * huellas de las versiones anteriores (hooks-history.json); el proyecto guarda
 * en `.claude/hooks/.specbox-hooks.json` qué instaló. Con eso cada fichero queda en:
 *
 *   current    igual que el publicado
 *   updatable  sin retocar (huella de una versión publicada o de lo instalado): se sustituye
 *   modified   retocado en local: no se toca; la versión nueva queda al lado (<hook>.mjs.new)
 *              salvo que se pida sobrescribirlo
 *   missing    no está en el proyecto: se instala
 *   retired    lo instaló una versión anterior y ya no se publica: se lista, no se borra
 *
 * `.claude/settings.json` solo gana registros: los hooks de la plantilla que no estén.
 */
import { createHash } from "node:crypto";
import { copyFileSync, existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

export const REGISTRY = ".specbox-hooks.json";
const LIB_DIR = dirname(fileURLToPath(import.meta.url));

function sha256(content) {
  return createHash("sha256").update(content).digest("hex");
}

function readJson(path, fallback = null) {
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch {
    return fallback;
  }
}

function writeAtomic(path, content) {
  mkdirSync(dirname(path), { recursive: true });
  const tmp = `${path}.${process.pid}.tmp`;
  writeFileSync(tmp, content);
  renameSync(tmp, path);
}

/** Los hooks que trae este paquete (o null si se ejecuta desde un clon sin empaquetar). */
export function loadPackaged(dir = join(LIB_DIR, "..", "hooks")) {
  const manifest = readJson(join(dir, "hooks-manifest.json"));
  if (!manifest?.files) return null;
  return {
    dir,
    version: manifest.version,
    files: manifest.files,
    history: readJson(join(dir, "hooks-history.json"), {}),
    settingsHooks: readJson(join(dir, "settings-hooks.json"), {}),
  };
}

function registrations(hooks) {
  const out = [];
  for (const [event, groups] of Object.entries(hooks ?? {})) {
    for (const group of groups ?? []) {
      for (const hook of group.hooks ?? []) out.push({ event, matcher: group.matcher, hook });
    }
  }
  return out;
}

/** Los registros de la plantilla que faltan en el settings.json del proyecto. */
export function missingRegistrations(settings, settingsHooks) {
  const present = new Set(registrations(settings?.hooks).map((r) => `${r.event}\u0000${r.hook.command}`));
  return registrations(settingsHooks).filter((r) => !present.has(`${r.event}\u0000${r.hook.command}`));
}

/** El estado de cada hook del proyecto frente a los publicados (AC-01). */
export function hooksStatus({ projectRoot, packaged }) {
  const hooksDir = join(projectRoot, ".claude", "hooks");
  const registry = readJson(join(hooksDir, REGISTRY), {});
  const hooks = [];
  for (const [path, published] of Object.entries(packaged.files)) {
    const local = join(hooksDir, path);
    if (!existsSync(local)) {
      hooks.push({ path, state: "missing" });
      continue;
    }
    const hash = sha256(readFileSync(local));
    let state = "modified";
    if (hash === published) state = "current";
    else if (hash === registry.files?.[path] || (packaged.history[path] ?? []).includes(hash)) state = "updatable";
    hooks.push({ path, state });
  }
  for (const path of Object.keys(registry.files ?? {})) {
    if (!(path in packaged.files) && existsSync(join(hooksDir, path))) hooks.push({ path, state: "retired" });
  }
  const settings = readJson(join(projectRoot, ".claude", "settings.json"), {});
  const settingsMissing = missingRegistrations(settings, packaged.settingsHooks).map((r) => ({
    event: r.event,
    matcher: r.matcher ?? null,
    command: r.hook.command,
  }));
  return {
    version: packaged.version,
    installed_version: registry.version ?? null,
    hooks,
    settings_missing: settingsMissing,
    differs: hooks.some((h) => h.state !== "current") || settingsMissing.length > 0,
  };
}

const matches = (path, wanted) => wanted.some((w) => w === path || w === path.replace(/\.mjs$/, "") || `lib/${w}` === path || `lib/${w}.mjs` === path);

/**
 * Aplica la actualización (AC-02/AC-03). `overwrite`: hooks retocados que sí se
 * sustituyen (nombre o ruta, con o sin .mjs). Devuelve qué se hizo.
 */
export function updateHooks({ projectRoot, packaged, overwrite = [], now = () => new Date().toISOString() }) {
  const status = hooksStatus({ projectRoot, packaged });
  const hooksDir = join(projectRoot, ".claude", "hooks");
  const result = { version: packaged.version, written: [], kept: [], retired: [], settings_added: 0, settings_backup: null };
  for (const { path, state } of status.hooks) {
    const source = join(packaged.dir, path);
    const local = join(hooksDir, path);
    if (state === "missing" || state === "updatable" || (state === "modified" && matches(path, overwrite))) {
      writeAtomic(local, readFileSync(source));
      result.written.push(path);
    } else if (state === "modified") {
      writeAtomic(`${local}.new`, readFileSync(source));
      result.kept.push({ path, new: `.claude/hooks/${path}.new` });
    } else if (state === "retired") {
      result.retired.push(path);
    }
  }
  // A retired hook stays in the registry while it is on disk, so it keeps being listed.
  const previous = readJson(join(hooksDir, REGISTRY), {}).files ?? {};
  const files = { ...packaged.files };
  for (const path of result.retired) files[path] = previous[path];
  writeAtomic(join(hooksDir, REGISTRY), `${JSON.stringify({ version: packaged.version, updated_at: now(), files }, null, 2)}\n`);

  const settingsPath = join(projectRoot, ".claude", "settings.json");
  if (status.settings_missing.length) {
    const settings = readJson(settingsPath, {});
    if (existsSync(settingsPath)) {
      result.settings_backup = ".claude/settings.json.bak";
      copyFileSync(settingsPath, `${settingsPath}.bak`);
    }
    settings.hooks ??= {};
    for (const r of missingRegistrations(settings, packaged.settingsHooks)) {
      const groups = (settings.hooks[r.event] ??= []);
      const group = groups.find((g) => (g.matcher ?? null) === (r.matcher ?? null));
      if (group) (group.hooks ??= []).push(r.hook);
      else groups.push(r.matcher === undefined ? { hooks: [r.hook] } : { matcher: r.matcher, hooks: [r.hook] });
      result.settings_added += 1;
    }
    writeAtomic(settingsPath, `${JSON.stringify(settings, null, 2)}\n`);
  }
  return result;
}
