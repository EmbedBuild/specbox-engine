# Runbook — GitHub OAuth troubleshooting

> Audience: developers hitting a failure in the `SpecBox: Sign in with
> GitHub` flow. Covers the common error modes and how to recover.

## Quick diagnosis

| Symptom | Likely cause | Fix |
|---|---|---|
| Notification: "Sign-in failed: timeout" | Browser tab closed before completing OAuth, or the cloud took longer than 5 minutes. | Run `SpecBox: Sign in with GitHub` again. |
| Notification: "Sign-in failed: browser_blocked" | `vscode.env.openExternal` returned `false`. Usually a browser blocker or remote dev environment without a default browser. | Copy the URL the extension logged to the Output panel and open it manually. The callback will still reach the loopback if you keep the VSCode window open. |
| Notification: "Sign-in failed: state_mismatch" | The browser returned with a CSRF state that does not match the one this extension issued. Could be a cross-extension collision or a stale tab. | Run the command again. If it persists, file an issue with the URL the browser ended up on. |
| Notification: "Sign-in failed: access_denied" | You rejected the GitHub consent screen. | Run again and accept. |
| Notification: "Sign-in failed: invalid_token_shape" | The cloud returned something that is not a 64-hex token. Usually a deploy in flight. | Wait a minute and retry. If it persists, the cloud has a bug — file an issue. |
| Sidebar still says "Not signed in" after a successful sign-in | The MCP server config update did not propagate. | Run `Developer: Reload Window`. |
| `whoami` returns `UNAUTHENTICATED` immediately after sign-in | The MCP server respawn failed silently. | Open the Output panel → `SpecBox Engine` channel and look for a launcher error. Reload the window. |

## Verifying the secret on each platform

The token is stored under the key `specbox.mcpToken` in VSCode SecretStorage.

- **macOS** — Open Keychain Access → search "vscode" → look for the secret
  scoped to your VSCode profile.
- **Windows** — Open Credential Manager → Windows Credentials → look for a
  generic credential under `vscode-EmbedBuild.specbox-engine`.
- **Linux** — `secret-tool search` against the libsecret default keyring:
  ```
  secret-tool search service vscode
  ```

You should see one entry per workspace where you signed in. The value
itself is never displayed in the UI.

## Forcing a sign-out

```
Command Palette → SpecBox: Sign out
```

If the command fails (rare), wipe by hand:

```bash
# macOS:
security delete-generic-password -s "vscode" -a "EmbedBuild.specbox-engine.specbox.mcpToken"
# Windows (PowerShell):
cmdkey /delete:vscode-EmbedBuild.specbox-engine
# Linux:
secret-tool clear service vscode account EmbedBuild.specbox-engine.specbox.mcpToken
```

Then `Developer: Reload Window`.

## What the engine logs

`.quality/logs/onboarding.jsonl` (per workspace) — every onboarding-gate
event, including `dismissed_without_decision`. No PII; only a SHA-256 hash
of the workspace URI.

`.quality/logs/mcp-handshake.jsonl` (per workspace) — every handshake
attempt and its outcome. The token is never logged.

## When to file an issue

If a sign-in attempt fails with the same error twice in a row and none of
the fixes above apply, file an issue at
[EmbedBuild/specbox-engine/issues](https://github.com/EmbedBuild/specbox-engine/issues)
with:

- The error code/message from the notification.
- The contents of `.quality/logs/onboarding.jsonl` for the workspace.
- Your VSCode version (`Help → About`) and OS.
