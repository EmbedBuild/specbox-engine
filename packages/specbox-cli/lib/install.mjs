/**
 * Instala el ayudante de cabeceras en `~/.specbox/bin` (ruta fija que no
 * cambia al actualizar el paquete ni la extensión): el script y los módulos
 * que importa, más un package.json que marca la carpeta como ESM. Se
 * sobrescribe en cada `specbox login` para llevar siempre la última versión.
 */
import { copyFileSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

export const RUNTIME_FILES = ["config.mjs", "store.mjs", "renew.mjs", "mcp-headers.mjs"];

const LIB_DIR = dirname(fileURLToPath(import.meta.url));

export function packageVersion() {
  try {
    return JSON.parse(readFileSync(join(LIB_DIR, "..", "package.json"), "utf8")).version;
  } catch {
    return null;
  }
}

export function installHelper(home, { sourceDir = LIB_DIR, version = packageVersion() } = {}) {
  const bin = join(home, "bin");
  mkdirSync(bin, { recursive: true, mode: 0o700 });
  for (const file of RUNTIME_FILES) copyFileSync(join(sourceDir, file), join(bin, file));
  writeFileSync(
    join(bin, "package.json"),
    `${JSON.stringify({ private: true, type: "module", specbox_helper_version: version }, null, 2)}\n`,
  );
  return join(bin, "mcp-headers.mjs");
}
