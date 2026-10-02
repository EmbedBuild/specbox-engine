/**
 * Almacén seguro de la credencial del dispositivo (UC-3904 AC-02).
 *
 * Una credencial por servidor MCP (clave = URL del servidor), guardada en el
 * almacén del sistema:
 *
 *   - macOS:   Llavero (`security`). El secreto entra por stdin con
 *              `security -i`, nunca como argumento visible en `ps`.
 *   - Linux:   Secret Service (`secret-tool`), secreto por stdin.
 *   - Windows: DPAPI del usuario (PowerShell), en ~/.specbox/credentials/.
 *   - Si no hay ninguno (Linux sin sesión gráfica, contenedores): un fichero
 *     ~/.specbox/credentials.json con permisos 0600. `specbox status` lo avisa.
 *
 * La credencial es un JSON (token, caducidad, dispositivo, persona) que se
 * guarda en base64: así no hay comillas ni espacios que escapar.
 *
 * Todo es síncrono y sin dependencias: el ayudante que ejecuta Claude Code en
 * cada conexión tiene 10 s y no puede instalar nada.
 */
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { chmodSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { legacyAccountsFor } from "./config.mjs";

export const SERVICE = "SpecBox MCP";
const SECRET_TOOL_SERVICE = "specbox-mcp";

/** Ejecuta un programa sin shell. Nunca lanza: devuelve el resultado o el error. */
export function runCommand(cmd, args, { input, env, cwd, timeout = 8_000 } = {}) {
  const res = spawnSync(cmd, args, {
    input,
    cwd,
    env: env ? { ...process.env, ...env } : process.env,
    encoding: "utf8",
    windowsHide: true,
    timeout,
    // Sin shell nunca: los argumentos (JSON de Claude Code) no se reinterpretan.
    // En Windows, un `claude.cmd` de npm no arranca así (EINVAL) y se ofrece la
    // orden para ejecutarla a mano; el `claude.exe` nativo sí.
  });
  return { status: res.status, stdout: res.stdout ?? "", stderr: res.stderr ?? "", error: res.error ?? null };
}

export function encode(credential) {
  return Buffer.from(JSON.stringify(credential), "utf8").toString("base64");
}

export function decode(raw) {
  const text = String(raw ?? "").trim();
  if (!text) return null;
  try {
    return JSON.parse(Buffer.from(text, "base64").toString("utf8"));
  } catch {
    return null;
  }
}

function missing(res) {
  return res.error?.code === "ENOENT";
}

function keychainStore(run) {
  return {
    kind: "keychain",
    read(account) {
      const res = run("security", ["find-generic-password", "-s", SERVICE, "-a", account, "-w"]);
      return res.status === 0 ? decode(res.stdout) : null;
    },
    write(account, credential) {
      const res = run("security", ["-i"], {
        input: `add-generic-password -U -s "${SERVICE}" -a "${account}" -w ${encode(credential)}\n`,
      });
      if (res.status !== 0 || /error/i.test(res.stderr)) throw new Error(`keychain write failed: ${res.stderr.trim()}`);
    },
    remove(account) {
      run("security", ["delete-generic-password", "-s", SERVICE, "-a", account]);
    },
  };
}

function secretToolStore(run) {
  const attrs = (account) => ["service", SECRET_TOOL_SERVICE, "account", account];
  return {
    kind: "secret-service",
    read(account) {
      const res = run("secret-tool", ["lookup", ...attrs(account)]);
      if (missing(res)) throw Object.assign(new Error("secret-tool missing"), { code: "ENOENT" });
      return res.status === 0 ? decode(res.stdout) : null;
    },
    write(account, credential) {
      const res = run("secret-tool", ["store", `--label=${SERVICE}`, ...attrs(account)], { input: encode(credential) });
      if (missing(res)) throw Object.assign(new Error("secret-tool missing"), { code: "ENOENT" });
      if (res.status !== 0) throw new Error(`secret-tool store failed: ${res.stderr.trim()}`);
    },
    remove(account) {
      run("secret-tool", ["clear", ...attrs(account)]);
    },
  };
}

const PS_WRITE =
  "Add-Type -AssemblyName System.Security; $d=[Console]::In.ReadToEnd().Trim(); " +
  "$b=[Text.Encoding]::UTF8.GetBytes($d); " +
  "$p=[Security.Cryptography.ProtectedData]::Protect($b,$null,[Security.Cryptography.DataProtectionScope]::CurrentUser); " +
  "[IO.File]::WriteAllBytes($env:SPECBOX_CRED_FILE,$p)";
const PS_READ =
  "Add-Type -AssemblyName System.Security; $p=[IO.File]::ReadAllBytes($env:SPECBOX_CRED_FILE); " +
  "$b=[Security.Cryptography.ProtectedData]::Unprotect($p,$null,[Security.Cryptography.DataProtectionScope]::CurrentUser); " +
  "[Console]::Out.Write([Text.Encoding]::UTF8.GetString($b))";

function dpapiStore(run, home) {
  const fileFor = (account) =>
    join(home, "credentials", `${createHash("sha256").update(account).digest("hex").slice(0, 32)}.dpapi`);
  return {
    kind: "dpapi",
    read(account) {
      const res = run("powershell", ["-NoProfile", "-NonInteractive", "-Command", PS_READ], {
        env: { SPECBOX_CRED_FILE: fileFor(account) },
      });
      return res.status === 0 ? decode(res.stdout) : null;
    },
    write(account, credential) {
      mkdirSync(join(home, "credentials"), { recursive: true });
      const res = run("powershell", ["-NoProfile", "-NonInteractive", "-Command", PS_WRITE], {
        input: encode(credential),
        env: { SPECBOX_CRED_FILE: fileFor(account) },
      });
      if (res.status !== 0) throw new Error(`DPAPI write failed: ${res.stderr.trim()}`);
    },
    remove(account) {
      rmSync(fileFor(account), { force: true });
    },
  };
}

export function fileStore(home) {
  const file = join(home, "credentials.json");
  const load = () => {
    try {
      return JSON.parse(readFileSync(file, "utf8"));
    } catch {
      return {};
    }
  };
  const save = (all) => {
    mkdirSync(home, { recursive: true, mode: 0o700 });
    writeFileSync(file, JSON.stringify(all, null, 2), { mode: 0o600 });
    chmodSync(file, 0o600);
  };
  return {
    kind: "file",
    read(account) {
      return decode(load()[account]);
    },
    write(account, credential) {
      save({ ...load(), [account]: encode(credential) });
    },
    remove(account) {
      const all = load();
      if (!(account in all)) return;
      delete all[account];
      save(all);
    },
  };
}

/**
 * Si el almacén del sistema no está o no responde (Linux sin sesión gráfica),
 * se usa el fichero protegido. `kind` dice dónde quedó la última escritura.
 */
function withFallback(primary, fallback) {
  let kind = primary.kind;
  return {
    get kind() {
      return kind;
    },
    read(account) {
      try {
        const value = primary.read(account);
        if (value) return value;
      } catch {
        // sin almacén del sistema: se mira el fichero
      }
      return fallback.read(account);
    },
    write(account, credential) {
      try {
        primary.write(account, credential);
        kind = primary.kind;
        return;
      } catch {
        // cae al fichero protegido
      }
      fallback.write(account, credential);
      kind = fallback.kind;
    },
    remove(account) {
      try {
        primary.remove(account);
      } catch {
        // nada que borrar en el almacén del sistema
      }
      fallback.remove(account);
    },
  };
}

/**
 * UC-5102: una versión anterior guardó la credencial con la URL antigua del servidor como
 * clave. Al leer, si no está con la clave de ahora pero sí con una antigua, se copia a la de
 * ahora y se usa: el ordenador sigue identificado tras la mudanza a mcp.specbox.build. La
 * copia antigua se queda (una instalación sin actualizar la sigue leyendo). Al borrar
 * (`specbox logout`) se borran todas.
 */
export function withLegacyAccounts(store) {
  return {
    get kind() {
      return store.kind;
    },
    read(account) {
      const value = store.read(account);
      if (value) return value;
      for (const legacy of legacyAccountsFor(account)) {
        const old = store.read(legacy);
        if (!old) continue;
        try {
          store.write(account, old);
        } catch {
          // se reintenta en la próxima lectura; la credencial sirve igual
        }
        return old;
      }
      return null;
    },
    write(account, credential) {
      store.write(account, credential);
    },
    remove(account) {
      store.remove(account);
      for (const legacy of legacyAccountsFor(account)) store.remove(legacy);
    },
  };
}

function platformStore({ platform, run, home }) {
  if (platform === "darwin") return keychainStore(run);
  if (platform === "win32") return dpapiStore(run, home);
  if (platform === "linux") return withFallback(secretToolStore(run), fileStore(home));
  return fileStore(home);
}

export function createStore({ platform = process.platform, run = runCommand, home } = {}) {
  if (!home) throw new Error("createStore needs the specbox home");
  return withLegacyAccounts(platformStore({ platform, run, home }));
}
