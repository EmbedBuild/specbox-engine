/**
 * Renovación automática del token (UC-3904 AC-03).
 *
 * A partir de 14 días antes de caducar, el cliente pide un token nuevo con el
 * vigente (POST /api/devices/renew), guarda el nuevo y el viejo deja de valer.
 * La persona no hace nada. Varias sesiones de Claude Code pueden intentarlo a
 * la vez: un cerrojo en ~/.specbox las pone en fila, y quien llega tarde usa
 * la credencial que ya renovó otra (también si el servidor responde 409).
 * Si la red falla, se sigue con el token vigente: todavía le quedan días.
 */
import { closeSync, mkdirSync, openSync, statSync, unlinkSync } from "node:fs";
import { join } from "node:path";
import { RENEW_WINDOW_DAYS } from "./config.mjs";

const DAY = 86_400_000;
const STALE_LOCK_MS = 60_000;

export function renewDue(credential, now = Date.now()) {
  if (!credential?.expires_at) return false;
  const from = credential.renew_after
    ? Date.parse(credential.renew_after)
    : Date.parse(credential.expires_at) - RENEW_WINDOW_DAYS * DAY;
  return now >= from;
}

/** La credencial que guarda el cliente, a partir de la respuesta del servidor. */
export function credentialFromResponse(body, cloudApi) {
  return {
    token: body.access_token,
    token_id: body.token_id,
    expires_at: body.expires_at,
    renew_after: body.renew_after ?? null,
    device_id: body.device?.device_id ?? null,
    device_name: body.device?.device_name ?? null,
    client: body.device?.client ?? null,
    developer: body.developer ?? null,
    cloud_api: cloudApi,
    updated_at: new Date().toISOString(),
  };
}

export function acquireLock(dir, now = Date.now) {
  const file = join(dir, "renew.lock");
  mkdirSync(dir, { recursive: true, mode: 0o700 });
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      closeSync(openSync(file, "wx"));
      return () => {
        try {
          unlinkSync(file);
        } catch {
          // ya no estaba
        }
      };
    } catch (err) {
      if (err?.code !== "EEXIST") return () => {};
      try {
        if (now() - statSync(file).mtimeMs > STALE_LOCK_MS) {
          unlinkSync(file); // cerrojo abandonado por un proceso que murió
          continue;
        }
      } catch {
        continue;
      }
      return null;
    }
  }
  return null;
}

async function fetchWithTimeout(fetchImpl, url, init, timeoutMs) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetchImpl(url, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Renueva `credential` si nadie lo está haciendo ya. Nunca lanza: devuelve la
 * credencial con la que seguir (la nueva, la que renovó otro proceso o la
 * misma si no se pudo).
 */
export async function renewCredential({
  store,
  account,
  credential,
  lockDir,
  fetchImpl = fetch,
  timeoutMs = 5_000,
  body = {},
}) {
  const release = acquireLock(lockDir);
  if (!release) return safeRead(store, account) ?? credential;
  try {
    const stored = safeRead(store, account);
    if (stored?.token && stored.token !== credential.token) return stored; // otro proceso ya renovó
    const res = await fetchWithTimeout(
      fetchImpl,
      `${credential.cloud_api}/devices/renew`,
      {
        method: "POST",
        headers: { authorization: `Bearer ${credential.token}`, "content-type": "application/json" },
        body: JSON.stringify(body),
      },
      timeoutMs,
    );
    if (res.status === 200) {
      const next = credentialFromResponse(await res.json(), credential.cloud_api);
      store.write(account, next);
      return next;
    }
    if (res.status === 409) return safeRead(store, account) ?? credential;
    return credential;
  } catch {
    return credential;
  } finally {
    release();
  }
}

function safeRead(store, account) {
  try {
    return store.read(account);
  } catch {
    return null;
  }
}
