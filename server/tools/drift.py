"""La puerta de desviación del CI local (US-126): lo que la rama cambia frente a la spec.

UC-12603: ``get_closed_uc_files`` dice, para unas rutas cambiadas, qué UC cerradas las cambiaron en su
cierre (``complete_uc(files=[…])``), con la propuesta de revisar sus criterios. Solo lee: la spec no
cambia hasta que una persona lo decide.

UC-12602: ``get_drift_report`` es lo que llama ``specbox drift`` (el bloque «desviacion» del CI local):
cada fichero de la rama con la UC que lo reclama o «sin UC», las dependencias que el plan no declara,
las exclusiones y las UC cerradas que toca, más el modo de la medida ``drift_gate``. Solo lee.
"""

from __future__ import annotations

import json
from typing import Any

from fastmcp import Context

from ..ac_evidence import evidence_from_comments
from ..auth_gateway import get_session_backend
from ..closed_files import NOT_SUPPORTED_NOTICE, ClosedUc, closed_uc_touches
from ..drift import build_drift_report
from ..plan_contract import parse_plan_contract
from .spec_driven import _get_uc_id, _get_us_id, _is_uc, _is_us


def closed_ucs_of(items: list[Any]) -> list[ClosedUc]:
    """Las UC hechas del tablero con la lista que guardó su cierre (None si se cerraron sin ella)."""
    stories = {i.id: _get_us_id(i) for i in items if _is_us(i)}
    out: list[ClosedUc] = []
    for item in items:
        if not _is_uc(item) or item.state != "done":
            continue
        meta = item.meta or {}
        files = meta.get("closed_files")
        out.append(ClosedUc(
            uc_id=_get_uc_id(item),
            us_id=str(meta.get("us_id") or stories.get(item.parent_id or "", "")),
            name=_display_name(item.name, _get_uc_id(item)),
            files=[f for f in files if isinstance(f, str)] if isinstance(files, list) else None,
            closed_at=meta.get("closed_files_at") if isinstance(meta.get("closed_files_at"), str) else None,
            by_repo=_by_repo(meta.get("closed_files_by_repo")),
            satellite=meta.get("satellite") if isinstance(meta.get("satellite"), str) else None,
        ))
    return out


def _by_repo(raw: Any) -> dict[str, list[str]] | None:
    if not isinstance(raw, dict):
        return None
    out = {str(k): [f for f in v if isinstance(f, str)] for k, v in raw.items() if isinstance(v, list)}
    return out or None


def _display_name(name: str, uc_id: str) -> str:
    clean = (name or "").strip()
    for prefix in (f"[{uc_id}]", f"{uc_id}:", uc_id):
        if prefix and clean.startswith(prefix):
            return clean[len(prefix):].strip(" :·-")
    return clean


async def get_closed_uc_files(
    board_id: str,
    paths: list[str],
    ctx: Context,
    exclude_uc_ids: list[str] | None = None,
    items_content: str | None = None,
    repo: str | None = None,
    satellite: str | None = None,
) -> dict[str, Any]:
    """Which closed UCs changed these files when they were closed (UC-12603). Read-only.

    Args:
        board_id: Board/project ID.
        paths: Files changed by the branch, relative to the repo.
        exclude_uc_ids: The branch's own UCs (their files are not «another UC»).
        repo: The changed repository («owner/name»); satellite: its satellite. In multirepo a closed
            UC of another repository does not count (by the repo of its PR, else by its satellite).
        items_content: FreeForm content-passing: the whole items.json for the remote MCP.

    Returns:
        `touches`: the closed UCs that changed any of the paths (those sharing more files first, up to
        20; `touches_total` counts them all), with `files` and a `proposal` to review its criteria
        (the board does not change: a person decides).
        `by_path`: path → closed UCs. `closed_without_files`: closed UCs without their list (closed
        before 6.46.0, or without `files`), which never warn, with a `notice`. Trello and Plane do not
        keep the list: `supported: false`.
    """
    if not isinstance(paths, list) or not all(isinstance(p, str) for p in paths):
        return {"error": "paths debe ser una lista de rutas (texto)", "code": "INVALID_PATHS"}
    backend = await get_session_backend(ctx, items_content=items_content)
    try:
        if not getattr(backend, "STORES_SPEC_META", False):
            return {"success": True, "supported": False, "touches": [], "touches_total": 0, "by_path": {},
                    "closed_without_files": 0, "notice": NOT_SUPPORTED_NOTICE}
        items = await backend.list_done_ucs(board_id)
        report = closed_uc_touches(closed_ucs_of(items), paths, exclude_uc_ids, repo=repo, satellite=satellite)
        return {"success": True, "supported": True, **report}
    finally:
        await backend.close()


MAX_DRIFT_FILES = 20_000
MAX_PLAN_BYTES = 2_000_000


async def _board_backend(
    ctx: Context, board_id: str, items_content: str | None, backend_type: str = ""
) -> tuple[Any | None, str]:
    """El tablero para leer, y su tipo: la sesión; si no hay, el ``items.json`` de FreeForm que llega o
    el tablero native del proyecto con el token de la conexión (la identidad del dispositivo, como
    ``set_auth_token``). ``(None, motivo)`` si no hay forma de leerlo."""
    from ..auth_gateway import BACKEND_STATE_KEY

    config = await ctx.get_state(BACKEND_STATE_KEY)
    if config:
        try:
            backend = await get_session_backend(ctx, items_content=items_content)
            return backend, str(config.get("backend_type") or "")
        except RuntimeError:
            pass  # una sesión que no sirve para esta lectura: las demás vías
    if items_content is not None:
        from ..backends.freeform_backend import FreeformBackend

        return FreeformBackend(items_content=items_content), "freeform"
    if backend_type != "native":
        what = f"el tablero {backend_type}" if backend_type else "un tablero sin tipo declarado"
        return None, f"{what} no se lee sin su sesión: solo cuenta el plan"
    from ..coordination.transport_auth import transport_token
    from .session_heartbeat import PROJECT_ID

    token = transport_token(ctx)
    if token and PROJECT_ID.match(board_id or ""):
        from ..backends.native_backend import NativeBackend

        return NativeBackend(project_id=board_id, dev_token=token), "native"
    return None, "sin sesión del tablero ni identidad del dispositivo (specbox login)"


async def _drift_mode(backend_type: str, board_id: str, policy_content: str | None) -> str:
    """El modo de la medida ``drift_gate`` del tablero («warn» si no se puede leer)."""
    from ..coordination.enforcement import effective_policy, mode_of

    raw: Any = None
    try:
        if backend_type == "native":
            from ..db.pool import get_pool

            pool = await get_pool()
            raw = await pool.fetchval("SELECT meta->'enforcement' FROM projects WHERE project_id = $1", board_id)
            raw = json.loads(raw) if isinstance(raw, str) else raw
        elif backend_type == "freeform" and policy_content:
            raw = json.loads(policy_content)
    except Exception:  # noqa: BLE001 — sin política legible, la puerta avisa y no detiene
        raw = None
    try:
        return mode_of(effective_policy(raw, backend_type=backend_type or "native"), "drift_gate")
    except Exception:  # noqa: BLE001
        return "warn"


async def get_drift_report(
    board_id: str,
    files: list[str],
    ctx: Context,
    uc_ids: list[str] | None = None,
    plan_contents: dict[str, str] | None = None,
    dependencies_added: list[dict[str, str]] | None = None,
    exclude: list[str] | None = None,
    items_content: str | None = None,
    policy_content: str | None = None,
    repo: str | None = None,
    satellite: str | None = None,
    backend_type: str = "",
) -> dict[str, Any]:
    """The drift gate's report for a branch (UC-12602). Read-only; `specbox drift` calls it.

    Args:
        board_id: Board/project ID (in multirepo, the orchestrator's).
        files: Files the branch changed (not deleted ones), relative to the repo.
        uc_ids: The branch's UCs (commit subjects, branch name or the active UC marker).
        plan_contents: The plans of those UCs, path → text, read from the orchestrator.
        dependencies_added: Dependencies the branch adds to its manifests, [{ecosystem, name, manifest}].
        exclude: The project's exclusion globs (specbox.drift.exclude).
        items_content: FreeForm content-passing: the whole items.json.
        policy_content: FreeForm: doc/tracking/policy.json, for the mode of the measure.
        repo: The branch's repository («owner/name»); satellite: its satellite in multirepo. Only
            closed UCs of the same repository are reported.
        backend_type: The board's backend as the project declares it (native, freeform, trello,
            plane): without a board session, only a native board is opened with the connection's
            identity.

    Returns:
        `files` (each with `claimed_by`, `source` plan|receipt|plan+receipt, or `excluded_by`),
        `unclaimed` («sin UC»), `exclude` and `excluded`, `dependencies` (`added`, `undeclared`),
        `closed_touches` (closed UCs the change touches, with a proposal to review their criteria;
        the spec does not change), `ok`, `mode` of the `drift_gate` measure (off|warn|block) and
        `board` (read | why it could not be read).
    """
    if not isinstance(files, list) or not all(isinstance(f, str) for f in files) or len(files) > MAX_DRIFT_FILES:
        return {"error": f"files debe ser una lista de hasta {MAX_DRIFT_FILES} rutas (texto)", "code": "INVALID_FILES"}
    plans = plan_contents or {}
    if not isinstance(plans, dict) or sum(len(str(v)) for v in plans.values()) > MAX_PLAN_BYTES:
        return {"error": "plan_contents debe ser {ruta: texto} de hasta 2 MB", "code": "INVALID_PLANS"}
    from ..drift import MAX_EXCLUDE, MAX_EXCLUDE_LEN

    if exclude is not None and (
        not isinstance(exclude, list) or len(exclude) > MAX_EXCLUDE
        or not all(isinstance(p, str) and len(p) <= MAX_EXCLUDE_LEN for p in exclude)
    ):
        return {"error": f"exclude admite hasta {MAX_EXCLUDE} globs de hasta {MAX_EXCLUDE_LEN} caracteres",
                "code": "INVALID_EXCLUDE"}
    branch = [str(u).strip().upper() for u in (uc_ids or []) if str(u).strip()]
    contracts = [(path, parse_plan_contract(str(text))) for path, text in plans.items()]

    receipts: dict[str, set[str]] = {}
    closed: list[ClosedUc] = []
    known: set[str] | None = None
    board_note = "leído"
    mode = "warn"
    backend, backend_type = await _board_backend(ctx, board_id, items_content, backend_type)
    if backend is None:
        board_note = backend_type
    else:
        try:
            items = await backend.list_board_summary(board_id)
            if getattr(backend, "STORES_SPEC_META", False):
                closed = closed_ucs_of(await backend.list_done_ucs(board_id))
            ucs = {_get_uc_id(i).upper(): i for i in items if _is_uc(i)}
            known = set(ucs)
            for uc_id in branch:
                item = ucs.get(uc_id)
                if item is None:
                    continue
                acs = await backend.get_acceptance_criteria(board_id, item.id)
                from_comments: dict[str, list[dict[str, Any]]] = {}
                if any(not ac.evidence for ac in acs):
                    from_comments = evidence_from_comments(await backend.get_comments(board_id, item.id))
                found: set[str] = set()
                for ac in acs:
                    for receipt in (ac.evidence or from_comments.get(ac.id, [])):
                        if receipt.get("passed") is not False and isinstance(receipt.get("files"), list):
                            found |= {f for f in receipt["files"] if isinstance(f, str)}
                receipts[uc_id] = found
            mode = await _drift_mode(backend_type, board_id, policy_content)
        except Exception as e:  # noqa: BLE001 — sin acceso al tablero, el informe sale con el plan
            board_note = f"no se pudo leer: {str(e)[:160]}"
            closed, receipts, known = [], {}, None
        finally:
            await backend.close()

    report = build_drift_report(
        files=files, uc_ids=branch, contracts=contracts, receipts=receipts, closed=closed,
        dependencies_added=dependencies_added, exclude=exclude, known_ucs=known, repo=repo, satellite=satellite,
    )
    return {"success": True, "board": board_note, "mode": mode, **report}


def register_spec_drift_tools(mcp_instance) -> None:
    """Registra las tools de la puerta de desviación (US-126)."""
    mcp_instance.tool(
        description="Which closed UCs changed these files when they were closed (read-only, UC-12603): "
        "pass the branch's changed paths and its own UCs as exclude_uc_ids. Returns touches (closed UC, "
        "its files, and a proposal to review its criteria; the spec does not change), by_path and "
        "closed_without_files (closed without their file list: they never warn)."
    )(get_closed_uc_files)
    mcp_instance.tool(
        description="The drift gate's report for a branch (read-only, UC-12602; `specbox drift` calls it): pass "
        "the changed files, the branch's uc_ids, the plans of those UCs (plan_contents {path: text}), the "
        "dependencies the branch adds and the project's exclusion globs. Returns each file with the UC that "
        "claims it (by the plan's **Ficheros:** lines or the criteria receipts) or «sin UC» (unclaimed), the "
        "undeclared dependencies, the excluded files, the closed UCs the change touches, ok and the mode of "
        "the drift_gate measure."
    )(get_drift_report)
