"""Migrate a project's spec data from Trello/Plane to FreeForm (v5.29.0 PR-8).

Skills call `migrate_to_freeform_tool(project, target_path)` to download
items, comments, and attachments from a remote backend into the local
FreeForm filesystem. After successful migration, the caller should
update settings.local.json to use `backend_type: "freeform"` and the
absolute path returned in the result.

This is the inverse of the existing migrate_project (Trello↔Plane) and
shares no code with it intentionally — FreeForm has different semantics
(local filesystem, no remote URLs, append-only comments) and the
mapping is straightforward enough that copy-paste is clearer than a
generic abstraction.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastmcp import Context, FastMCP


async def migrate_to_freeform(
    project: str,
    target_path: str,
    ctx: Context,
    *,
    dry_run: bool = True,
    download_attachments: bool = True,
) -> dict[str, Any]:
    """Migrate a project from the active backend (Trello or Plane) to FreeForm.

    Args:
        project: Project name (used for logging and the migration report).
        target_path: ABSOLUTE path where the FreeForm `doc/tracking/` will
            live on the client filesystem. Validated for absoluteness here
            because the v5.29.0 BLOCKER fix (PR-1) rejects relative paths.
        ctx: FastMCP context — required for `get_session_backend`.
        dry_run: When True (default), no files are written; only the plan is
            returned. Pass False to execute.
        download_attachments: When True, attachment metadata is preserved
            and the original URLs are recorded as `external_url` so the
            user can re-download manually. Binary download from Trello
            requires its specific auth flow and is out of scope for v5.29.0
            — the report tells the user how many attachments would need
            manual download.

    Returns:
        {
          "ok": bool,
          "dry_run": bool,
          "summary": {...counts...},
          "target_path": str,
          "report_path": str | None,  # written under doc/migrations/
          "warnings": [str, ...],
        }
    """
    from ..auth_gateway import get_session_backend

    if not Path(target_path).is_absolute():
        return {
            "ok": False,
            "error": "freeform_path_must_be_absolute",
            "message": (
                f"target_path must be absolute, got {target_path!r}. The MCP "
                "server may run remotely; relative paths resolve against the "
                "server CWD, not the client repo."
            ),
        }

    try:
        source_backend = await get_session_backend(ctx)
    except Exception as e:
        return {"ok": False, "error": "no_active_backend", "detail": str(e)}

    # Read everything from the source.
    items = await source_backend.list_items()
    item_count = len(items)
    comment_count = 0
    attachment_count = 0
    attachments_external = []  # URLs the user must download manually
    warnings: list[str] = []

    items_payload: list[dict[str, Any]] = []
    comments_payload: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        items_payload.append(
            {
                "id": item.id,
                "name": item.name,
                "description": item.description,
                "state": item.state,
                "parent_id": item.parent_id,
                "labels": list(item.labels or []),
                "meta": dict(item.meta or {}),
                "created_at": item.created_at,
                "updated_at": item.updated_at,
            }
        )
        try:
            comments = await source_backend.get_comments("", item.id)
            if comments:
                comments_payload[item.id] = [
                    {"id": c.id, "text": c.text, "created_at": getattr(c, "created_at", None)}
                    for c in comments
                ]
                comment_count += len(comments)
        except Exception as e:
            warnings.append(f"Could not fetch comments for {item.id}: {e}")
        try:
            attachments = await source_backend.get_attachments("", item.id)
            for att in attachments:
                attachment_count += 1
                if getattr(att, "url", None):
                    attachments_external.append(
                        {"item_id": item.id, "url": att.url, "name": getattr(att, "name", "")}
                    )
        except Exception as e:
            warnings.append(f"Could not fetch attachments for {item.id}: {e}")

    summary = {
        "items": item_count,
        "comments": comment_count,
        "attachments": attachment_count,
        "attachments_with_external_urls": len(attachments_external),
    }

    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "summary": summary,
            "target_path": target_path,
            "warnings": warnings,
            "external_attachment_urls": attachments_external[:50],  # truncate for safety
            "message": (
                f"Dry run: would migrate {item_count} items, {comment_count} comments, "
                f"{attachment_count} attachments to {target_path}. "
                "Run again with dry_run=False to execute."
            ),
        }

    # Execute: write files atomically.
    target = Path(target_path)
    target.mkdir(parents=True, exist_ok=True)
    (target / "items.json").write_text(
        json.dumps(items_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if comments_payload:
        comments_dir = target / "comments"
        comments_dir.mkdir(exist_ok=True)
        for item_id, comments in comments_payload.items():
            file_path = comments_dir / f"{item_id}.jsonl"
            with file_path.open("w", encoding="utf-8") as f:
                for c in comments:
                    f.write(json.dumps(c, ensure_ascii=False) + "\n")

    # Write a config.json so FreeformBackend recognises the directory.
    config = {
        "board_name": project,
        "states": ["user_stories", "backlog", "in_progress", "review", "done"],
        "labels": [],
        "migrated_from": "trello_or_plane",
        "migrated_at": datetime.now(timezone.utc).isoformat(),
    }
    (target / "config.json").write_text(
        json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    # Write a migration report under <project>/doc/migrations/.
    repo_root = target.parent.parent  # target = .../doc/tracking → repo_root = .../
    report_dir = repo_root / "doc" / "migrations"
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = report_dir / f"{stamp}_to_freeform.md"
    report_lines = [
        f"# Migration to FreeForm — {project}",
        "",
        f"Date: {datetime.now(timezone.utc).isoformat()}",
        f"Target: {target_path}",
        "",
        "## Summary",
        f"- Items migrated: {summary['items']}",
        f"- Comments migrated: {summary['comments']}",
        f"- Attachments referenced: {summary['attachments']}",
        f"- External attachment URLs preserved: {summary['attachments_with_external_urls']}",
        "",
        "## Warnings" if warnings else "## Warnings — none",
    ]
    for w in warnings:
        report_lines.append(f"- {w}")
    if attachments_external:
        report_lines.extend(
            [
                "",
                "## External attachments (download manually if needed)",
                "Trello/Plane attachments require their original auth to download. The list",
                "below is preserved verbatim from the source backend.",
                "",
            ]
        )
        for att in attachments_external[:200]:  # cap to avoid huge files
            report_lines.append(f"- [{att['item_id']}] {att.get('name', '')} → {att['url']}")
        if len(attachments_external) > 200:
            report_lines.append(
                f"- ...and {len(attachments_external) - 200} more (see metadata)."
            )
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    return {
        "ok": True,
        "dry_run": False,
        "summary": summary,
        "target_path": target_path,
        "report_path": str(report_path),
        "warnings": warnings,
        "next_steps": [
            "Update .claude/settings.local.json: set specbox.backend_type=\"freeform\" "
            f"and specbox.freeform_root_absolute=\"{target_path}\".",
            "Re-run set_auth_token(backend_type=\"freeform\", root_path="
            f"\"{target_path}\") to activate the new backend in this session.",
            "Inspect doc/migrations/ for the full report.",
        ],
    }


def register_freeform_migration_tools(mcp: FastMCP, engine_path: Path) -> None:
    """Register the migrate_to_freeform tool."""

    @mcp.tool
    async def migrate_to_freeform_tool(
        project: str,
        target_path: str,
        ctx: Context,
        dry_run: bool = True,
        download_attachments: bool = True,
    ) -> dict[str, Any]:
        """Migrate a project from Trello/Plane to FreeForm.

        Reads all items, comments, and attachment metadata from the active
        backend and writes them to the local filesystem at ``target_path``.
        Set ``dry_run=False`` to actually execute (default is preview).

        FreeForm requires absolute paths (v5.29.0 BLOCKER fix from PR-1).
        Pass an absolute path resolved client-side, e.g. via
        `git rev-parse --show-toplevel`.
        """
        return await migrate_to_freeform(
            project,
            target_path,
            ctx,
            dry_run=dry_run,
            download_attachments=download_attachments,
        )
