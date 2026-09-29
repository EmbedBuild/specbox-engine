/**
 * Órdenes internas para la extensión de VSCode (UC-3901 AC-03, UC-3904).
 *
 * La extensión empaqueta este paquete y lo ejecuta con el Node del sistema
 * para no reimplementar (y dejar divergir) el almacén seguro, el ayudante ni
 * la configuración de Claude Code: la extensión y `specbox login` hacen
 * exactamente lo mismo en un mismo ordenador. Hablan JSON (una línea por
 * stdout; la entrada, si la hay, por stdin) y no aparecen en `--help`.
 *
 *   _device      id y nombre del dispositivo (los mismos que usa `specbox login`)
 *   _status      ¿hay credencial? dispositivo, caducidad y si Claude Code usa el ayudante
 *                (nunca el token: solo su huella)
 *   _connect     guarda la credencial que trae la extensión, instala el ayudante y
 *                configura Claude Code
 *   _configure   instala el ayudante y configura Claude Code, sin credencial
 *   _adopt       con el token que ya tenía la extensión, obtiene un token de
 *                dispositivo (/devices/adopt, que NO revoca el anterior: puede estar
 *                pegado en otros sitios) y lo conecta como `_connect`
 *   _renew       renueva si toca y devuelve el token vigente (para la extensión)
 *   _disconnect  /devices/logout y borra la credencial local
 */
import { createHash } from "node:crypto";
import { claudeUsesHelper, configureClaudeCode, helperCommand } from "./claude.mjs";
import { CLIENT } from "./config.mjs";
import { deviceId, hostLabel } from "./device.mjs";
import { installHelper } from "./install.mjs";
import { credentialFromResponse, renewCredential, renewDue } from "./renew.mjs";

export async function readStdinJson(stream = process.stdin) {
  let raw = "";
  for await (const chunk of stream) raw += chunk;
  return raw.trim() ? JSON.parse(raw) : {};
}

function tokenSha(token) {
  return createHash("sha256").update(String(token)).digest("hex").slice(0, 16);
}

/** Lo que la extensión puede ver de una credencial: todo menos el token. */
export function credentialMeta(credential) {
  return {
    token_sha: tokenSha(credential.token),
    token_id: credential.token_id ?? null,
    device_id: credential.device_id ?? null,
    device_name: credential.device_name ?? null,
    client: credential.client ?? null,
    expires_at: credential.expires_at ?? null,
    renew_after: credential.renew_after ?? null,
    developer: credential.developer ?? null,
  };
}

function safeRead(store, account) {
  try {
    return store.read(account);
  } catch {
    return null;
  }
}

export async function runInternal(command, ctx) {
  const { config, store, account, home, fetchImpl, readInput, out, deps = {} } = ctx;
  const device = () => ({
    device_id: deps.deviceId ?? deviceId(CLIENT, { home }),
    host: deps.host ?? hostLabel(),
    client: CLIENT,
  });
  const connectClaude = () =>
    configureClaudeCode({
      mcpUrl: config.mcpUrl,
      helperCmd: helperCommand((deps.installHelper ?? installHelper)(home), deps.nodePath ?? process.execPath),
      run: deps.runCommand,
      claudeJsonPath: deps.claudeJsonPath,
    });
  const usesHelper = () => claudeUsesHelper(deps.claudeJsonPath ? { claudeJsonPath: deps.claudeJsonPath } : {});

  switch (command) {
    case "_device":
      out(device());
      return 0;

    case "_status": {
      const credential = safeRead(store, account);
      out({
        connected: Boolean(credential?.token),
        store: store.kind,
        ...(credential?.token ? credentialMeta(credential) : {}),
        claude_helper: usesHelper(),
      });
      return 0;
    }

    case "_connect": {
      const { credential } = await readInput();
      if (!credential?.token) {
        out({ ok: false, reason: "missing_credential" });
        return 1;
      }
      const stored = { ...credential, cloud_api: credential.cloud_api ?? config.cloudApi, updated_at: new Date().toISOString() };
      store.write(account, stored);
      out({ ok: true, store: store.kind, ...credentialMeta(stored), claude: connectClaude() });
      return 0;
    }

    case "_configure":
      out({ ok: true, claude: connectClaude() });
      return 0;

    case "_adopt": {
      const { token, issued_via: issuedVia = "vscode" } = await readInput();
      if (!token) {
        out({ ok: false, reason: "missing_token" });
        return 1;
      }
      let res;
      try {
        res = await fetchImpl(`${config.cloudApi}/devices/adopt`, {
          method: "POST",
          headers: { authorization: `Bearer ${token}`, "content-type": "application/json" },
          body: JSON.stringify({ ...device(), issued_via: issuedVia }),
        });
      } catch {
        out({ ok: false, reason: "network" });
        return 1;
      }
      if (res.status !== 200) {
        const reason = res.status === 401 ? "invalid_token" : res.status === 409 ? "conflict" : `http_${res.status}`;
        out({ ok: false, reason });
        return 1;
      }
      const credential = credentialFromResponse(await res.json(), config.cloudApi);
      store.write(account, credential);
      out({ ok: true, token: credential.token, store: store.kind, ...credentialMeta(credential), claude: connectClaude() });
      return 0;
    }

    case "_renew": {
      let credential = safeRead(store, account);
      if (!credential?.token) {
        out({ connected: false });
        return 0;
      }
      let renewed = false;
      if (renewDue(credential)) {
        const next = await renewCredential({ store, account, credential, fetchImpl, lockDir: home });
        renewed = next.token !== credential.token;
        credential = next;
      }
      out({ connected: true, renewed, token: credential.token, ...credentialMeta(credential) });
      return 0;
    }

    case "_disconnect": {
      const credential = safeRead(store, account);
      let remote = false;
      if (credential?.token) {
        try {
          const res = await fetchImpl(`${credential.cloud_api ?? config.cloudApi}/devices/logout`, {
            method: "POST",
            headers: { authorization: `Bearer ${credential.token}` },
          });
          remote = res.status === 200 || res.status === 401;
        } catch {
          remote = false;
        }
      }
      store.remove(account);
      out({ ok: true, remote, had_credential: Boolean(credential?.token) });
      return 0;
    }

    default:
      out({ ok: false, reason: "unknown_command" });
      return 1;
  }
}
