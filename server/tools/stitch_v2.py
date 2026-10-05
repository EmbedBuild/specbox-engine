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
from ..coordination.i18n_messages import extract_locale_from_ctx
from ..design_md.generator import GeneratorInputs, generate_design_md
from ..design_md.io import compute_signature, load
from ..design_md.material3_view import build_material3_frontmatter
from ..design_md.archetypes import ArchetypeId
from ..design_md.system_view import build_material3_from_system
from ..design_md.writer import serialize
from ..design_system import (
    SYSTEM_TOKENS_CANDIDATE_PATHS,
    SYSTEM_TOKENS_GUIDE_URL,
    SystemTokensError,
    candidate_marker,
    find_values_outside,
    parse_system_tokens,
    system_tokens_notice,
)
from ..stitch_enums import DEFAULT_MODEL, UnknownModelError, resolve_model
from ..transport import is_remote_transport
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
        project_root: str | None = None,
        project_name: str | None = None,
        output_path: str | None = None,
        archetype_override: str | None = None,
        contract: str = "native_v2",
        system_tokens_content: str | None = None,
        system_tokens_path: str | None = None,
        brand_kit_content: str | None = None,
        veg_content: str | None = None,
        app_prd_content: str | None = None,
        app_spec_content: str | None = None,
    ) -> dict:
        """Generate the canonical DESIGN.md for a project.

        Synthesises a DESIGN.md (Google Stitch's official format —
        github.com/google-labs-code/design.md). **When the project has
        system tokens** (``design-system.tokens.json``, US-49 · UC-4901)
        they are the only source: colours, typography, radii, spacing,
        states and shadows come from them, the brand kit and archetypes
        are ignored, and the response reports ``values_outside_system``
        (empty when the document holds only token values). Without
        system tokens it synthesises from ``doc/brand/brand_kit.md``,
        ``doc/veg/*.md`` and ``doc/app/app_{prd,spec}.md``, falls back to
        the closest VEG archetype, and returns a ``notice`` explaining how
        to adopt the tokens, with the link to the guide.

        Two modes (MCP path contract):

        - **content** — the client sends the files' contents
          (``*_content``) and writes the returned ``design_md_content`` to
          ``suggested_relpath`` itself. Nothing is read from or written to
          the server's disk. The only mode of a remote server.
        - **disk** — only with a local server: ``project_root`` is read
          (system tokens are looked for in ``SYSTEM_TOKENS_CANDIDATE_PATHS``)
          and DESIGN.md is written to ``output_path``.

        Idempotent; the signature excludes ``generated_at``.

        Args:
            project: SpecBox project slug (telemetry only).
            project_root: Local server only — absolute path of the repo.
            project_name: Display name (defaults to ``project``).
            output_path: Disk mode: where to write (default
                ``{project_root}/doc/design/DESIGN.md``). Content mode:
                echoed as ``suggested_relpath``.
            archetype_override: corporate | startup | creative | consumer |
                gen_z | gov. Ignored when system tokens exist.
            contract: ``"native_v2"`` (default) emits the Material 3
                front-matter Stitch parses; ``"inline_prefix_v1"`` the
                legacy SpecBox front-matter.
            system_tokens_content: Content of ``design-system.tokens.json``.
            system_tokens_path: Its path relative to the repo (provenance).
            brand_kit_content / veg_content / app_prd_content /
            app_spec_content: Contents of the other inputs, if any.

        Returns:
            ``{status, mode, design_md_content, path | suggested_relpath,
              signature, contract, sections, design_source, system_tokens,
              values_outside_system?, notice?, warnings?, material3?}``;
            ``{error, code}`` on failure (``DESIGN_MD_CONTENT_REQUIRED``,
            ``SYSTEM_TOKENS_INVALID``).
        """

        locale = extract_locale_from_ctx(ctx)
        if contract not in {"native_v2", "inline_prefix_v1"}:
            return {
                "error": (
                    f"unknown contract {contract!r}. Use 'native_v2' or "
                    "'inline_prefix_v1'."
                )
            }

        contents = (
            system_tokens_content,
            brand_kit_content,
            veg_content,
            app_prd_content,
            app_spec_content,
        )
        content_mode = any(c is not None for c in contents) or not project_root
        if not content_mode and is_remote_transport():
            _log_v2(project, "generate_design_md", status="error", reason="remote_disk_mode")
            return _content_required_error(project, project_root)

        root: Path | None = None
        tokens_text, tokens_rel = system_tokens_content, system_tokens_path
        try:
            if not content_mode:
                root = Path(project_root).expanduser().resolve()  # type: ignore[arg-type]
                if not root.is_dir():
                    _log_v2(project, "generate_design_md", status="error", reason="bad_root")
                    return {"error": f"project_root does not exist: {project_root}"}
                if tokens_text is None:
                    found = _find_system_tokens_file(root)
                    if found:
                        tokens_rel, tokens_text = found
            tokens = (
                parse_system_tokens(tokens_text, source=tokens_rel)
                if tokens_text is not None
                else None
            )
        except SystemTokensError as exc:
            _log_v2(project, "generate_design_md", status="error", reason="system_tokens_invalid")
            return {
                "error": f"SYSTEM_TOKENS_INVALID: {exc}",
                "code": "SYSTEM_TOKENS_INVALID",
                "project": project,
                "path": tokens_rel,
                "guide_url": SYSTEM_TOKENS_GUIDE_URL,
            }

        try:
            inputs = GeneratorInputs(
                project_root=root,
                project_name=project_name or project,
                brand_kit_path=root / "doc" / "brand" / "brand_kit.md" if root else None,
                veg_path=_pick_veg_path(root) if root else None,
                app_prd_path=root / "doc" / "app" / "app_prd.md" if root else None,
                app_spec_path=root / "doc" / "app" / "app_spec.md" if root else None,
                archetype_override=_resolve_archetype(archetype_override),
                brand_kit_text=brand_kit_content,
                veg_text=veg_content,
                app_prd_text=app_prd_content,
                app_spec_text=app_spec_content,
                system_tokens=tokens,
            )

            doc = generate_design_md(inputs)

            warnings: list[str] = []
            m3_fm = None
            if contract == "native_v2":
                if tokens is not None:
                    m3_fm = build_material3_from_system(doc, tokens)
                    warnings.extend(m3_fm.warnings)
                else:
                    m3_fm = build_material3_frontmatter(
                        doc, inputs.archetype_override or ArchetypeId.STARTUP
                    )
            content = serialize(doc, material3=m3_fm)
            sig = compute_signature(doc)

            if content_mode:
                location = {"suggested_relpath": output_path or "doc/design/DESIGN.md"}
                logged_path = location["suggested_relpath"]
            else:
                out = (
                    Path(output_path).expanduser().resolve()
                    if output_path
                    else root / "doc" / "design" / "DESIGN.md"  # type: ignore[operator]
                )
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(content, encoding="utf-8")
                # Persist signature in project meta so the sync layer can
                # detect drift between Brand Kit and DESIGN.md.
                _store_design_md_meta(
                    state_path, project, out, sig, doc.front_matter.colors.primary
                )
                location = {"path": str(out)}
                logged_path = str(out)

            _log_v2(
                project,
                "generate_design_md",
                signature=sig,
                archetype="system_tokens" if tokens else (archetype_override or "auto"),
                contract=contract,
                path=logged_path,
            )

            brand_kit_given = brand_kit_content is not None or bool(
                inputs.brand_kit_path and inputs.brand_kit_path.exists()
            )
            response: dict = {
                "status": "ok",
                "project": project,
                "mode": "content" if content_mode else "disk",
                **location,
                "design_md_content": content,
                "signature": sig,
                "archetype": None if tokens else (archetype_override or "auto"),
                "contract": contract,
                "design_source": (
                    tokens.describe()
                    if tokens
                    else {"kind": "brand_kit" if brand_kit_given else "archetype"}
                ),
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
            if tokens is not None:
                response["system_tokens"] = {"found": True, **tokens.describe()}
                response["values_outside_system"] = [
                    d.to_dict() for d in find_values_outside(content, tokens)
                ]
            else:
                response["system_tokens"] = {"found": False}
                response["notice"] = system_tokens_notice(locale)
            if warnings:
                response["warnings"] = warnings
            if m3_fm is not None:
                response["material3"] = m3_fm.to_dict()
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
        model_id: str = DEFAULT_MODEL,
        baseline_screen_id: str | None = None,
        max_total_attempts: int = 3,
        contract: str = "native_v2",
        design_md_content: str | None = None,
        design_system: str | None = None,
    ) -> dict:
        """Generate a screen with the v5.31.0 fallback chain.

        Strategy ladder when the natural call fails:
            edit_baseline → variants_refine → regenerate

        Args:
            project: SpecBox project slug.
            stitch_project_id: Target Stitch project ID.
            prompt: The generation prompt (already validated upstream).
            device_type: DESKTOP|MOBILE|TABLET.
            model_id: Stitch model: GEMINI_3_8_FLASH (default, quality
                first) or GEMINI_3_5_FLASH_LITE (simple screens). A legacy
                id (GEMINI_3_PRO, GEMINI_3_FLASH, GEMINI_3_1_PRO) is
                translated and reported in ``model_notice``; any other is
                rejected before calling Stitch. The fallback ladder uses
                GEMINI_3_5_FLASH_LITE.
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
            design_system: ``assets/{id}`` to generate with. Without it,
                ``native_v2`` sends the project's design system it detects
                (the first one listed), so the colours and fonts stripped
                from the prompt come from the DS (UC-8501).

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
            model, model_notice = resolve_model(model_id)
        except UnknownModelError as exc:
            return {"error": str(exc), "project": project}

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

            ds_asset = design_system or (
                ds_info.get("first_asset") if prompt_mode == "design_system_applied" else None
            )
            ops = _StitchOpsAdapter(client)
            result = await generate_screen_with_fallback(
                ops,
                stitch_project_id,
                effective_prompt,
                device_type=device_type,
                model_id=model,
                design_system=ds_asset,
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
                "design_system_used": ds_asset,
                **({"model_notice": model_notice} if model_notice else {}),
                **candidate_marker("stitch", extract_locale_from_ctx(ctx)),
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
        """Multi-screen build: every screen generated, then one pass that unifies the theme.

        Each screen is a ``generate_screen_from_text`` call, in batches of
        ≤``batch_size`` (explicit group, then route prefix, then order).
        With more than one batch, a final ``edit_screens`` over all the
        generated screens aligns their visual language. If any screen fails
        the answer is ``status: error`` and ``failed_screens`` says which
        and why (UC-8504).

        Args:
            screens: list of dicts with ``name``, ``prompt``, optional
                ``route`` (default ``/``), ``order``, ``group``.
            batch_size: max screens per batch. Default 4.
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

            failed = result.get("failed_screens") or []
            unified_failed = [x for x in result.get("unified_pass", []) if x.get("status") == "error"]
            response = {
                "status": "ok" if not failed and not unified_failed else "error",
                "project": project,
                "stitch_project_id": stitch_project_id,
                **result,
                **candidate_marker("stitch", extract_locale_from_ctx(ctx)),
            }
            if failed or unified_failed:
                # UC-8504 — a build with failed screens is not ok: say which and why.
                response["error"] = "; ".join(
                    [f"{f['name']}: {f['error']}" for f in failed]
                    + [f"unified pass: {x['error']}" for x in unified_failed]
                )
            return response
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
        self, project_id, prompt, *, device_type="DESKTOP", model_id=DEFAULT_MODEL, design_system=None
    ):
        return await self._client.generate_screen_from_text(
            project_id, prompt, device_type=device_type, model_id=model_id, design_system=design_system
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
        prompt="",
        variant_count=1,
        creative_range="REFINE",
        aspects=None,
        device_type=None,
        model_id=None,
    ):
        return await self._client.generate_variants(
            project_id,
            screen_id,
            prompt=prompt,
            variant_count=variant_count,
            creative_range=creative_range,
            aspects=aspects,
            device_type=device_type,
            model_id=model_id,
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


def _find_system_tokens_file(root: Path) -> tuple[str, str] | None:
    """Disk mode only: ``(relpath, content)`` of the project's system tokens."""

    for rel in SYSTEM_TOKENS_CANDIDATE_PATHS:
        path = root / rel
        if path.is_file():
            try:
                return rel, path.read_text(encoding="utf-8")
            except OSError:
                continue
    return None


def _content_required_error(project: str, project_root: str | None) -> dict:
    """A remote server never reads the client's repo (threat model, rule 3)."""

    return {
        "error": (
            "DESIGN_MD_CONTENT_REQUIRED: this MCP server is remote, so it cannot "
            f"read {project_root!r} — that path lives on your machine. Send the "
            "contents instead (system_tokens_content with system_tokens_path, and "
            "brand_kit_content / veg_content / app_prd_content / app_spec_content "
            "when they exist) and write the returned design_md_content to "
            "suggested_relpath."
        ),
        "code": "DESIGN_MD_CONTENT_REQUIRED",
        "project": project,
        "how_to": {
            "system_tokens": (
                "look for design-system.tokens.json in: "
                + ", ".join(SYSTEM_TOKENS_CANDIDATE_PATHS)
            ),
            "call": (
                "generate_design_md_tool(project=..., "
                "system_tokens_content=<file>, system_tokens_path=<relpath>)"
            ),
            "write": "save design_md_content to suggested_relpath (doc/design/DESIGN.md)",
        },
    }


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
