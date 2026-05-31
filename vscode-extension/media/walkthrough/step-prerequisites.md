## Prerequisites

SpecBox Engine needs these tools to work:

| Tool | Required | Why |
|------|----------|-----|
| **Node.js 18+** | Yes | Runs hooks and quality scripts |
| **Claude Code** | Yes | The AI coding assistant SpecBox enhances |
| **Engram** | Yes | Persistent memory — native binary, installed via Homebrew |
| **GGA** | Optional | Cached lint for faster quality checks |

> The SpecBox MCP server runs on a free hosted endpoint — there is nothing to
> install locally for it. All 110 tools work out of the box.

> **No manual `git clone` needed.** When the extension can't find the engine
> repo on your machine, it clones the public engine for you automatically into a
> managed folder (`~/.specbox/specbox-engine`) and keeps it up to date. You only
> pick a folder manually if that automatic clone fails.

SpecBox **checks these prerequisites automatically on startup**. If a critical
one is missing (Claude Code, Engram, Node, or the MCP servers), you'll get a
clear warning that SpecBox may not work correctly, with one-click fixes. You can
re-check any time with **SpecBox: Check Prerequisites** from the Command Palette.

Click **Run Health Check** to see what's installed and what's missing.
