"""Load embed.build brand tokens from the `embed-build-brand` skill.

Graceful fallback: if the skill is not installed or malformed, return
defaults (black background + cyan #29F3E3) and add a warning to the report.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class BrandConfig:
    name: str = "embed.build (fallback)"
    primary_color: str = "#29F3E3"   # cyan
    background_color: str = "#000000"  # black
    text_color: str = "#FFFFFF"
    accent_color: str = "#29F3E3"
    font_family: str = "Helvetica"
    logo_path: str | None = None
    source: str = "fallback"  # "skill" when loaded from embed-build-brand
    warning: str | None = "embed-build-brand skill not found — using defaults"


def load_brand(engine_path: Path | None = None) -> BrandConfig:
    """Best-effort load of the embed-build-brand skill.

    Search order:
    1. ~/.claude/skills/embed-build-brand/brand.yaml
    2. <engine>/.claude/skills/embed-build-brand/brand.yaml
    3. Fallback defaults.
    """
    candidates: list[Path] = []
    home_skill = Path.home() / ".claude" / "skills" / "embed-build-brand"
    candidates.append(home_skill / "brand.yaml")
    candidates.append(home_skill / "SKILL.md")
    if engine_path:
        repo_skill = engine_path / ".claude" / "skills" / "embed-build-brand"
        candidates.append(repo_skill / "brand.yaml")
        candidates.append(repo_skill / "SKILL.md")

    for p in candidates:
        if not p.exists():
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue

        cfg = BrandConfig(source=f"skill:{p}")
        cfg.warning = None
        # Minimal YAML-ish parsing — avoid hard dep on PyYAML here
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("primary_color:"):
                cfg.primary_color = line.split(":", 1)[1].strip().strip('"').strip("'")
            elif line.startswith("background_color:"):
                cfg.background_color = line.split(":", 1)[1].strip().strip('"').strip("'")
            elif line.startswith("text_color:"):
                cfg.text_color = line.split(":", 1)[1].strip().strip('"').strip("'")
            elif line.startswith("accent_color:"):
                cfg.accent_color = line.split(":", 1)[1].strip().strip('"').strip("'")
            elif line.startswith("font_family:"):
                cfg.font_family = line.split(":", 1)[1].strip().strip('"').strip("'")
            elif line.startswith("logo_path:"):
                cfg.logo_path = line.split(":", 1)[1].strip().strip('"').strip("'")
            elif line.startswith("name:"):
                cfg.name = line.split(":", 1)[1].strip().strip('"').strip("'")
        return cfg

    return BrandConfig()
