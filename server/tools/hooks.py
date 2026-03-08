"""Tools for querying the engine's hook system and configuration."""

import json
from pathlib import Path
from fastmcp import FastMCP


def register_hook_tools(mcp: FastMCP, engine_path: Path):

    @mcp.tool
    def list_hooks() -> list[dict]:
        """List all hooks installed in the engine with their purpose and status.
        Returns hook filename, type (automatic vs manual), blocking status,
        trigger event, and file size. Use to understand what automatic
        enforcement the engine provides."""
        hooks_dir = engine_path / ".claude" / "hooks"
        if not hooks_dir.exists():
            return []

        # Read settings.json to know which hooks are wired automatically
        settings_file = engine_path / ".claude" / "settings.json"
        auto_hooks: set[str] = set()
        if settings_file.exists():
            try:
                with open(settings_file) as f:
                    settings = json.load(f)
                for event_type, event_hooks in settings.get("hooks", {}).items():
                    if isinstance(event_hooks, list):
                        for hook_group in event_hooks:
                            for hook in hook_group.get("hooks", []):
                                cmd = hook.get("command", "")
                                # Extract filename from path
                                auto_hooks.add(cmd.split("/")[-1])
            except (json.JSONDecodeError, KeyError):
                pass

        hooks = []
        for f in sorted(hooks_dir.glob("*.sh")):
            is_auto = f.name in auto_hooks
            content = f.read_text(encoding="utf-8")

            # Extract description from first comment line
            desc = ""
            for line in content.splitlines():
                if line.startswith("# Hook:") or line.startswith("# Hook helper:"):
                    desc = line.lstrip("# ").replace("Hook:", "").replace("Hook helper:", "").strip()
                    break

            # Detect if blocking
            blocking = False
            if is_auto:
                try:
                    with open(settings_file) as sf:
                        s = json.load(sf)
                    for et, ehs in s.get("hooks", {}).items():
                        if isinstance(ehs, list):
                            for hg in ehs:
                                for h in hg.get("hooks", []):
                                    if f.name in h.get("command", ""):
                                        blocking = h.get("blocking", False)
                except Exception:
                    pass

            hooks.append({
                "name": f.name,
                "description": desc,
                "type": "automatic" if is_auto else "manual",
                "blocking": blocking if is_auto else None,
                "size_bytes": f.stat().st_size,
                "path": str(f),
            })

        return hooks

    @mcp.tool
    def get_hook_config() -> dict:
        """Get the full hooks configuration from .claude/settings.json.
        Returns the parsed settings with hook event types (PostToolUse, Stop),
        matchers, commands, blocking status, and timeouts.
        Use to understand what automatic enforcement is active."""
        settings_file = engine_path / ".claude" / "settings.json"
        if not settings_file.exists():
            return {"error": "No .claude/settings.json found"}

        try:
            with open(settings_file) as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            return {"error": f"Invalid JSON in settings.json: {e}"}

    @mcp.tool
    def get_hook_source(hook_name: str) -> dict:
        """Read the source code of a specific hook script.
        Args:
            hook_name: Filename of the hook (e.g. 'pre-commit-lint.sh').
        Returns the full script content, description, and metadata.
        Use to understand exactly what a hook does or to debug hook behavior."""
        hooks_dir = engine_path / ".claude" / "hooks"
        hook_file = hooks_dir / hook_name

        if not hook_file.exists():
            # Try without .sh
            hook_file = hooks_dir / f"{hook_name}.sh"
        if not hook_file.exists():
            available = [f.name for f in hooks_dir.glob("*.sh")] if hooks_dir.exists() else []
            return {"error": f"Hook '{hook_name}' not found", "available": available}

        content = hook_file.read_text(encoding="utf-8")
        return {
            "name": hook_file.name,
            "content": content,
            "lines": len(content.splitlines()),
            "executable": hook_file.stat().st_mode & 0o111 != 0,
        }
