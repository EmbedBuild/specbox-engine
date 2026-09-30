/**
 * Textos de `specbox` en español e inglés, según el idioma del sistema
 * (LC_ALL, LC_MESSAGES o LANG empezando por "es" → español).
 */
export function pickLang(env = process.env) {
  const raw = env.LC_ALL || env.LC_MESSAGES || env.LANG || "";
  return raw.toLowerCase().startsWith("es") ? "es" : "en";
}

const STORE_LABEL = {
  es: { keychain: "Llavero de macOS", "secret-service": "Secret Service", dpapi: "DPAPI de Windows", file: "fichero protegido (~/.specbox, 0600)" },
  en: { keychain: "macOS Keychain", "secret-service": "Secret Service", dpapi: "Windows DPAPI", file: "protected file (~/.specbox, 0600)" },
};

function day(iso, lang) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString(lang === "es" ? "es-ES" : "en-GB", { day: "numeric", month: "long", year: "numeric" });
}

export function messages(lang) {
  const es = lang === "es";
  return {
    usage: es
      ? [
          "Uso: specbox <orden> [opciones]",
          "",
          "Órdenes:",
          "  login    conecta este ordenador a SpecBox con tu cuenta de GitHub",
          "  status   enseña con qué cuenta y dispositivo estás conectado",
          "  logout   desconecta este ordenador",
          "",
          "Opciones:",
          "  --server <url>   servidor MCP (por defecto el de SpecBox)",
          "  --cloud <url>    API del panel",
          "  --no-browser     no abrir el navegador",
          "  --version, --help",
        ].join("\n")
      : [
          "Usage: specbox <command> [options]",
          "",
          "Commands:",
          "  login    connect this computer to SpecBox with your GitHub account",
          "  status   show which account and device you are connected with",
          "  logout   disconnect this computer",
          "",
          "Options:",
          "  --server <url>   MCP server (SpecBox's by default)",
          "  --cloud <url>    panel API",
          "  --no-browser     do not open the browser",
          "  --version, --help",
        ].join("\n"),
    loginTitle: es ? "SpecBox · conectar este ordenador" : "SpecBox · connect this computer",
    openUrl: (url) => (es ? `  1. Abre esta dirección (se abre sola si puede):\n     ${url}` : `  1. Open this address (it opens by itself if it can):\n     ${url}`),
    confirmCode: (code) =>
      es
        ? `  2. Comprueba que el código es este y confírmalo con tu cuenta de GitHub:\n     ${code}`
        : `  2. Check that the code is this one and confirm it with your GitHub account:\n     ${code}`,
    waiting: (minutes) => (es ? `\nEsperando la confirmación… (el código caduca en ${minutes} min)` : `\nWaiting for the confirmation… (the code expires in ${minutes} min)`),
    connected: (cred, storeKind) => {
      const who = cred.developer?.handle ? `@${cred.developer.handle}` : cred.developer?.display_name ?? "?";
      return es
        ? `\n✓ Conectado como ${who} en «${cred.device_name}».\n  El token está en el ${STORE_LABEL.es[storeKind] ?? storeKind}; caduca el ${day(cred.expires_at, "es")} y se renueva solo.`
        : `\n✓ Connected as ${who} on “${cred.device_name}”.\n  The token is in the ${STORE_LABEL.en[storeKind] ?? storeKind}; it expires on ${day(cred.expires_at, "en")} and renews itself.`;
    },
    fileStoreWarning: es
      ? "  ⚠ No hay almacén seguro del sistema disponible: el token queda en ~/.specbox/credentials.json con permisos 0600."
      : "  ⚠ No system secure store is available: the token is kept in ~/.specbox/credentials.json with 0600 permissions.",
    claudeConfigured: (updated) =>
      es
        ? `✓ Claude Code configurado: ${updated.map((u) => (u.cwd ? `${u.name} (${u.cwd})` : u.name)).join(", ")} envía el token en cada conexión.\n  Reinicia Claude Code (o /mcp → reconectar) para usarlo ya.`
        : `✓ Claude Code configured: ${updated.map((u) => (u.cwd ? `${u.name} (${u.cwd})` : u.name)).join(", ")} sends the token on every connection.\n  Restart Claude Code (or /mcp → reconnect) to use it now.`,
    claudeFailed: (failed) =>
      es
        ? `  ⚠ No se pudo actualizar: ${failed.map((f) => `${f.name} (${f.cwd ?? "usuario"})`).join(", ")}.`
        : `  ⚠ Could not update: ${failed.map((f) => `${f.name} (${f.cwd ?? "user"})`).join(", ")}.`,
    claudeManual: (cmd) =>
      es
        ? `  ⚠ No encuentro la orden \`claude\`. Configura Claude Code con:\n     ${cmd}`
        : `  ⚠ The \`claude\` command was not found. Configure Claude Code with:\n     ${cmd}`,
    howItWorks: (url) => (es ? `\nCómo funciona: ${url}` : `\nHow it works: ${url}`),
    loginError: (code) =>
      ({
        denied: es ? "✗ Cancelado en el navegador: el ordenador no se ha conectado." : "✗ Cancelled in the browser: this computer was not connected.",
        expired: es ? "✗ El código caducó antes de confirmarse. Ejecuta specbox login otra vez." : "✗ The code expired before it was confirmed. Run specbox login again.",
        rate_limited: es ? "✗ Demasiados intentos seguidos. Espera unos minutos." : "✗ Too many attempts in a row. Wait a few minutes.",
        network: es ? "✗ No hay conexión con el panel de SpecBox." : "✗ Cannot reach the SpecBox panel.",
        device_limit: es
          ? "✗ Tu cuenta ya tiene 5 dispositivos conectados. Desconecta uno en https://cloud.specbox.build/profile y ejecuta specbox login otra vez."
          : "✗ Your account already has 5 connected devices. Disconnect one at https://cloud.specbox.build/profile and run specbox login again.",
      })[code] ?? (es ? `✗ No se pudo conectar (${code}).` : `✗ Could not connect (${code}).`),
    notConnected: es ? "Este ordenador no está conectado. Ejecuta: specbox login" : "This computer is not connected. Run: specbox login",
    statusTitle: es ? "SpecBox · este ordenador" : "SpecBox · this computer",
    statusLines: (cred, storeKind, server, valid, helper) => {
      const who = cred.developer?.handle ? `@${cred.developer.handle} (${cred.developer.display_name})` : cred.developer?.display_name ?? "?";
      const state =
        valid === null
          ? es ? "sin comprobar (no hay conexión con el panel)" : "not checked (cannot reach the panel)"
          : valid
            ? es ? "válido ✓" : "valid ✓"
            : es ? "caducado o revocado ✗ → ejecuta specbox login" : "expired or revoked ✗ → run specbox login";
      return (es
        ? [
            `  Cuenta:       ${who}`,
            `  Dispositivo:  ${cred.device_name}`,
            `  Caduca:       ${day(cred.expires_at, "es")} (se renueva sola desde el ${day(cred.renew_after, "es")})`,
            `  Almacén:      ${STORE_LABEL.es[storeKind] ?? storeKind}`,
            `  Servidor:     ${server}`,
            `  Token:        ${state}`,
            `  Claude Code:  ${helper ? "usa el ayudante ✓" : "sin configurar ✗ → ejecuta specbox login"}`,
          ]
        : [
            `  Account:      ${who}`,
            `  Device:       ${cred.device_name}`,
            `  Expires:      ${day(cred.expires_at, "en")} (renews itself from ${day(cred.renew_after, "en")})`,
            `  Store:        ${STORE_LABEL.en[storeKind] ?? storeKind}`,
            `  Server:       ${server}`,
            `  Token:        ${state}`,
            `  Claude Code:  ${helper ? "uses the helper ✓" : "not configured ✗ → run specbox login"}`,
          ]
      ).join("\n");
    },
    loggedOut: (name, remote) =>
      es
        ? `✓ Dispositivo desconectado: «${name}».${remote ? "" : "\n  ⚠ No se pudo avisar al panel: desconéctalo también en Perfil → Dispositivos conectados."}\n  Claude Code seguirá configurado y se conectará sin cuenta hasta que vuelvas a ejecutar specbox login.`
        : `✓ Device disconnected: “${name}”.${remote ? "" : "\n  ⚠ The panel could not be told: disconnect it also in Profile → Connected devices."}\n  Claude Code stays configured and connects without an account until you run specbox login again.`,
  };
}
