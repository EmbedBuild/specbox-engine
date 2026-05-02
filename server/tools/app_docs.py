"""MCP tools to read the canonical project documents (v5.29.0 PR-4).

`read_app_docs(project_path)` is the single entry point that `/prd`,
`/plan`, `/visual-setup`, and any other skill calls in their Paso 0 to
inherit project-level decisions instead of asking the user again.

Returns structured data with:
  - prd: { vision, audience, scope, success_metrics, roadmap, stakeholders }
  - spec: { stack, tracking_backend, brand_visual, conventions, autopilot, canonical_decisions }
  - meta: signatures, paths, parsing errors

If the canonical docs do not exist, returns `{"exists": False}` so
callers can fall back to v5.28 behavior (ask everything) without
breaking backwards compatibility.
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

    This is the canonical entry point for skills that need to know
    project-level decisions before asking the user. Returns a structure
    suitable for downstream policy decisions:

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

    result: dict[str, Any] = {
        "has_app_prd": prd_path.exists(),
        "has_app_spec": spec_path.exists(),
        "prd": None,
        "spec": None,
        "project_path": str(root),
    }

    if result["has_app_prd"]:
        result["prd"] = _doc_to_dict(parse_document(prd_path), PRD_REQUIRED_ZONES)
    if result["has_app_spec"]:
        result["spec"] = _doc_to_dict(parse_document(spec_path), SPEC_REQUIRED_ZONES)

    if not result["has_app_prd"] and not result["has_app_spec"]:
        result["summary"] = (
            "doc/app/ no existe. Ejecuta /app-init para crear los documentos "
            "canónicos antes de continuar."
        )
    elif result["has_app_prd"] and result["has_app_spec"]:
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

    Skills call this in Paso 0 to know what they can skip asking. The
    return shape is intentionally flat and stable — it is the contract
    that `/prd`, `/plan`, `/visual-setup` rely on.

    Returns:
        {
          "audience_defined": bool,
          "audience_text": str | None,
          "scope_defined": bool,
          "veg_mode_known": bool,
          "veg_archetype": str | None,
          "stack_known": bool,
          "stack_text": str | None,
          "backend_type": "freeform" | "trello" | "plane" | None,
          "freeform_root_absolute": str | None,
          "autopilot_level": "low"|"conservador"|"equilibrado"|"agresivo" | None,
          "image_budget_eur_per_feature": float | None,
        }
    """
    docs = read_app_docs(project_path)
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
                # Best-effort extraction; the canonical source remains settings.local.json.
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
    """Register app_docs MCP tools."""

    @mcp.tool
    def read_app_docs_tool(project_path: str = ".") -> dict[str, Any]:
        """Read doc/app/app_prd.md and doc/app/app_spec.md if they exist.

        Returns structured data including parsed zones, validation errors,
        and signatures. Skills call this in their Paso 0 to know what
        questions they can skip. If the docs don't exist, returns
        {has_app_prd: false, has_app_spec: false}, which signals the
        skill to fall back to v5.28 ask-everything behavior.

        Args:
            project_path: Project root (default: current working directory).
        """
        return read_app_docs(project_path)

    @mcp.tool
    def get_inheritable_values_tool(project_path: str = ".") -> dict[str, Any]:
        """Extract a flat dict of project-level decisions ready to inherit.

        This is the high-level entry point for skills. Returns booleans
        like audience_defined, scope_defined, veg_mode_known, stack_known,
        plus the extracted values when present. Skills use this to
        decide whether to ask or use the canonical value.
        """
        return get_inheritable_values(project_path)
