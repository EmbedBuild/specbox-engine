#!/usr/bin/env node
/**
 * Ayudante de cabeceras para Claude Code (UC-3901 AC-03, UC-3904 AC-03).
 *
 * Claude Code lo ejecuta (`headersHelper`) al conectar con el servidor MCP, al
 * reconectar y tras un 401/403, y usa como cabeceras el JSON que imprime. Lee
 * la credencial del almacén seguro para la URL del servidor que recibe en
 * `CLAUDE_CODE_MCP_SERVER_URL`, la renueva si le quedan menos de 14 días e
 * imprime `{"Authorization": "Bearer …"}`.
 *
 * Sin credencial imprime `{}`: la conexión sale sin token y el servidor decide
 * (en el periodo de gracia avisa; después la rechaza con el mensaje de cómo
 * conectarse). Nunca imprime otra cosa por stdout ni falla: un error de
 * Claude Code aquí dejaría a la persona sin MCP.
 *
 * UC-11301: también manda la clave de Stitch del proyecto (`X-Stitch-Api-Key`),
 * para que llegue al servidor sin pasar por la conversación.
 *
 * Se instala en ~/.specbox/bin junto a los módulos que importa.
 */
import { readFileSync, realpathSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { DEFAULT_MCP_URL, accountFor, specboxHome } from "./config.mjs";
import { renewCredential, renewDue } from "./renew.mjs";
import { createStore } from "./store.mjs";

export const STITCH_HEADER = "X-Stitch-Api-Key";

/**
 * La clave de Stitch: `STITCH_API_KEY` del entorno o `stitch.apiKey` del
 * `.claude/settings.local.json` más cercano subiendo desde la carpeta del
 * proyecto (donde la deja /visual-setup). null si no hay.
 */
export function stitchKeyFor({ env = process.env, cwd = env.CLAUDE_PROJECT_DIR || process.cwd() } = {}) {
  const fromEnv = (env.STITCH_API_KEY || "").trim();
  if (fromEnv) return fromEnv;
  for (let dir = resolve(cwd); ; dir = dirname(dir)) {
    try {
      const key = JSON.parse(readFileSync(join(dir, ".claude", "settings.local.json"), "utf8"))?.stitch?.apiKey;
      if (typeof key === "string" && key.trim()) return key.trim();
    } catch {
      // sin fichero o con JSON roto: se sigue subiendo
    }
    if (dirname(dir) === dir) return null;
  }
}

export async function headersFor({
  env = process.env,
  store = createStore({ home: specboxHome(env) }),
  fetchImpl = fetch,
  now = Date.now(),
  cwd,
} = {}) {
  const url = env.CLAUDE_CODE_MCP_SERVER_URL || env.SPECBOX_MCP_URL || DEFAULT_MCP_URL;
  const account = accountFor(url);
  const stitchKey = stitchKeyFor(cwd ? { env, cwd } : { env });
  const headers = stitchKey ? { [STITCH_HEADER]: stitchKey } : {};
  let credential = store.read(account);
  if (!credential?.token) return headers;
  if (renewDue(credential, now)) {
    credential = await renewCredential({ store, account, credential, fetchImpl, lockDir: specboxHome(env) });
  }
  return { Authorization: `Bearer ${credential.token}`, ...headers };
}

// Por `npx`/npm el script se ejecuta a través de un enlace simbólico: se
// compara con la ruta real.
const invokedDirectly = (() => {
  try {
    return Boolean(process.argv[1]) && import.meta.url === pathToFileURL(realpathSync(process.argv[1])).href;
  } catch {
    return false;
  }
})();
if (invokedDirectly) {
  headersFor()
    .then((headers) => process.stdout.write(JSON.stringify(headers)))
    .catch(() => process.stdout.write("{}"));
}
