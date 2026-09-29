/**
 * `specbox login` — conectar este ordenador con un código de un solo uso
 * (UC-3904 AC-02), gestionado por el panel de SpecBox:
 *
 *   1. POST {cloud}/device/code con el dispositivo → código y enlace.
 *   2. La persona abre el enlace, entra con GitHub y confirma el código.
 *   3. Mientras, se pregunta a POST {cloud}/device/token cada `interval`
 *      segundos (más 5 con cada `slow_down`) hasta recibir el token, que va
 *      directo al almacén seguro: nadie lo ve ni lo copia.
 */
import { credentialFromResponse } from "./renew.mjs";

export class LoginError extends Error {
  constructor(code, detail) {
    super(detail ? `${code}: ${detail}` : code);
    this.code = code;
  }
}

async function postJson(fetchImpl, url, body) {
  const res = await fetchImpl(url, {
    method: "POST",
    headers: { "content-type": "application/json", accept: "application/json" },
    body: JSON.stringify(body),
  });
  let json = {};
  try {
    json = await res.json();
  } catch {
    // cuerpo vacío o no JSON
  }
  return { status: res.status, json };
}

/**
 * Pide el código, avisa (`onCode`) y espera la confirmación. Devuelve la
 * credencial ya guardada en `store` bajo `account`.
 */
export async function deviceLogin({
  cloudApi,
  account,
  store,
  device,
  onCode,
  fetchImpl = fetch,
  sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
  now = Date.now,
}) {
  let code;
  try {
    code = await postJson(fetchImpl, `${cloudApi}/device/code`, device);
  } catch (err) {
    throw new LoginError("network", err?.message);
  }
  if (code.status !== 200 || !code.json.device_code) {
    throw new LoginError(code.status === 429 ? "rate_limited" : "code_failed", code.json.error_description ?? code.json.message);
  }
  const { device_code: deviceCode, expires_in: expiresIn = 600 } = code.json;
  let interval = Math.max(1, Number(code.json.interval) || 5);
  await onCode?.(code.json);

  const deadline = now() + expiresIn * 1000;
  while (now() < deadline) {
    await sleep(interval * 1000);
    let res;
    try {
      res = await postJson(fetchImpl, `${cloudApi}/device/token`, { device_code: deviceCode });
    } catch {
      continue; // un corte de red momentáneo: se vuelve a preguntar
    }
    if (res.status === 200 && res.json.access_token) {
      const credential = credentialFromResponse(res.json, cloudApi);
      store.write(account, credential);
      return credential;
    }
    const error = res.json.error;
    if (error === "authorization_pending") continue;
    if (error === "slow_down" || res.status === 429) {
      interval += 5;
      continue;
    }
    if (error === "access_denied") throw new LoginError("denied");
    if (error === "expired_token" || error === "invalid_grant") throw new LoginError("expired");
    throw new LoginError("unexpected", `HTTP ${res.status} ${error ?? ""}`.trim());
  }
  throw new LoginError("expired");
}
