#!/usr/bin/env node
/**
 * `specbox` — conectar un ordenador a SpecBox sin copiar tokens (UC-3904).
 *
 *   specbox login    código de un solo uso → token al almacén seguro →
 *                    ayudante en ~/.specbox/bin → Claude Code lo usa solo
 *   specbox status   con qué cuenta y dispositivo, caducidad, si sigue valiendo
 *   specbox logout   desconecta el dispositivo y borra la credencial local
 *
 * Todo se puede inyectar (`run`) para las pruebas.
 */
import { spawn } from "node:child_process";
import { realpathSync } from "node:fs";
import { pathToFileURL } from "node:url";
import { claudeUsesHelper, configureClaudeCode, helperCommand } from "../lib/claude.mjs";
import { CLIENT, HOW_TO_CONNECT_URL, accountFor, resolveConfig, specboxHome } from "../lib/config.mjs";
import { deviceId, hostLabel } from "../lib/device.mjs";
import { installHelper, packageVersion } from "../lib/install.mjs";
import { readStdinJson, runInternal } from "../lib/internal.mjs";
import { LoginError, deviceLogin } from "../lib/login.mjs";
import { messages, pickLang } from "../lib/messages.mjs";
import { createStore } from "../lib/store.mjs";

export function parseArgs(argv) {
  const opts = { command: null, server: null, cloud: null, browser: true };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--server") opts.server = argv[(i += 1)];
    else if (arg === "--cloud") opts.cloud = argv[(i += 1)];
    else if (arg === "--no-browser") opts.browser = false;
    else if (arg === "--version" || arg === "-v") opts.command = "version";
    else if (arg === "--help" || arg === "-h") opts.command = "help";
    else if (!opts.command) opts.command = arg;
  }
  return opts;
}

function openInBrowser(url) {
  const [cmd, args] =
    process.platform === "darwin"
      ? ["open", [url]]
      : process.platform === "win32"
        ? ["cmd", ["/c", "start", "", url]]
        : ["xdg-open", [url]];
  try {
    spawn(cmd, args, { stdio: "ignore", detached: true, windowsHide: true }).on("error", () => {}).unref();
  } catch {
    // sin navegador: la persona tiene el enlace en pantalla
  }
}

export async function run(argv, deps = {}) {
  const env = deps.env ?? process.env;
  const print = deps.print ?? ((line) => process.stdout.write(`${line}\n`));
  const printErr = deps.printErr ?? ((line) => process.stderr.write(`${line}\n`));
  const fetchImpl = deps.fetchImpl ?? fetch;
  const t = messages(pickLang(env));
  const opts = parseArgs(argv);
  const config = resolveConfig({ server: opts.server, cloud: opts.cloud }, env);
  const home = specboxHome(env);
  const store = deps.store ?? createStore({ home });
  const account = accountFor(config.mcpUrl);

  // Órdenes internas de la extensión de VSCode (JSON por stdin/stdout).
  if (typeof opts.command === "string" && opts.command.startsWith("_")) {
    return runInternal(opts.command, {
      config,
      store,
      account,
      home,
      fetchImpl,
      readInput: deps.readInput ?? readStdinJson,
      out: (value) => print(JSON.stringify(value)),
      deps,
    });
  }

  switch (opts.command) {
    case "version":
      print(packageVersion() ?? "unknown");
      return 0;
    case "login": {
      print(t.loginTitle);
      const device = {
        device_id: deps.deviceId ?? deviceId(CLIENT, { home }),
        host: deps.host ?? hostLabel(),
        client: CLIENT,
      };
      let credential;
      try {
        credential = await deviceLogin({
          cloudApi: config.cloudApi,
          account,
          store,
          device,
          fetchImpl,
          sleep: deps.sleep,
          onCode: (code) => {
            print(t.openUrl(code.verification_uri_complete));
            print(t.confirmCode(code.user_code));
            print(t.waiting(Math.round((code.expires_in ?? 600) / 60)));
            if (opts.browser) (deps.openUrl ?? openInBrowser)(code.verification_uri_complete);
          },
        });
      } catch (err) {
        printErr(err instanceof LoginError ? t.loginError(err.code) : t.loginError(err?.message ?? "error"));
        return 1;
      }
      print(t.connected(credential, store.kind));
      if (store.kind === "file") print(t.fileStoreWarning);

      const helperPath = (deps.installHelper ?? installHelper)(home);
      const result = configureClaudeCode({
        mcpUrl: config.mcpUrl,
        helperCmd: helperCommand(helperPath, deps.nodePath ?? process.execPath),
        run: deps.runCommand,
        claudeJsonPath: deps.claudeJsonPath,
      });
      if (result.ok) {
        print(t.claudeConfigured(result.updated));
        if (result.failed.length) print(t.claudeFailed(result.failed));
      } else {
        print(t.claudeManual(result.manual));
      }
      print(t.howItWorks(HOW_TO_CONNECT_URL));
      return 0;
    }
    case "status": {
      const credential = store.read(account);
      if (!credential?.token) {
        print(t.notConnected);
        return 1;
      }
      let valid = null;
      try {
        const res = await fetchImpl(`${credential.cloud_api ?? config.cloudApi}/whoami`, {
          headers: { authorization: `Bearer ${credential.token}`, accept: "application/json" },
        });
        valid = res.status === 200 ? true : res.status === 401 ? false : null;
      } catch {
        valid = null;
      }
      print(t.statusTitle);
      print(
        t.statusLines(
          credential,
          store.kind,
          config.mcpUrl,
          valid,
          claudeUsesHelper(deps.claudeJsonPath ? { claudeJsonPath: deps.claudeJsonPath } : {}),
        ),
      );
      return valid === false ? 1 : 0;
    }
    case "logout": {
      const credential = store.read(account);
      if (!credential?.token) {
        print(t.notConnected);
        return 0;
      }
      let remote = false;
      try {
        const res = await fetchImpl(`${credential.cloud_api ?? config.cloudApi}/devices/logout`, {
          method: "POST",
          headers: { authorization: `Bearer ${credential.token}` },
        });
        remote = res.status === 200 || res.status === 401; // 401: ya no valía
      } catch {
        remote = false;
      }
      store.remove(account);
      print(t.loggedOut(credential.device_name ?? "?", remote));
      return 0;
    }
    case "help":
    case null:
      print(t.usage);
      return opts.command === "help" ? 0 : 1;
    default:
      printErr(t.usage);
      return 1;
  }
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
  run(process.argv.slice(2)).then(
    (code) => process.exit(code),
    (err) => {
      process.stderr.write(`${err?.stack ?? err}\n`);
      process.exit(1);
    },
  );
}
