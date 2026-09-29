# specbox

Connect this computer to [SpecBox](https://specbox.embed.build) without copying tokens.

```bash
npx specbox login
```

1. It shows a one-time code and opens `https://cloud.specbox.build/device`.
2. You sign in with GitHub and confirm the code.
3. Done: the token goes straight into your system's secure store, and Claude Code is configured to send it on every connection. You never see it or paste it.

The token expires after 90 days and **renews itself** from 14 days before. If a connection ever ends ("the connection from this device has ended"), run `specbox login` again.

## Commands

| Command | What it does |
|---|---|
| `specbox login` | Connects this computer (one device = this computer + Claude Code). Signing in again replaces the previous token of this device. |
| `specbox status` | Account, device, expiry date, whether the token is still valid and whether Claude Code uses it. |
| `specbox logout` | Disconnects this device in the panel and deletes the local credential. |

Options: `--no-browser` (just print the link), `--server <url>` and `--cloud <url>` for self-hosted servers (or `SPECBOX_MCP_URL` / `SPECBOX_CLOUD_API`).

## What it changes on your computer

- **Secure store:** the macOS Keychain, Secret Service on Linux (`secret-tool`) or Windows DPAPI. Without any of them (headless Linux), a `~/.specbox/credentials.json` file with `0600` permissions; `specbox login` says so.
- **`~/.specbox/bin/mcp-headers.mjs`:** a small helper. Claude Code runs it when it connects (and after a `401`) to get the `Authorization` header; it reads the store and renews the token when due. It never prints anything but that header.
- **Claude Code:** the `SpecBox-MCP` server (user scope) becomes `{"type": "http", "url": …, "headersHelper": "<node> ~/.specbox/bin/mcp-headers.mjs"}` through the official `claude mcp` command, and other entries pointing to the same server get the same helper.
- **`~/.specbox/device-id`:** only if the machine id cannot be read. The server only ever sees a SHA-256 of it.

Your devices are listed in the panel under **Profile → Connected devices**, where you can rename or disconnect them. For clients that cannot sign in (Cursor, Claude Desktop…), **Advanced** creates a manual token with the exact configuration for each client.

More: [How SpecBox connects](https://cloud.specbox.build/how-to-connect) · [Cómo se conecta SpecBox](https://cloud.specbox.build/como-se-conecta)

---

**En español.** `npx specbox login` conecta este ordenador: te muestra un código, lo confirmas en el navegador con tu cuenta de GitHub y el token queda en el almacén seguro del sistema; Claude Code lo envía solo y se renueva solo. `specbox status` dice con qué cuenta estás conectado y cuándo caduca; `specbox logout` desconecta el ordenador. Los mensajes salen en español si tu sistema está en español.
