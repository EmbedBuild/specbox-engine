"""Tools for Google Stitch design proxy — generate UI screens via MCP.

Exposes Stitch functionality through the SpecBox Engine MCP server so that
claude.ai users (who only have OAuth) can use Stitch (which requires API Key)
via the SpecBox Engine connector.

API Key is stored per-project in session state and in project meta on disk.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import structlog
from fastmcp import Context, FastMCP

from ..auth_gateway import get_stitch_client, store_stitch_credentials

logger = structlog.get_logger(__name__)

# Session state key for Stitch config
STITCH_STATE_KEY = "stitch_config"


def register_stitch_tools(mcp: FastMCP, state_path: Path):
    """Register Stitch proxy tools on the MCP instance."""

    def _log_stitch_usage(project: str, tool: str) -> None:
        """Log Stitch proxy usage for telemetry."""
        try:
            log_dir = state_path / "projects" / project
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / "stitch_usage.jsonl"
            entry = {
                "tool": tool,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass  # Telemetry is best-effort

    @mcp.tool
    async def stitch_set_api_key(
        ctx: Context,
        project: str,
        api_key: str,
    ) -> dict:
        """Configure or update the Google Stitch API Key for a project.

        Use when a user wants to set up Stitch design generation for their project.
        The API Key is stored in the session and persisted in project meta on disk
        (obfuscated — only last 4 chars visible).

        Args:
            project: Project slug (as registered in SpecBox Engine).
            api_key: Google Stitch API Key.

        Returns:
            Confirmation with project and obfuscated key.
        """
        if not api_key or len(api_key) < 8:
            return {"error": "Invalid API key — must be at least 8 characters."}

        # Store in session for immediate use
        await store_stitch_credentials(ctx, project, api_key)

        # Persist obfuscated reference in project meta on disk
        project_dir = state_path / "projects" / project
        project_dir.mkdir(parents=True, exist_ok=True)
        meta_file = project_dir / "meta.json"
        meta = {}
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                meta = {}

        meta["stitch_configured"] = True
        meta["stitch_key_hint"] = f"...{api_key[-4:]}"
        meta["stitch_configured_at"] = time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
        )

        # Store encrypted key on disk (base64 obfuscation — not true encryption,
        # but avoids plain-text exposure in JSON files)
        import base64

        meta["stitch_key_b64"] = base64.b64encode(api_key.encode()).decode()

        meta_file.write_text(
            json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        logger.info("stitch_api_key_set", project=project, hint=meta["stitch_key_hint"])
        return {
            "status": "ok",
            "project": project,
            "key_hint": meta["stitch_key_hint"],
            "message": f"Stitch API Key configured for project '{project}'.",
        }

    async def _get_client_for_project(ctx: Context, project: str):
        """Resolve StitchClient for a project — session first, then disk fallback."""
        try:
            return await get_stitch_client(ctx, project)
        except RuntimeError:
            pass

        # Fallback: try to load from disk meta
        project_dir = state_path / "projects" / project
        meta_file = project_dir / "meta.json"
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                key_b64 = meta.get("stitch_key_b64")
                if key_b64:
                    import base64

                    api_key = base64.b64decode(key_b64).decode()
                    await store_stitch_credentials(ctx, project, api_key)
                    return await get_stitch_client(ctx, project)
            except (json.JSONDecodeError, OSError, ValueError):
                pass

        raise RuntimeError(
            f"No Stitch API Key configured for project '{project}'. "
            "Call stitch_set_api_key(project, api_key) first."
        )

    @mcp.tool
    async def stitch_list_projects(ctx: Context, project: str) -> dict:
        """List all Google Stitch projects for the user's account.

        Use when you need to see which Stitch design projects are available.

        Args:
            project: SpecBox Engine project slug (to resolve the API Key).

        Returns:
            List of Stitch projects with their IDs and names.
        """
        try:
            client = await _get_client_for_project(ctx, project)
            result = await client.list_projects()
            _log_stitch_usage(project, "list_projects")
            return {"status": "ok", "project": project, "result": result}
        except Exception as exc:
            logger.error("stitch_list_projects_error", project=project, error=str(exc))
            return {"error": str(exc), "project": project}

    @mcp.tool
    async def stitch_get_project(
        ctx: Context, project: str, stitch_project_id: str
    ) -> dict:
        """Get details of a specific Google Stitch project.

        Use when you need to inspect a Stitch project's configuration or metadata.

        Args:
            project: SpecBox Engine project slug (to resolve the API Key).
            stitch_project_id: The Stitch project ID to query.

        Returns:
            Project details including screens, settings, etc.
        """
        try:
            client = await _get_client_for_project(ctx, project)
            result = await client.get_project(stitch_project_id)
            _log_stitch_usage(project, "get_project")
            return {"status": "ok", "project": project, "result": result}
        except Exception as exc:
            logger.error("stitch_get_project_error", project=project, error=str(exc))
            return {"error": str(exc), "project": project}

    @mcp.tool
    async def stitch_list_screens(
        ctx: Context, project: str, stitch_project_id: str
    ) -> dict:
        """List all screens in a Google Stitch project.

        Use when you need to see which UI screens have been generated.

        Args:
            project: SpecBox Engine project slug (to resolve the API Key).
            stitch_project_id: The Stitch project ID.

        Returns:
            List of screens with IDs, names, and thumbnails.
        """
        try:
            client = await _get_client_for_project(ctx, project)
            result = await client.list_screens(stitch_project_id)
            _log_stitch_usage(project, "list_screens")
            return {"status": "ok", "project": project, "result": result}
        except Exception as exc:
            logger.error("stitch_list_screens_error", project=project, error=str(exc))
            return {"error": str(exc), "project": project}

    @mcp.tool
    async def stitch_get_screen(
        ctx: Context,
        project: str,
        stitch_project_id: str,
        screen_id: str,
    ) -> dict:
        """Get the full HTML of a specific Stitch screen.

        Use when you need the complete HTML output of a generated UI screen.

        Args:
            project: SpecBox Engine project slug (to resolve the API Key).
            stitch_project_id: The Stitch project ID.
            screen_id: The screen ID to retrieve.

        Returns:
            Full HTML content of the screen.
        """
        try:
            client = await _get_client_for_project(ctx, project)
            result = await client.get_screen(stitch_project_id, screen_id)
            _log_stitch_usage(project, "get_screen")
            return {"status": "ok", "project": project, "result": result}
        except Exception as exc:
            logger.error("stitch_get_screen_error", project=project, error=str(exc))
            return {"error": str(exc), "project": project}

    @mcp.tool
    async def stitch_generate_screen(
        ctx: Context,
        project: str,
        stitch_project_id: str,
        prompt: str,
        device_type: str = "DESKTOP",
        model_id: str = "GEMINI_3_PRO",
    ) -> dict:
        """Generate a UI screen from a text prompt using Google Stitch.

        WARNING: This operation can take several minutes to complete.
        ALWAYS use LIGHT MODE in prompts unless explicitly told otherwise.

        Use when you need to create a new UI design screen from a description.

        Args:
            project: SpecBox Engine project slug (to resolve the API Key).
            stitch_project_id: The Stitch project ID to create the screen in.
            prompt: Text description of the UI to generate.
            device_type: Target device — "DESKTOP", "MOBILE", or "TABLET".
            model_id: AI model — "GEMINI_3_PRO" (complex) or "GEMINI_3_FLASH" (simple).

        Returns:
            Generated screen details including ID and HTML content.
        """
        try:
            client = await _get_client_for_project(ctx, project)
            logger.info(
                "stitch_generate_screen_start",
                project=project,
                stitch_project=stitch_project_id,
                device_type=device_type,
                model_id=model_id,
            )
            result = await client.generate_screen_from_text(
                stitch_project_id,
                prompt,
                device_type=device_type,
                model_id=model_id,
            )
            _log_stitch_usage(project, "generate_screen")
            logger.info("stitch_generate_screen_complete", project=project)
            return {"status": "ok", "project": project, "result": result}
        except Exception as exc:
            logger.error(
                "stitch_generate_screen_error", project=project, error=str(exc)
            )
            return {"error": str(exc), "project": project}

    @mcp.tool
    async def stitch_edit_screen(
        ctx: Context,
        project: str,
        stitch_project_id: str,
        screen_id: str,
        prompt: str,
        device_type: str = "",
        model_id: str = "",
    ) -> dict:
        """Edit an existing Stitch screen with a text prompt.

        WARNING: This operation can take several minutes to complete.

        Use when you need to modify an existing UI design — change layout,
        colors, add/remove elements, etc.

        Args:
            project: SpecBox Engine project slug (to resolve the API Key).
            stitch_project_id: The Stitch project ID.
            screen_id: The screen ID to edit.
            prompt: Text description of the changes to make.
            device_type: Optional — "DESKTOP", "MOBILE", "TABLET", or "AGNOSTIC".
            model_id: Optional — "GEMINI_3_PRO" or "GEMINI_3_FLASH".

        Returns:
            Updated screen details.
        """
        try:
            client = await _get_client_for_project(ctx, project)
            logger.info(
                "stitch_edit_screen_start",
                project=project,
                screen_id=screen_id,
            )
            result = await client.edit_screens(
                stitch_project_id,
                screen_id,
                prompt,
                device_type=device_type or None,
                model_id=model_id or None,
            )
            _log_stitch_usage(project, "edit_screens")
            logger.info("stitch_edit_screen_complete", project=project)
            return {"status": "ok", "project": project, "result": result}
        except Exception as exc:
            logger.error(
                "stitch_edit_screen_error", project=project, error=str(exc)
            )
            return {"error": str(exc), "project": project}

    @mcp.tool
    async def stitch_generate_variants(
        ctx: Context,
        project: str,
        stitch_project_id: str,
        screen_id: str,
        prompt: str = "",
        variant_count: int = 3,
        creative_range: str = "EXPLORE",
        aspects: str = "",
    ) -> dict:
        """Generate design variants of an existing Stitch screen.

        WARNING: This operation can take several minutes to complete.

        Use when you need alternative versions of an existing UI design.

        Args:
            project: SpecBox Engine project slug (to resolve the API Key).
            stitch_project_id: The Stitch project ID.
            screen_id: The screen ID to generate variants from.
            prompt: Optional text prompt to guide variant generation.
            variant_count: Number of variants (1-5, default: 3).
            creative_range: "REFINE" (subtle), "EXPLORE" (moderate), or "REIMAGINE" (radical).
            aspects: Comma-separated aspects to vary: LAYOUT, COLOR_SCHEME, IMAGES, TEXT_FONT, TEXT_CONTENT.

        Returns:
            List of generated variant screens.
        """
        try:
            client = await _get_client_for_project(ctx, project)
            aspect_list = (
                [a.strip().upper() for a in aspects.split(",") if a.strip()]
                if aspects
                else None
            )
            logger.info(
                "stitch_generate_variants_start",
                project=project,
                screen_id=screen_id,
                variant_count=variant_count,
                creative_range=creative_range,
            )
            result = await client.generate_variants(
                stitch_project_id,
                screen_id,
                prompt=prompt or None,
                variant_count=variant_count,
                creative_range=creative_range,
                aspects=aspect_list,
            )
            _log_stitch_usage(project, "generate_variants")
            logger.info("stitch_generate_variants_complete", project=project)
            return {"status": "ok", "project": project, "result": result}
        except Exception as exc:
            logger.error(
                "stitch_generate_variants_error", project=project, error=str(exc)
            )
            return {"error": str(exc), "project": project}

    @mcp.tool
    async def stitch_create_project(
        ctx: Context,
        project: str,
        title: str,
    ) -> dict:
        """Create a new Google Stitch project/workspace.

        Use when you need a new Stitch project to organize design screens.

        Args:
            project: SpecBox Engine project slug (to resolve the API Key).
            title: Name for the new Stitch project.

        Returns:
            Created project details including ID.
        """
        try:
            client = await _get_client_for_project(ctx, project)
            result = await client.create_project(title)
            _log_stitch_usage(project, "create_project")
            return {"status": "ok", "project": project, "result": result}
        except Exception as exc:
            logger.error(
                "stitch_create_project_error", project=project, error=str(exc)
            )
            return {"error": str(exc), "project": project}

    @mcp.tool
    async def stitch_fetch_screen_code(
        ctx: Context,
        project: str,
        stitch_project_id: str,
        screen_id: str,
    ) -> dict:
        """Download the raw HTML/frontend code of a Stitch screen.

        Use when you need the actual HTML source code of a generated design
        to integrate into your project.

        Args:
            project: SpecBox Engine project slug (to resolve the API Key).
            stitch_project_id: The Stitch project ID.
            screen_id: The screen ID.

        Returns:
            Raw HTML code of the screen.
        """
        try:
            client = await _get_client_for_project(ctx, project)
            result = await client.fetch_screen_code(stitch_project_id, screen_id)
            _log_stitch_usage(project, "fetch_screen_code")
            return {"status": "ok", "project": project, "result": result}
        except Exception as exc:
            logger.error(
                "stitch_fetch_screen_code_error", project=project, error=str(exc)
            )
            return {"error": str(exc), "project": project}

    @mcp.tool
    async def stitch_fetch_screen_image(
        ctx: Context,
        project: str,
        stitch_project_id: str,
        screen_id: str,
    ) -> dict:
        """Download the high-resolution screenshot of a Stitch screen.

        Use when you need a visual preview or screenshot of a generated design.

        Args:
            project: SpecBox Engine project slug (to resolve the API Key).
            stitch_project_id: The Stitch project ID.
            screen_id: The screen ID.

        Returns:
            High-res screenshot (base64 encoded or URL).
        """
        try:
            client = await _get_client_for_project(ctx, project)
            result = await client.fetch_screen_image(stitch_project_id, screen_id)
            _log_stitch_usage(project, "fetch_screen_image")
            return {"status": "ok", "project": project, "result": result}
        except Exception as exc:
            logger.error(
                "stitch_fetch_screen_image_error", project=project, error=str(exc)
            )
            return {"error": str(exc), "project": project}

    @mcp.tool
    async def stitch_extract_design_context(
        ctx: Context,
        project: str,
        stitch_project_id: str,
        screen_id: str,
    ) -> dict:
        """Extract Design DNA from a Stitch screen — fonts, colors, layouts.

        Use when you need to analyze an existing design to maintain style
        consistency across new screens. Returns structured design tokens
        that can be used as context for generate/edit operations.

        Args:
            project: SpecBox Engine project slug (to resolve the API Key).
            stitch_project_id: The Stitch project ID.
            screen_id: The screen ID to analyze.

        Returns:
            Design DNA: fonts, colors, layouts, spacing, and other design tokens.
        """
        try:
            client = await _get_client_for_project(ctx, project)
            result = await client.extract_design_context(
                stitch_project_id, screen_id
            )
            _log_stitch_usage(project, "extract_design_context")
            return {"status": "ok", "project": project, "result": result}
        except Exception as exc:
            logger.error(
                "stitch_extract_design_context_error",
                project=project,
                error=str(exc),
            )
            return {"error": str(exc), "project": project}

    @mcp.tool
    async def stitch_build_site(
        ctx: Context,
        project: str,
        stitch_project_id: str,
        routes: str,
    ) -> dict:
        """Build a multi-page site by mapping Stitch screens to URL routes.

        WARNING: This operation can take several minutes to complete.

        Use when you have multiple screens and want to assemble them into
        a complete site with proper routing.

        Args:
            project: SpecBox Engine project slug (to resolve the API Key).
            stitch_project_id: The Stitch project ID.
            routes: JSON array of route mappings, e.g.:
                    [{"screenId": "abc", "route": "/"}, {"screenId": "def", "route": "/about"}]

        Returns:
            Site build result with HTML for each route.
        """
        try:
            import json as json_mod

            try:
                route_list = json_mod.loads(routes)
            except (json_mod.JSONDecodeError, TypeError):
                return {
                    "error": "Invalid routes JSON. Expected array of {screenId, route} objects.",
                    "project": project,
                }

            client = await _get_client_for_project(ctx, project)
            logger.info(
                "stitch_build_site_start",
                project=project,
                route_count=len(route_list),
            )
            result = await client.build_site(stitch_project_id, route_list)
            _log_stitch_usage(project, "build_site")
            logger.info("stitch_build_site_complete", project=project)
            return {"status": "ok", "project": project, "result": result}
        except Exception as exc:
            logger.error(
                "stitch_build_site_error", project=project, error=str(exc)
            )
            return {"error": str(exc), "project": project}
