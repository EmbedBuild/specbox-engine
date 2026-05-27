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
import re
import time
from pathlib import Path

import structlog
from fastmcp import Context, FastMCP

from ..auth_gateway import get_stitch_client
from ..design_md.generator import GeneratorInputs, generate_design_md
from ..design_md.io import compute_signature, load, save
from ..design_md.material3_view import build_material3_frontmatter
from ..design_md.archetypes import ArchetypeId
from ..stitch_orchestration import (
    FallbackOutcome,
    FallbackStrategy,
    ScreenSpec,
    build_site_batched,
    generate_screen_with_fallback,
)
from ..stitch_prompt import (
    PromptLayers,
    ValidatorMode,
    build_prompt,
    validate_and_normalize,
)
# Quota subsystem removed in v6.4.0. Stitch MCP is free of charge —
# the 350+200 monthly ceiling applies only to the Stitch web UI, not to
# the MCP/API surface. See doc/decisions/stitch_native_chain.md.

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
        contract: str = "native_v2",
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
            contract: ``"native_v2"`` (default, v6.4.0+) emits a
                Material 3 YAML frontmatter consumable by Stitch's
                ``create_design_system_from_design_md`` plus a ``VEG
                Notes`` body section preserving VEG semantics.
                ``"inline_prefix_v1"`` reproduces the v5.31 SpecBox-native
                frontmatter for backwards compatibility — projects still
                on that contract continue to work unchanged.

        Returns:
            ``{status, path, signature, archetype, contract, sections,
              material3}`` on success; ``{error}`` on failure.
            ``material3`` is the resolved theme payload (only when
            ``contract == "native_v2"``).
        """

        try:
            root = Path(project_root).expanduser().resolve()
            if not root.is_dir():
                _log_v2(project, "generate_design_md", status="error", reason="bad_root")
                return {"error": f"project_root does not exist: {project_root}"}

            if contract not in {"native_v2", "inline_prefix_v1"}:
                return {
                    "error": (
                        f"unknown contract {contract!r}. Use 'native_v2' or "
                        "'inline_prefix_v1'."
                    )
                }

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

            material3_payload: dict | None = None
            if contract == "native_v2":
                resolved_archetype = (
                    inputs.archetype_override or ArchetypeId.STARTUP
                )
                m3_fm = build_material3_frontmatter(doc, resolved_archetype)
                save(doc, out, material3=m3_fm)
                material3_payload = m3_fm.to_dict()
            else:
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
                contract=contract,
                path=str(out),
            )

            response: dict = {
                "status": "ok",
                "project": project,
                "path": str(out),
                "signature": sig,
                "archetype": archetype_override or "auto",
                "contract": contract,
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
            if material3_payload is not None:
                response["material3"] = material3_payload
            return response
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
    async def stitch_generate_screen_v2(
        ctx: Context,
        project: str,
        stitch_project_id: str,
        prompt: str,
        device_type: str = "DESKTOP",
        model_id: str = "GEMINI_3_PRO",
        baseline_screen_id: str | None = None,
        max_total_attempts: int = 3,
        contract: str = "native_v2",
        design_md_content: str | None = None,
    ) -> dict:
        """Generate a screen with the v5.31.0 fallback chain.

        Strategy ladder when the natural call fails:
            edit_baseline → variants_refine → regenerate

        Args:
            project: SpecBox project slug.
            stitch_project_id: Target Stitch project ID.
            prompt: The generation prompt (already validated upstream).
            device_type: DESKTOP|MOBILE|TABLET.
            model_id: Stitch model. Default GEMINI_3_PRO (per user
                preference for quality).
            baseline_screen_id: If a previous screen exists for this
                spot, supply its ID — it unlocks the EDIT_BASELINE and
                VARIANTS_REFINE strategies. Without it, the chain
                degrades to REGENERATE only.
            contract: ``"native_v2"`` (default) checks whether the
                project has a server-side Design System applied (via
                ``list_design_systems``) and, if so, **strips color /
                font / roundness directives from the prompt**. Stitch
                applies those server-side via the DS. ``"inline_prefix_v1"``
                preserves the v5.31 behaviour of prepending the full
                ``design_md_content`` to every prompt (legacy).
            design_md_content: When ``contract == "inline_prefix_v1"``,
                the DESIGN.md text to prepend. Ignored when contract is
                ``native_v2`` and a DS is detected.

        Returns:
            ``{status, outcome, final_strategy, model_used, attempts,
              degraded, degraded_reason, result, prompt_mode}``.
            ``prompt_mode`` is ``"design_system_applied"``,
            ``"design_system_missing"`` (native_v2 without applied DS,
            fallback to legacy prefix if available), or
            ``"inline_prefix"`` (legacy contract).

        Note: the v5.31 ``flash_safety_net`` parameter was removed in
        v6.4.0. Stitch MCP has no quota; degrading to Flash was a
        defensive measure for a constraint that does not exist.
        """

        if contract not in {"native_v2", "inline_prefix_v1"}:
            return {
                "error": (
                    f"unknown contract {contract!r}. Use 'native_v2' or "
                    "'inline_prefix_v1'."
                ),
                "project": project,
            }

        try:
            client = await _v2_get_client(ctx, project, state_path)

            # Resolve effective prompt + mode based on contract & DS state.
            effective_prompt, prompt_mode, ds_info = await _resolve_prompt_for_contract(
                client,
                stitch_project_id,
                prompt,
                contract=contract,
                design_md_content=design_md_content,
            )

            ops = _StitchOpsAdapter(client)
            result = await generate_screen_with_fallback(
                ops,
                stitch_project_id,
                effective_prompt,
                device_type=device_type,
                model_id=model_id,
                baseline_screen_id=baseline_screen_id,
                max_total_attempts=max_total_attempts,
            )

            _log_v2(
                project,
                "stitch_generate_screen_v2",
                outcome=result.outcome.value,
                final_strategy=result.final_strategy,
                model_used=result.model_used,
                degraded=result.degraded,
                attempt_count=len(result.attempts),
                contract=contract,
                prompt_mode=prompt_mode,
            )

            return {
                "status": "ok" if result.outcome != FallbackOutcome.FAILED else "error",
                "project": project,
                "outcome": result.outcome.value,
                "final_strategy": result.final_strategy,
                "model_used": result.model_used,
                "attempts": result.attempts,
                "degraded": result.degraded,
                "degraded_reason": result.degraded_reason,
                "result": result.result,
                "error": result.error,
                "contract": contract,
                "prompt_mode": prompt_mode,
                "design_system_info": ds_info,
            }
        except Exception as exc:
            logger.error(
                "stitch_generate_screen_v2_error", project=project, error=str(exc)
            )
            _log_v2(
                project,
                "stitch_generate_screen_v2",
                status="error",
                reason=type(exc).__name__,
            )
            return {"error": str(exc), "project": project}

    @mcp.tool
    async def stitch_build_site_batched_v2(
        ctx: Context,
        project: str,
        stitch_project_id: str,
        screens: list[dict],
        batch_size: int = 4,
        apply_unified_theme_pass: bool = True,
        unified_theme_prompt: str | None = None,
    ) -> dict:
        """Multi-screen build that auto-partitions when needed.

        Stitch's native ``build_site`` reliably handles up to ~5 connected
        screens; beyond that it tends to drift or fail. This wrapper
        partitions ``screens`` into groups of ≤``batch_size`` (preferring
        explicit groups, then route prefix, then order chunks) and
        applies a final pass that unifies the theme across all generated
        screens.

        Args:
            screens: list of dicts with ``name``, ``prompt``, optional
                ``route`` (default ``/``), ``order``, ``group``.
            batch_size: max screens per Stitch ``build_site`` call.
                Default 4.
            apply_unified_theme_pass: if True and the build needed >1
                batch, run a final ``edit_screens`` pass with
                ``unified_theme_prompt`` to align the visual language.
            unified_theme_prompt: override the default standardisation
                prompt (which references DESIGN.md component patterns).

        Returns:
            ``{status, total_screens, total_batches, batches[],
              unified_pass[], unified_pass_applied}``.
        """

        try:
            client = await _v2_get_client(ctx, project, state_path)
            ops = _StitchOpsAdapter(client)
            specs = [
                ScreenSpec(
                    name=s["name"],
                    prompt=s.get("prompt", ""),
                    route=s.get("route", "/"),
                    order=int(s.get("order", 0)),
                    group=s.get("group"),
                )
                for s in screens
            ]
            extra: dict = {}
            if unified_theme_prompt:
                extra["unified_theme_prompt"] = unified_theme_prompt
            result = await build_site_batched(
                ops,
                stitch_project_id,
                specs,
                batch_size=batch_size,
                apply_unified_theme_pass=apply_unified_theme_pass,
                **extra,
            )

            _log_v2(
                project,
                "stitch_build_site_batched_v2",
                total_screens=result["total_screens"],
                total_batches=result["total_batches"],
                unified_pass_applied=result["unified_pass_applied"],
            )

            return {
                "status": "ok",
                "project": project,
                "stitch_project_id": stitch_project_id,
                **result,
            }
        except Exception as exc:
            logger.error(
                "stitch_build_site_batched_v2_error",
                project=project,
                error=str(exc),
            )
            _log_v2(
                project,
                "stitch_build_site_batched_v2",
                status="error",
                reason=type(exc).__name__,
            )
            return {"error": str(exc), "project": project}

    # `get_stitch_quota_status` was removed in v6.4.0. The Stitch MCP/API
    # surface is free of charge — quota tracking only made sense for the
    # legacy assumption that 350+200 monthly ceilings applied to MCP
    # calls. They don't.

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

# ── Adapter to bridge real StitchClient → orchestration Protocol ──────


class _StitchOpsAdapter:
    """Adapt :class:`server.stitch_client.StitchClient` to the Protocol
    expected by ``stitch_orchestration``.

    Only renames are needed: the real client calls
    ``generate_screen_from_text`` whereas the orchestration Protocol
    expects ``generate_screen``.
    """

    def __init__(self, client) -> None:
        self._client = client

    async def generate_screen(
        self, project_id, prompt, *, device_type="DESKTOP", model_id="GEMINI_3_PRO"
    ):
        return await self._client.generate_screen_from_text(
            project_id, prompt, device_type=device_type, model_id=model_id
        )

    async def edit_screens(
        self, project_id, screen_id, prompt, *, device_type=None, model_id=None
    ):
        return await self._client.edit_screens(
            project_id, screen_id, prompt, device_type=device_type, model_id=model_id
        )

    async def generate_variants(
        self,
        project_id,
        screen_id,
        *,
        prompt=None,
        variant_count=1,
        creative_range="REFINE",
        aspects=None,
    ):
        return await self._client.generate_variants(
            project_id,
            screen_id,
            prompt=prompt,
            variant_count=variant_count,
            creative_range=creative_range,
            aspects=aspects,
        )

    # ``build_site`` deliberately omitted — the underlying MCP tool was
    # removed in v6.4.0 (ghost tool). Callers that need multi-page builds
    # should use ``stitch_build_site_batched_v2`` which chunks via
    # ``generate_screen`` + ``edit_screens`` instead.


async def _v2_get_client(ctx: Context, project: str, state_path: Path):
    """Resolve a StitchClient. Mirrors the v1 ``_get_client_for_project``
    fallback (session → meta.json on disk) so v1 and v2 share behaviour.
    """

    try:
        return await get_stitch_client(ctx, project)
    except RuntimeError:
        pass
    # Disk fallback (same shape as v1 _get_client_for_project)
    project_dir = state_path / "projects" / project
    meta_file = project_dir / "meta.json"
    if meta_file.exists():
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            key_b64 = meta.get("stitch_key_b64")
            if key_b64:
                import base64

                from ..auth_gateway import store_stitch_credentials

                api_key = base64.b64decode(key_b64).decode()
                await store_stitch_credentials(ctx, project, api_key)
                return await get_stitch_client(ctx, project)
        except (json.JSONDecodeError, OSError, ValueError):
            pass
    raise RuntimeError(
        f"No Stitch API Key configured for project '{project}'. "
        "Call stitch_set_api_key(project, api_key) first."
    )


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


# ── Contract-aware prompt resolution (v6.4.0) ─────────────────────────


# Heuristic patterns that strongly suggest a directive about colors,
# fonts or roundness — the directives Stitch applies server-side once a
# DS is bound. Matches are removed (line-level) so the resulting prompt
# focuses on layout + content only.
_THEME_DIRECTIVE_PATTERNS = (
    # Colors as hex
    re.compile(r"#[0-9A-Fa-f]{6}\b"),
    # Color tokens / named directives
    re.compile(
        r"\b(?:primary|secondary|tertiary|accent|background|surface|"
        r"foreground|on-?primary|on-?surface|color|colour|palette)\b\s*[:=]",
        re.IGNORECASE,
    ),
    # Typography directives
    re.compile(
        r"\b(?:font[_\- ]?family|font[_\- ]?size|font[_\- ]?weight|"
        r"line[_\- ]?height|letter[_\- ]?spacing|typography|typeface)\b",
        re.IGNORECASE,
    ),
    # Specific font names from the StitchFont enum (subset of common ones).
    re.compile(
        r"\b(?:Inter|Roboto|DM Sans|Space Grotesk|Playfair Display|Bebas Neue|"
        r"Geist|Manrope|Work Sans|Montserrat|IBM Plex|JetBrains Mono)\b",
        re.IGNORECASE,
    ),
    # Roundness directives
    re.compile(
        r"\b(?:rounded|border[_\- ]?radius|corner[_\- ]?radius|roundness)\b",
        re.IGNORECASE,
    ),
)


def _strip_theme_directives(prompt: str) -> tuple[str, list[str]]:
    """Remove lines containing theme directives from a prompt.

    Returns ``(cleaned_prompt, stripped_lines)``. The original line break
    structure of non-theme lines is preserved.

    Heuristic by design: false positives are acceptable (the prompt stays
    valid even with a couple of unnecessary line removals) but false
    negatives would defeat the purpose. We err on the side of stripping
    more than less. Callers that need full control can pre-clean their
    prompt and skip this step.
    """
    if not prompt:
        return prompt, []
    kept: list[str] = []
    stripped: list[str] = []
    for line in prompt.splitlines():
        if any(p.search(line) for p in _THEME_DIRECTIVE_PATTERNS):
            stripped.append(line)
        else:
            kept.append(line)
    return "\n".join(kept).strip(), stripped


async def _resolve_prompt_for_contract(
    client,
    stitch_project_id: str,
    prompt: str,
    *,
    contract: str,
    design_md_content: str | None,
) -> tuple[str, str, dict]:
    """Pick the right prompt shape based on contract + DS state.

    Returns ``(effective_prompt, prompt_mode, ds_info)`` where:
      * ``prompt_mode`` is one of:
        - ``"design_system_applied"`` — DS bound to project; prompt cleaned
        - ``"design_system_missing"`` — native_v2 but no DS bound; falls
          back to ``inline_prefix`` if ``design_md_content`` is provided,
          else passes the prompt as-is.
        - ``"inline_prefix"`` — legacy contract, DESIGN.md prepended.
      * ``ds_info`` is the resolved DS metadata when applicable, else ``{}``.
    """
    if contract == "inline_prefix_v1":
        if design_md_content:
            prefixed = f"# DESIGN SYSTEM (REQUIRED)\n{design_md_content}\n\n# Screen\n{prompt}"
            return prefixed, "inline_prefix", {}
        return prompt, "inline_prefix", {}

    # contract == "native_v2"
    ds_list = await _list_design_systems_safe(client, stitch_project_id)
    if ds_list:
        cleaned, stripped = _strip_theme_directives(prompt)
        ds_info = {
            "count": len(ds_list),
            "first_asset": ds_list[0].get("name") if isinstance(ds_list[0], dict) else None,
            "stripped_line_count": len(stripped),
        }
        return cleaned, "design_system_applied", ds_info

    # native_v2 but no DS — fallback to legacy prefix when available.
    if design_md_content:
        prefixed = f"# DESIGN SYSTEM (PROVISIONAL)\n{design_md_content}\n\n# Screen\n{prompt}"
        return prefixed, "design_system_missing", {}
    return prompt, "design_system_missing", {}


async def _list_design_systems_safe(client, stitch_project_id: str) -> list:
    """Call ``list_design_systems`` and normalise the return shape.

    The MCP tool returns ``{"designSystems": [...]}`` when there is at
    least one DS and ``{}`` (or 404) when there is none. We always
    return a plain list so callers can ``if ds_list:`` without surprises.
    """
    try:
        result = await client.list_design_systems(stitch_project_id)
    except Exception:  # noqa: BLE001 — fallback is "no DS"
        return []
    if isinstance(result, dict):
        ds = result.get("designSystems")
        if isinstance(ds, list):
            return ds
    return []
