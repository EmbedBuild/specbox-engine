"""Stitch Autopilot tools (v5.31.0).

Sits alongside ``server/tools/stitch.py`` rather than replacing it. The v1
tools stay registered for backwards compatibility; v2 tools layer the
DESIGN.md flow, prompt validation hooks, batched site build, fallback
chain, and quota tracking on top.

Phase 1+2 (this file as committed): :func:`generate_design_md` and
:func:`upload_design_md_to_stitch`. Phases 3-5 will register additional
tools in this same module.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import structlog
from fastmcp import Context, FastMCP

from ..design_md.generator import GeneratorInputs, generate_design_md
from ..design_md.io import compute_signature, load, save
from ..design_md.archetypes import ArchetypeId
from ..stitch_prompt import (
    PromptLayers,
    ValidatorMode,
    build_prompt,
    validate_and_normalize,
)

logger = structlog.get_logger(__name__)


def register_stitch_v2_tools(mcp: FastMCP, state_path: Path) -> None:
    """Register Stitch Autopilot tools on the MCP instance.

    The state_path is the same one used by ``register_stitch_tools`` —
    project metadata and telemetry live under ``state_path/projects/<slug>/``.
    """

    def _log_v2(project: str, tool: str, status: str = "ok", **extra) -> None:
        """Telemetry — best-effort write to ``stitch_usage.jsonl``."""

        try:
            log_dir = state_path / "projects" / project
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / "stitch_usage.jsonl"
            entry = {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "tool": tool,
                "status": status,
                **extra,
            }
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def _resolve_archetype(value: str | None) -> ArchetypeId | None:
        if not value:
            return None
        try:
            return ArchetypeId(value.strip().lower())
        except ValueError:
            return None

    @mcp.tool
    async def generate_design_md_tool(
        ctx: Context,
        project: str,
        project_root: str,
        project_name: str | None = None,
        output_path: str | None = None,
        archetype_override: str | None = None,
    ) -> dict:
        """Generate the canonical DESIGN.md for a project.

        Synthesises a DESIGN.md (Google Stitch's official format —
        github.com/google-labs-code/design.md) from existing SpecBox
        inputs: ``doc/brand/brand_kit.md``, ``doc/veg/*.md``, the canonical
        ``doc/app/app_prd.md`` + ``doc/app/app_spec.md``. Always produces
        a valid file; missing inputs fall back to the closest VEG
        archetype's defaults.

        Idempotent: rerunning regenerates the file. Stable signature
        across runs (excludes ``generated_at`` from the hash) so drift
        detection only triggers on real content changes.

        Args:
            project: SpecBox project slug (used for telemetry only).
            project_root: Absolute path to the project repo on disk.
            project_name: Display name (defaults to ``project``).
            output_path: Where to write DESIGN.md (defaults to
                ``{project_root}/doc/design/DESIGN.md``).
            archetype_override: One of corporate, startup, creative,
                consumer, gen_z, gov. If omitted, the generator detects
                from VEG file or defaults to startup.

        Returns:
            ``{status, path, signature, archetype, sections}`` on success;
            ``{error}`` on failure.
        """

        try:
            root = Path(project_root).expanduser().resolve()
            if not root.is_dir():
                _log_v2(project, "generate_design_md", status="error", reason="bad_root")
                return {"error": f"project_root does not exist: {project_root}"}

            out = (
                Path(output_path).expanduser().resolve()
                if output_path
                else root / "doc" / "design" / "DESIGN.md"
            )

            inputs = GeneratorInputs(
                project_root=root,
                project_name=project_name or project,
                brand_kit_path=root / "doc" / "brand" / "brand_kit.md",
                veg_path=_pick_veg_path(root),
                app_prd_path=root / "doc" / "app" / "app_prd.md",
                app_spec_path=root / "doc" / "app" / "app_spec.md",
                archetype_override=_resolve_archetype(archetype_override),
            )

            doc = generate_design_md(inputs)
            save(doc, out)
            sig = compute_signature(doc)

            # Persist signature in project meta so the sync layer can
            # detect drift between Brand Kit and DESIGN.md.
            _store_design_md_meta(state_path, project, out, sig, doc.front_matter.colors.primary)

            _log_v2(
                project,
                "generate_design_md",
                signature=sig,
                archetype=archetype_override or "auto",
                path=str(out),
            )

            return {
                "status": "ok",
                "project": project,
                "path": str(out),
                "signature": sig,
                "archetype": archetype_override or "auto",
                "sections": [
                    name
                    for name, body in (
                        ("overview", doc.overview),
                        ("colors", doc.colors_md),
                        ("typography", doc.typography_md),
                        ("layout", doc.layout),
                        ("elevation", doc.elevation),
                        ("shapes", doc.shapes),
                        ("components", doc.components_md),
                        ("dos_and_donts", doc.dos_and_donts),
                    )
                    if body and body.strip()
                ],
            }
        except Exception as exc:
            logger.error("generate_design_md_error", project=project, error=str(exc))
            _log_v2(project, "generate_design_md", status="error", reason=type(exc).__name__)
            return {"error": str(exc), "project": project}

    @mcp.tool
    async def upload_design_md_to_stitch(
        ctx: Context,
        project: str,
        stitch_project_id: str,
        design_md_path: str | None = None,
        project_root: str | None = None,
    ) -> dict:
        """Register DESIGN.md as the persistent context for a Stitch project.

        Google's Stitch MCP today does not expose a native endpoint to
        attach a DESIGN.md document to a project. Until that ships, this
        tool registers the file locally — subsequent Stitch generation
        calls (Phase 4 fallback chain, Phase 4 batched build_site) read
        the registered path and prefix the file content to every prompt.

        The behaviour upgrades transparently the day Google adds a native
        endpoint: ``stitch_client.upload_design_md`` will be implemented
        and called from here, and the prompt-prefix fallback removed.

        Args:
            project: SpecBox project slug.
            stitch_project_id: The target Stitch project ID.
            design_md_path: Path to DESIGN.md. Defaults to
                ``{project_root}/doc/design/DESIGN.md``.
            project_root: Project root, only needed if design_md_path is
                not provided.

        Returns:
            ``{status, mode, path, signature, stitch_project_id}``.
            ``mode`` is ``inline-prefix`` until a native endpoint exists.
        """

        try:
            if design_md_path:
                path = Path(design_md_path).expanduser().resolve()
            elif project_root:
                path = (
                    Path(project_root).expanduser().resolve()
                    / "doc" / "design" / "DESIGN.md"
                )
            else:
                return {
                    "error": "either design_md_path or project_root must be provided"
                }

            if not path.exists():
                return {"error": f"DESIGN.md not found at {path}"}

            doc = load(path)
            sig = compute_signature(doc)

            project_dir = state_path / "projects" / project
            project_dir.mkdir(parents=True, exist_ok=True)
            meta_file = project_dir / "meta.json"
            meta: dict = {}
            if meta_file.exists():
                try:
                    meta = json.loads(meta_file.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    meta = {}

            meta["design_md"] = {
                "path": str(path),
                "signature": sig,
                "stitch_project_id": stitch_project_id,
                "registered_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "mode": "inline-prefix",
            }
            meta_file.write_text(
                json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
            )

            _log_v2(
                project,
                "upload_design_md",
                stitch_project_id=stitch_project_id,
                signature=sig,
                mode="inline-prefix",
            )

            return {
                "status": "ok",
                "project": project,
                "stitch_project_id": stitch_project_id,
                "path": str(path),
                "signature": sig,
                "mode": "inline-prefix",
                "note": (
                    "Stitch MCP has no native DESIGN.md attachment endpoint yet. "
                    "Future Stitch generations will prefix the DESIGN.md content "
                    "to each prompt automatically."
                ),
            }
        except Exception as exc:
            logger.error(
                "upload_design_md_error", project=project, error=str(exc)
            )
            _log_v2(
                project,
                "upload_design_md",
                status="error",
                reason=type(exc).__name__,
            )
            return {"error": str(exc), "project": project}


    @mcp.tool
    async def validate_stitch_prompt(
        ctx: Context,
        project: str,
        prompt: str,
        mode: str = "warn",
        project_root: str | None = None,
    ) -> dict:
        """Validate a Stitch prompt against the v5.31.0 best-practice rules.

        Detects:
          E1 named colors without hex equivalents
          E2 prompts mixing layout + component changes (proposes split)
          W1 prompt body >500 chars (excluding DESIGN.md prefix)
          W2 Layer 1 (CONTEXT) >80 words
          W3 Layer 2 (COMPONENTS) written as prose instead of bullets
          W4 named colors auto-resolved against DESIGN.md palette

        Args:
            project: SpecBox project slug.
            prompt: The full prompt string to validate.
            mode: 'warn' (default — issues reported, prompt still allowed)
                or 'strict' (errors set valid=False).
            project_root: If provided, the validator loads
                ``{project_root}/doc/design/DESIGN.md`` and uses its
                palette to auto-resolve named colors.

        Returns:
            ``{status, valid, normalized_prompt, warnings, errors,
              requires_split, split_prompts, color_substitutions}``.
        """

        try:
            try:
                vmode = ValidatorMode(mode.lower())
            except ValueError:
                return {"error": f"unknown mode {mode!r}; expected 'warn' or 'strict'"}

            palette = None
            if project_root:
                design_md_path = (
                    Path(project_root).expanduser().resolve()
                    / "doc" / "design" / "DESIGN.md"
                )
                if design_md_path.exists():
                    try:
                        doc = load(design_md_path)
                        palette = doc.front_matter.colors
                    except Exception as exc:
                        logger.warning(
                            "validate_stitch_prompt_palette_load_failed",
                            project=project,
                            error=str(exc),
                        )

            result = validate_and_normalize(prompt, palette=palette, mode=vmode)

            _log_v2(
                project,
                "validate_stitch_prompt",
                valid=result.valid,
                error_count=len(result.errors),
                warning_count=len(result.warnings),
                requires_split=result.requires_split,
            )

            return {
                "status": "ok",
                "project": project,
                "valid": result.valid,
                "normalized_prompt": result.normalized_prompt,
                "warnings": result.warnings,
                "errors": result.errors,
                "requires_split": result.requires_split,
                "split_prompts": result.split_prompts,
                "color_substitutions": result.color_substitutions,
                "char_count": result.char_count_excluding_design_md,
            }
        except Exception as exc:
            logger.error("validate_stitch_prompt_error", project=project, error=str(exc))
            _log_v2(
                project,
                "validate_stitch_prompt",
                status="error",
                reason=type(exc).__name__,
            )
            return {"error": str(exc), "project": project}

# ── Internal helpers (module-private, importable from later phases) ────


def _pick_veg_path(root: Path) -> Path | None:
    """Locate the most recent VEG file under ``doc/veg/``.

    Layout:
        doc/veg/{global,feature_X}/veg.md  — current convention
        doc/veg/global.md                  — older flat layout

    Returns the chosen Path or None if no VEG exists.
    """

    veg_root = root / "doc" / "veg"
    if not veg_root.is_dir():
        return None

    candidates: list[Path] = []
    for p in veg_root.rglob("*.md"):
        if p.is_file():
            candidates.append(p)
    if not candidates:
        return None

    # Prefer "global.md" if it exists, else the most-recently-modified file.
    for c in candidates:
        if c.name.lower() in {"global.md", "veg.md"} and c.parent.name.lower() in {"global", "veg"}:
            return c
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _store_design_md_meta(
    state_path: Path,
    project: str,
    output_path: Path,
    signature: str,
    primary_color: str,
) -> None:
    """Persist DESIGN.md provenance in ``meta.json`` (idempotent)."""

    project_dir = state_path / "projects" / project
    project_dir.mkdir(parents=True, exist_ok=True)
    meta_file = project_dir / "meta.json"
    meta: dict = {}
    if meta_file.exists():
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            meta = {}

    existing = meta.get("design_md", {})
    meta["design_md"] = {
        **existing,
        "path": str(output_path),
        "signature": signature,
        "primary_color": primary_color,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    meta_file.write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )
