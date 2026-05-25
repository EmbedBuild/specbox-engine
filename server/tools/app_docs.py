"""MCP tools to read the canonical project documents (v5.29.0 PR-4, v6.0.1 refactor).

`read_app_docs(project_path)` is the single entry point that `/prd`,
`/plan`, `/visual-setup`, and any other skill calls in their Paso 0 to
inherit project-level decisions instead of asking the user again.

Returns structured data with:
  - prd: { vision, audience, scope, success_metrics, roadmap, stakeholders }
  - spec: { stack, tracking_backend, brand_visual, conventions, autopilot, canonical_decisions }
  - meta: signatures, paths, parsing errors

**v6.0.1 — MCP Path Contract**

The two @mcp.tool wrappers (`read_app_docs_tool`, `get_inheritable_values_tool`)
now accept document content via parameters and never touch the client
filesystem. The internal Path-based functions `read_app_docs(project_path)`
and `get_inheritable_values(project_path)` are preserved unchanged for
in-process callers (other tools that run on the MCP host's filesystem and
for tests). External MCP callers (skills, claude.ai web) must use the
content-passing variants.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from ..app_docs.zones import (
    ParsedDoc,
    ZoneKind,
    compute_signature,
    parse_document,
    validate_document,
)


PRD_REQUIRED_ZONES: dict[str, ZoneKind] = {
    "vision": ZoneKind.MANUAL,
    "audience": ZoneKind.MANUAL,
    "scope": ZoneKind.MANUAL,
    "success_metrics": ZoneKind.HYBRID,
    "roadmap": ZoneKind.AUTO,
    "stakeholders": ZoneKind.MANUAL,
}

SPEC_REQUIRED_ZONES: dict[str, ZoneKind] = {
    "stack": ZoneKind.AUTO,
    "tracking_backend": ZoneKind.AUTO,
    "brand_visual": ZoneKind.MANUAL,
    "conventions": ZoneKind.MANUAL,
    "autopilot": ZoneKind.AUTO,
    "canonical_decisions": ZoneKind.HYBRID,
}


def _doc_to_dict(doc: ParsedDoc, required: dict[str, ZoneKind]) -> dict[str, Any]:
    """Project a ParsedDoc into a flat zone_id → body dict + meta."""
    issues = validate_document(doc, required_zones=required)
    errors = [
        {"severity": i.severity, "zone_id": i.zone_id, "message": i.message}
        for i in issues
    ]
    zones = {z.id: {"kind": z.kind.value, "body": z.body, "auto_sync_on": list(z.auto_sync_on)} for z in doc.zones}
    return {
        "exists": True,
        "path": str(doc.path),
        "well_formed": doc.is_well_formed and not [e for e in errors if e["severity"] == "error"],
        "signature": compute_signature(doc),
        "zones": zones,
        "errors": errors,
    }


def read_app_docs(project_path: str | Path = ".") -> dict[str, Any]:
    """Read `doc/app/app_prd.md` and `doc/app/app_spec.md` if they exist.

    Path-based internal helper. The MCP boundary uses
    :func:`read_app_docs_from_content` (v6.0.1 content-passing API).

    Args:
        project_path: Project root (default: cwd).

    Returns:
        {
          "has_app_prd": bool,
          "has_app_spec": bool,
          "prd": {...} | None,
          "spec": {...} | None,
          "summary": "human-readable one-liner",
        }
    """
    root = Path(project_path).resolve()
    prd_path = root / "doc" / "app" / "app_prd.md"
    spec_path = root / "doc" / "app" / "app_spec.md"

    prd_content: str | None = None
    spec_content: str | None = None
    if prd_path.exists():
        try:
            prd_content = prd_path.read_text(encoding="utf-8")
        except OSError:
            prd_content = None
    if spec_path.exists():
        try:
            spec_content = spec_path.read_text(encoding="utf-8")
        except OSError:
            spec_content = None

    result = read_app_docs_from_content(
        app_prd_content=prd_content,
        app_spec_content=spec_content,
    )
    result["project_path"] = str(root)
    # Preserve original absolute path strings for callers that expect them
    if result["prd"] is not None:
        result["prd"]["path"] = str(prd_path)
    if result["spec"] is not None:
        result["spec"]["path"] = str(spec_path)
    return result


def read_app_docs_from_content(
    *,
    app_prd_content: str | None,
    app_spec_content: str | None,
) -> dict[str, Any]:
    """Content-passing variant of :func:`read_app_docs`.

    The caller provides the raw markdown content; this function performs no
    filesystem I/O, making it safe to call from a remote MCP server.

    The returned ``prd.path`` and ``spec.path`` fields are nominal
    (``"doc/app/app_prd.md"`` / ``"doc/app/app_spec.md"``) — callers that
    need a real absolute path should use the Path-based wrapper.
    """
    has_app_prd = bool(app_prd_content is not None and app_prd_content.strip())
    has_app_spec = bool(app_spec_content is not None and app_spec_content.strip())

    result: dict[str, Any] = {
        "has_app_prd": has_app_prd,
        "has_app_spec": has_app_spec,
        "prd": None,
        "spec": None,
    }

    if has_app_prd:
        doc = parse_document("doc/app/app_prd.md", content=app_prd_content)
        result["prd"] = _doc_to_dict(doc, PRD_REQUIRED_ZONES)
        result["prd"]["path"] = "doc/app/app_prd.md"
    if has_app_spec:
        doc = parse_document("doc/app/app_spec.md", content=app_spec_content)
        result["spec"] = _doc_to_dict(doc, SPEC_REQUIRED_ZONES)
        result["spec"]["path"] = "doc/app/app_spec.md"

    if not has_app_prd and not has_app_spec:
        result["summary"] = (
            "doc/app/ no existe. Ejecuta /app-init para crear los documentos "
            "canónicos antes de continuar."
        )
    elif has_app_prd and has_app_spec:
        prd_ok = result["prd"]["well_formed"]
        spec_ok = result["spec"]["well_formed"]
        if prd_ok and spec_ok:
            result["summary"] = "app_prd.md y app_spec.md OK; valores heredables disponibles."
        else:
            result["summary"] = (
                "app_prd.md o app_spec.md tienen errores de formato. "
                "Ejecuta /app-init --refresh o revisa los marcadores @specbox:zone."
            )
    else:
        result["summary"] = "Solo uno de los documentos canónicos existe; ejecuta /app-init para completar."

    return result


def get_inheritable_values(project_path: str | Path = ".") -> dict[str, Any]:
    """Extract decision-ready values from the canonical docs.

    Path-based internal helper. The MCP boundary uses
    :func:`get_inheritable_values_from_content` (v6.0.1 content-passing API).
    """
    docs = read_app_docs(project_path)
    return _project_inheritable(docs)


def get_inheritable_values_from_content(
    *,
    app_prd_content: str | None,
    app_spec_content: str | None,
) -> dict[str, Any]:
    """Content-passing variant of :func:`get_inheritable_values`."""
    docs = read_app_docs_from_content(
        app_prd_content=app_prd_content,
        app_spec_content=app_spec_content,
    )
    return _project_inheritable(docs)


def _project_inheritable(docs: dict[str, Any]) -> dict[str, Any]:
    """Shared projection from a `read_app_docs` result to the flat
    inheritable-values dict. Used by both Path-based and content-based
    public functions.
    """
    out: dict[str, Any] = {
        "audience_defined": False,
        "audience_text": None,
        "scope_defined": False,
        "veg_mode_known": False,
        "veg_archetype": None,
        "stack_known": False,
        "stack_text": None,
        "backend_type": None,
        "freeform_root_absolute": None,
        "autopilot_level": None,
        "image_budget_eur_per_feature": None,
    }

    prd = docs.get("prd")
    if prd and prd.get("well_formed"):
        zones = prd.get("zones", {})
        audience_body = zones.get("audience", {}).get("body", "").strip()
        if audience_body and "{target_name}" not in audience_body:
            out["audience_defined"] = True
            out["audience_text"] = audience_body
        scope_body = zones.get("scope", {}).get("body", "").strip()
        if scope_body and "{feature de alto nivel" not in scope_body:
            out["scope_defined"] = True

    spec = docs.get("spec")
    if spec and spec.get("well_formed"):
        zones = spec.get("zones", {})
        brand_body = zones.get("brand_visual", {}).get("body", "")
        if "VEG arquetipo" in brand_body:
            for line in brand_body.splitlines():
                if "VEG arquetipo" in line and "{" not in line:
                    out["veg_archetype"] = line.split("VEG arquetipo")[-1].strip(" :*-").split("|")[0].strip()
                    break
            for line in brand_body.splitlines():
                if "Modo VEG" in line and "{" not in line:
                    out["veg_mode_known"] = True
                    break
        stack_body = zones.get("stack", {}).get("body", "")
        if stack_body and "(autoinferido" not in stack_body:
            out["stack_known"] = True
            out["stack_text"] = stack_body
        backend_body = zones.get("tracking_backend", {}).get("body", "")
        for line in backend_body.splitlines():
            if "Tipo:" in line:
                value = line.split("Tipo:")[-1].strip(" *-")
                if value in ("freeform", "trello", "plane"):
                    out["backend_type"] = value
            if "Path absoluto" in line and "/" in line:
                tail = line.split(":", 1)[-1].strip(" `*")
                if tail.startswith("/"):
                    out["freeform_root_absolute"] = tail
        autopilot_body = zones.get("autopilot", {}).get("body", "")
        for line in autopilot_body.splitlines():
            if "Level:" in line:
                value = line.split("Level:")[-1].strip(" *-")
                if value in ("low", "conservador", "equilibrado", "agresivo"):
                    out["autopilot_level"] = value
            if "Image budget" in line:
                tail = line.split(":")[-1].strip(" €*-")
                try:
                    out["image_budget_eur_per_feature"] = float(tail.split()[0])
                except (ValueError, IndexError):
                    pass

    return out


def register_app_docs_tools(mcp: FastMCP, engine_path: Path) -> None:
    """Register app_docs MCP tools (v6.0.1 content-passing API)."""

    @mcp.tool
    def read_app_docs_tool(
        app_prd_content: str | None = None,
        app_spec_content: str | None = None,
    ) -> dict[str, Any]:
        """Parse client-supplied canonical documents and return structured zones.

        **v6.0.1 — content-passing API**

        The caller reads ``doc/app/app_prd.md`` and ``doc/app/app_spec.md``
        from the local repo (or ``None`` when absent) and passes the content
        as strings. This tool never touches the filesystem.

        Returns parsed zones, validation errors, and signatures. Skills
        call this in their Paso 0 to know what questions they can skip.
        If both content parameters are ``None``/empty, returns
        ``{has_app_prd: false, has_app_spec: false}`` to signal fall-back
        to v5.28 ask-everything behavior.

        Args:
            app_prd_content: Raw markdown of ``doc/app/app_prd.md`` if it
                exists on the client; ``None`` otherwise.
            app_spec_content: Raw markdown of ``doc/app/app_spec.md`` if it
                exists on the client; ``None`` otherwise.
        """
        return read_app_docs_from_content(
            app_prd_content=app_prd_content,
            app_spec_content=app_spec_content,
        )

    @mcp.tool
    def get_inheritable_values_tool(
        app_prd_content: str | None = None,
        app_spec_content: str | None = None,
    ) -> dict[str, Any]:
        """Extract a flat dict of project-level decisions ready to inherit.

        **v6.0.1 — content-passing API**

        High-level entry point for skills that need to decide "ask vs.
        inherit" before prompting the user. Returns booleans like
        ``audience_defined``, ``scope_defined``, ``veg_mode_known``,
        ``stack_known``, plus the extracted values when present.

        Args:
            app_prd_content: Raw markdown of ``doc/app/app_prd.md``.
            app_spec_content: Raw markdown of ``doc/app/app_spec.md``.
        """
        return get_inheritable_values_from_content(
            app_prd_content=app_prd_content,
            app_spec_content=app_spec_content,
        )
