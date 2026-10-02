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

export const DEFAULT_MCP_URL = "https://mcp.specbox.build/mcp";

/**
 * UC-5102: nombres anteriores del mismo servidor. Comparten credencial con DEFAULT_MCP_URL
 * (`accountFor` los traduce) y sus entradas en Claude Code se mudan a él. El nombre antiguo
 * sigue respondiendo (UC-5101), así que una instalación sin actualizar no se rompe.
 */
export const LEGACY_MCP_URLS = ["https://mcp-specbox-engine.jpsdeveloper.com/mcp"];

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

/**
 * Clave de la credencial en el almacén: la URL del servidor sin barra final. Un nombre
 * anterior del servidor da la clave del nombre de ahora (UC-5102): una sola credencial.
 */
export function accountFor(mcpUrl) {
  const key = urlKey(mcpUrl);
  return LEGACY_MCP_URLS.some((legacy) => urlKey(legacy) === key) ? urlKey(DEFAULT_MCP_URL) : key;
}

/** Las claves con las que una versión anterior pudo guardar la credencial de `account`. */
export function legacyAccountsFor(account) {
  return account === urlKey(DEFAULT_MCP_URL) ? LEGACY_MCP_URLS.map(urlKey) : [];
}

/** ¿Apunta esta URL a un nombre anterior del servidor? (cualquier ruta de ese origen) */
export function isLegacyMcpUrl(value) {
  const from = originOf(value);
  return Boolean(from) && LEGACY_MCP_URLS.some((legacy) => originOf(legacy) === from);
}

/** La misma URL con el nombre de ahora en lugar de uno anterior; cualquier otra, igual. */
export function migrateMcpUrl(value) {
  if (!isLegacyMcpUrl(value)) return value;
  const url = new URL(value);
  return `${new URL(DEFAULT_MCP_URL).origin}${url.pathname}${url.search}`;
}

/** Los orígenes que son este servidor: el suyo y, si es el de SpecBox, los anteriores. */
export function serverOrigins(mcpUrl) {
  const own = originOf(mcpUrl);
  return own === originOf(DEFAULT_MCP_URL) ? [own, ...LEGACY_MCP_URLS.map(originOf)] : [own];
}

function urlKey(mcpUrl) {
  const url = new URL(mcpUrl);
  return stripSlash(`${url.origin}${url.pathname}`);
}

function originOf(value) {
  try {
    return new URL(value).origin;
  } catch {
    return null;
  }
}

function stripSlash(value) {
  return String(value).replace(/\/+$/, "");
}
