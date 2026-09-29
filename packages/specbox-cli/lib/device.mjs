/**
 * Identidad del dispositivo (UC-3904 AC-01): un dispositivo es un ordenador y
 * un cliente MCP. El `device_id` es el SHA-256 del id de la máquina y el
 * cliente: estable entre reinstalaciones y sin revelar el id real al servidor.
 * Si no se puede leer el id de la máquina, se usa uno aleatorio guardado en
 * `~/.specbox/device-id`.
 */
import { createHash, randomUUID } from "node:crypto";
import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { hostname } from "node:os";
import { join } from "node:path";

export function machineId({ platform = process.platform, run = execFileSync, readFile = readFileSync } = {}) {
  try {
    if (platform === "darwin") {
      const out = run("ioreg", ["-rd1", "-c", "IOPlatformExpertDevice"], { encoding: "utf8" });
      const match = /"IOPlatformUUID" = "([^"]+)"/.exec(out);
      if (match) return match[1];
    } else if (platform === "win32") {
      const out = run("reg", ["query", "HKLM\\SOFTWARE\\Microsoft\\Cryptography", "/v", "MachineGuid"], {
        encoding: "utf8",
      });
      const match = /MachineGuid\s+REG_SZ\s+(\S+)/.exec(out);
      if (match) return match[1];
    } else {
      for (const file of ["/etc/machine-id", "/var/lib/dbus/machine-id"]) {
        try {
          const value = String(readFile(file, "utf8")).trim();
          if (value) return value;
        } catch {
          // siguiente fuente
        }
      }
    }
  } catch {
    // sin id de máquina: se usa el aleatorio persistido
  }
  return null;
}

function persistedRandomId(home) {
  const file = join(home, "device-id");
  try {
    const value = readFileSync(file, "utf8").trim();
    if (value) return value;
  } catch {
    // se crea abajo
  }
  const id = randomUUID();
  mkdirSync(home, { recursive: true, mode: 0o700 });
  writeFileSync(file, id, { mode: 0o600 });
  return id;
}

export function deviceId(client, { home, machine = machineId } = {}) {
  const seed = (typeof machine === "function" ? machine() : machine) || persistedRandomId(home);
  return createHash("sha256").update(`${seed}:${client}`).digest("hex");
}

/** Nombre legible del ordenador para el nombre del dispositivo (≤ 80 caracteres). */
export function hostLabel(name = hostname()) {
  const clean = String(name)
    .replace(/\.local$/i, "")
    .replace(/[\u0000-\u001f\u007f]/g, "")
    .trim();
  return (clean || "ordenador").slice(0, 80);
}
