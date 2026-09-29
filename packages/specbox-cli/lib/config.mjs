/**
 * Valores por defecto y rutas de `specbox` (UC-3904).
 *
 * Todo se puede cambiar por entorno para operadores con su propio servidor:
 *   SPECBOX_MCP_URL    servidor MCP remoto
 *   SPECBOX_CLOUD_API  API del panel (código de un solo uso, renovación)
 *   SPECBOX_HOME       carpeta local de specbox (por defecto ~/.specbox)
 */
import { homedir } from "node:os";
import { join } from "node:path";

export const DEFAULT_MCP_URL = "https://mcp-specbox-engine.jpsdeveloper.com/mcp";
export const DEFAULT_CLOUD_API = "https://api-cloud.specbox.build/api";
export const HOW_TO_CONNECT_URL = "https://cloud.specbox.build/como-se-conecta";

/** Nombre del servidor en Claude Code: las skills del engine usan `mcp__SpecBox-MCP__*`. */
export const SERVER_NAME = "SpecBox-MCP";

/** El cliente que usa el token guardado en el almacén: Claude Code. */
export const CLIENT = "claude-code";

/** Los clientes renuevan a partir de estos días antes de caducar (UC-3904 AC-03). */
export const RENEW_WINDOW_DAYS = 14;

export function specboxHome(env = process.env) {
  return env.SPECBOX_HOME || join(homedir(), ".specbox");
}

export function resolveConfig({ server, cloud } = {}, env = process.env) {
  return {
    mcpUrl: stripSlash(server || env.SPECBOX_MCP_URL || DEFAULT_MCP_URL),
    cloudApi: stripSlash(cloud || env.SPECBOX_CLOUD_API || DEFAULT_CLOUD_API),
  };
}

/** Clave de la credencial en el almacén: la URL del servidor sin barra final. */
export function accountFor(mcpUrl) {
  const url = new URL(mcpUrl);
  return stripSlash(`${url.origin}${url.pathname}`);
}

function stripSlash(value) {
  return String(value).replace(/\/+$/, "");
}
