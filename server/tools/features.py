"""Tools para consultar definiciones de agentes, Agent Teams, y docs de arquitectura."""

from pathlib import Path
from fastmcp import FastMCP


def register_feature_tools(mcp: FastMCP, engine_path: Path):

    @mcp.tool
    def list_agent_definitions() -> list[dict]:
        """List all agent definitions in the engine (AG-01 through AG-08).
        Returns agent filename, title, and description excerpt.
        Use to understand the multi-agent system and which agent handles what."""
        agents_dir = engine_path / "agents"
        if not agents_dir.exists():
            return []

        agents = []
        for f in sorted(agents_dir.glob("*.md")):
            content = f.read_text(encoding="utf-8")
            lines = content.strip().splitlines()
            title = lines[0].lstrip("# ") if lines else f.stem
            desc = ""
            for line in lines[1:]:
                if line.strip():
                    desc = line.strip()
                    break

            agents.append({
                "filename": f.name,
                "title": title,
                "description": desc[:200],
                "path": str(f),
            })
        return agents

    @mcp.tool
    def get_agent_teams_config() -> dict:
        """Get the Agent Teams configuration for Claude Code native multi-agent teams.
        Returns README excerpt, available templates, role prompts, and hooks.
        Use when setting up or auditing multi-agent coordination."""
        teams_dir = engine_path / "agent-teams"
        if not teams_dir.exists():
            return {"error": "agent-teams directory not found"}

        config = {"readme": "", "templates": [], "prompts": [], "hooks": []}

        readme = teams_dir / "README.md"
        if readme.exists():
            config["readme"] = readme.read_text(encoding="utf-8")[:3000]

        for subdir_name in ("templates", "prompts", "hooks"):
            subdir = teams_dir / subdir_name
            if subdir.exists():
                config[subdir_name] = [f.name for f in subdir.iterdir() if f.is_file()]

        return config

    @mcp.tool
    def get_architecture_doc(stack: str, doc_type: str = "overview") -> dict:
        """Read architecture documentation for a specific technology stack.
        Args:
            stack: Technology stack name (flutter, react, python, gas).
            doc_type: Document type (overview, folder-structure, patterns, testing-strategy).
        Returns document content and metadata.
        Use when you need architecture guidance for implementing in a specific stack."""
        doc_file = engine_path / "architecture" / stack / f"{doc_type}.md"
        if not doc_file.exists():
            stack_dir = engine_path / "architecture" / stack
            available_docs = [f.stem for f in stack_dir.glob("*.md")] if stack_dir.exists() else []
            available_stacks = []
            arch_dir = engine_path / "architecture"
            if arch_dir.exists():
                available_stacks = [d.name for d in arch_dir.iterdir() if d.is_dir()]
            return {
                "error": f"Doc '{doc_type}' not found for stack '{stack}'",
                "available_docs": available_docs,
                "available_stacks": available_stacks,
            }

        content = doc_file.read_text(encoding="utf-8")
        return {
            "stack": stack,
            "doc_type": doc_type,
            "content": content,
            "lines": len(content.splitlines()),
        }

    @mcp.tool
    def get_infra_doc(service: str) -> dict:
        """Read infrastructure documentation for a specific service.
        Args:
            service: Service name (supabase, neon, stripe, firebase, n8n).
        Returns all markdown files content for that service.
        Use when you need infrastructure setup guidance or integration patterns."""
        infra_dir = engine_path / "infra" / service
        if not infra_dir.exists():
            available = []
            parent = engine_path / "infra"
            if parent.exists():
                available = [d.name for d in parent.iterdir() if d.is_dir()]
            return {"error": f"Infra '{service}' not found", "available": available}

        docs = {}
        for f in infra_dir.glob("*.md"):
            docs[f.name] = f.read_text(encoding="utf-8")[:5000]

        return {
            "service": service,
            "docs": docs,
            "file_count": len(docs),
        }

    @mcp.tool
    def read_agent_prompt(role_name: str) -> dict:
        """Read the full Agent Teams prompt for a specific role.
        Args:
            role_name: Role filename without .md (e.g. 'lead-agent', 'flutter-specialist', 'qa-reviewer').
        Returns the complete prompt content that defines the agent's behavior in Agent Teams.
        Use to review what instructions a specific teammate receives."""
        prompts_dir = engine_path / "agent-teams" / "prompts"
        if not prompts_dir.exists():
            return {"error": "agent-teams/prompts directory not found"}

        prompt_file = prompts_dir / f"{role_name}.md"
        if not prompt_file.exists():
            # Try fuzzy match
            matches = [f for f in prompts_dir.glob("*.md") if role_name.lower() in f.stem.lower()]
            if matches:
                prompt_file = matches[0]
            else:
                available = [f.stem for f in prompts_dir.glob("*.md")]
                return {"error": f"Prompt '{role_name}' not found", "available": available}

        content = prompt_file.read_text(encoding="utf-8")
        title = ""
        for line in content.splitlines():
            if line.startswith("# "):
                title = line.lstrip("# ").strip()
                break

        return {
            "role": prompt_file.stem,
            "title": title,
            "content": content,
            "lines": len(content.splitlines()),
            "has_engine_integration": "Engine" in content and ("v3" in content or "Skills" in content),
        }

    @mcp.tool
    def get_global_rules() -> dict:
        """Get the global rules that apply to ALL projects managed by the engine.
        Returns the full GLOBAL_RULES.md content with sections: identity, universal rules,
        per-stack rules, quality gates, testing requirements, and feature checklist.
        Use to understand the coding standards and policies enforced across all projects."""
        rules_file = engine_path / "rules" / "GLOBAL_RULES.md"
        if not rules_file.exists():
            return {"error": "GLOBAL_RULES.md not found"}

        content = rules_file.read_text(encoding="utf-8")

        # Extract sections
        sections = []
        for line in content.splitlines():
            if line.startswith("## "):
                sections.append(line.lstrip("# ").strip())

        return {
            "content": content,
            "lines": len(content.splitlines()),
            "sections": sections,
        }
