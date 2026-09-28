"""UC-3802 — El registro de proyectos solo muestra los proyectos del usuario identificado.

Origen: reporte de un tester externo (2026-09-24, punto 2). ``list_onboarded_projects``
en el MCP remoto devolvía el registro compartido entero (~100 proyectos con
descripciones de clientes, importes, NDA, URLs de repos y rutas locales) a
cualquier sesión, porque no tenía ``ctx``, identidad ni scoping.

AC-01: la tool que lista proyectos exige sesión identificada; sin identidad
       responde con el error de autenticación uniforme y sin datos.
AC-02: con identidad, el listado devuelve solo los proyectos del usuario
       (registrados por él o ligados a un proyecto native del que es miembro)
       y nunca la descripción, la ruta local ni el repositorio de los ajenos.
AC-03: estado de onboarding, matriz de versiones, registro, actualización,
       archivado y las tools de migración que tocan el registro compartido
       aplican la misma regla — una prueba por tool.
AC-04: los escritores dejan de guardar descripción y rutas locales; la purga
       del registro existente se prueba en ``test_registry_hygiene.py``.

Sin Postgres: la identidad se inyecta por el seam ``resolve_caller_scope`` de
cada módulo de tools, igual que ``test_native_unauthenticated.py`` hace con
``get_native_session`` / ``resolve_developer``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastmcp import FastMCP

from server.coordination.identity import UnauthenticatedError
from server.coordination.scope import (
    REGISTERED_BY_FIELD,
    SENSITIVE_REGISTRY_FIELDS,
    CallerScope,
    public_entry,
    resolve_caller_scope,
    stamp_owner,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

ALICE = CallerScope("alice", "Alice", frozenset({"acme/api"}))
BOB = CallerScope("bob", "Bob", frozenset({"globex/portal"}))

LEAKY_REGISTRY: dict[str, Any] = {
    "projects": {
        "acme-api": {
            "stack": "python",
            "infra": ["supabase"],
            "repo_url": "https://github.com/acme/api",
            "description": "Cliente ACME — contrato 40k€, NDA firmada",
            "registered_at": "2026-01-01T00:00:00+00:00",
            "engine_version": "6.12.0",
            "native_project_id": "acme/api",
        },
        "bobs-portal": {
            "stack": "react",
            "infra": [],
            "repo_url": "https://github.com/globex/portal",
            "description": "Portal interno de Globex — datos de RRHH",
            "path": "C:\\Users\\bob\\dev\\portal",
            "registered_at": "2026-02-01T00:00:00+00:00",
            "engine_version": "6.12.0",
            "registered_by": "bob",
        },
        "legacy-unowned": {
            "stack": "flutter",
            "infra": [],
            "repo_url": "https://github.com/someone/legacy",
            "description": "Proyecto antiguo sin dueño registrado",
            "registered_at": "2025-06-01T00:00:00+00:00",
        },
    }
}


def _unauth(*_a: Any, **_k: Any) -> Any:
    raise UnauthenticatedError("no token")


def _seed(state_path: Path, registry: dict[str, Any] = LEAKY_REGISTRY) -> None:
    state_path.mkdir(parents=True, exist_ok=True)
    (state_path / "registry.json").write_text(json.dumps(registry), encoding="utf-8")
    for name, entry in registry["projects"].items():
        d = state_path / "projects" / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "meta.json").write_text(
            json.dumps({"stack": entry["stack"], "engine_version": entry.get("engine_version", "x")}),
            encoding="utf-8",
        )


async def _onboarding_tools(state_path: Path) -> dict[str, Any]:
    from server.tools.onboarding import register_onboarding_tools

    mcp = FastMCP(name="t-onboarding")
    register_onboarding_tools(mcp, engine_path=REPO_ROOT, state_path=state_path)
    out: dict[str, Any] = {}
    for name in (
        "list_onboarded_projects",
        "get_onboarding_status",
        "onboard_project",
        "upgrade_project",
        "upgrade_all_projects",
        "get_version_matrix",
        "archive_project",
    ):
        out[name] = (await mcp.get_tool(name)).fn
    return out


async def _state_tools(state_path: Path) -> dict[str, Any]:
    from server.tools.state import register_state_tools

    mcp = FastMCP(name="t-state")
    register_state_tools(mcp, engine_path=REPO_ROOT, state_path=state_path)
    out: dict[str, Any] = {}
    for name in ("register_project", "update_project_meta"):
        out[name] = (await mcp.get_tool(name)).fn
    return out


def _assert_unauthenticated(result: Any) -> None:
    assert isinstance(result, dict)
    assert result["code"] == "UNAUTHENTICATED"
    assert result["status"] == "unauthenticated"
    assert "projects" not in result and "files" not in result
    for key in ("description", "repo_url", "path"):
        assert key not in json.dumps(result)


def _assert_no_foreign_data(result: Any) -> None:
    blob = json.dumps(result, ensure_ascii=False)
    assert "Globex" not in blob and "globex" not in blob
    assert "C:\\\\Users" not in blob and "RRHH" not in blob
    assert "legacy-unowned" not in blob and "someone/legacy" not in blob
    assert "contrato" not in blob  # descriptions are never returned, not even yours
    for field in SENSITIVE_REGISTRY_FIELDS:
        if field == "project_path":
            continue  # legitimately appears as an ARGUMENT name in the upgrade hints
        assert f'"{field}"' not in blob


# ── CallerScope (unit) ─────────────────────────────────────────────────


def test_scope_sees_own_registration_and_native_memberships():
    assert ALICE.can_see("acme-api", LEAKY_REGISTRY["projects"]["acme-api"])
    assert not ALICE.can_see("bobs-portal", LEAKY_REGISTRY["projects"]["bobs-portal"])
    assert not ALICE.can_see("legacy-unowned", LEAKY_REGISTRY["projects"]["legacy-unowned"])
    assert BOB.can_see("bobs-portal", LEAKY_REGISTRY["projects"]["bobs-portal"])
    # Native board id / mirror tenant / canonical name also bind an entry.
    assert ALICE.can_see("x", {"spec_backend": "native", "board_id": "acme/api"})
    assert ALICE.can_see("x", {"mirror": {"backend": "native", "project_id": "acme/api"}})
    assert ALICE.can_see("acme/api", {})
    assert not ALICE.can_see("x", {"spec_backend": "trello", "board_id": "acme/api"})
    assert ALICE.visible_names(LEAKY_REGISTRY["projects"]) == ["acme-api"]


def test_public_entry_is_a_whitelist_without_sensitive_fields():
    view = public_entry("bobs-portal", LEAKY_REGISTRY["projects"]["bobs-portal"])
    assert view["name"] == "bobs-portal" and view["stack"] == "react"
    assert "description" not in view and "path" not in view
    assert view[REGISTERED_BY_FIELD] == "bob"


def test_stamp_owner_attributes_and_strips():
    entry = stamp_owner({"stack": "go", "description": "x", "path": "/Users/a"}, ALICE, "acme/api")
    assert entry == {"stack": "go", REGISTERED_BY_FIELD: "alice", "native_project_id": "acme/api"}
    # An existing owner is kept (re-registering your own project).
    assert stamp_owner({REGISTERED_BY_FIELD: "carol"}, ALICE)[REGISTERED_BY_FIELD] == "carol"


async def test_resolve_caller_scope_without_context_or_token_is_unauthenticated():
    with pytest.raises(UnauthenticatedError):
        await resolve_caller_scope(None)


async def test_resolve_caller_scope_non_native_session_is_unauthenticated():
    ctx = MagicMock()
    ctx.get_state = AsyncMock(return_value={"backend_type": "freeform", "root_path": None})
    with pytest.raises(UnauthenticatedError):
        await resolve_caller_scope(ctx)


async def test_resolve_caller_scope_without_identity_db_is_unauthenticated():
    ctx = MagicMock()
    ctx.get_state = AsyncMock(return_value={"backend_type": "native", "project_id": "a/b", "dev_token": "spbx_x"})
    with patch("server.db.pool.get_pool", new=AsyncMock(side_effect=RuntimeError("no DSN"))):
        with pytest.raises(UnauthenticatedError):
            await resolve_caller_scope(ctx)


async def test_resolve_caller_scope_uses_explicit_token_and_memberships():
    dev = MagicMock(developer_id="alice", display_name="Alice")
    with patch("server.db.pool.get_pool", new=AsyncMock(return_value=object())), patch(
        "server.coordination.scope.resolve_developer", new=AsyncMock(return_value=dev)
    ), patch(
        "server.coordination.scope.list_memberships", new=AsyncMock(return_value=frozenset({"acme/api"}))
    ):
        scope = await resolve_caller_scope(None, token="spbx_alice")
    assert scope == ALICE


# ── AC-01 / AC-02: list_onboarded_projects ─────────────────────────────


async def test_ac01_list_without_identity_returns_auth_error_and_no_data(tmp_path):
    _seed(tmp_path)
    tools = await _onboarding_tools(tmp_path)
    with patch("server.tools.onboarding.resolve_caller_scope", new=AsyncMock(side_effect=_unauth)):
        result = await tools["list_onboarded_projects"](ctx=None)
    _assert_unauthenticated(result)


async def test_ac02_list_returns_only_the_callers_projects_without_sensitive_fields(tmp_path):
    _seed(tmp_path)
    tools = await _onboarding_tools(tmp_path)
    with patch("server.tools.onboarding.resolve_caller_scope", new=AsyncMock(return_value=ALICE)):
        result = await tools["list_onboarded_projects"](ctx=None)
    assert result["developer_id"] == "alice"
    assert [p["name"] for p in result["projects"]] == ["acme-api"]
    assert result["total"] == 1
    _assert_no_foreign_data(result)
    # Own public fields are still there.
    assert result["projects"][0]["repo_url"] == "https://github.com/acme/api"

    with patch("server.tools.onboarding.resolve_caller_scope", new=AsyncMock(return_value=BOB)):
        result = await tools["list_onboarded_projects"](ctx=None)
    assert [p["name"] for p in result["projects"]] == ["bobs-portal"]
    assert "description" not in result["projects"][0] and "path" not in result["projects"][0]


# ── AC-03: one test per tool ───────────────────────────────────────────


async def test_ac03_get_onboarding_status(tmp_path):
    _seed(tmp_path)
    tools = await _onboarding_tools(tmp_path)
    with patch("server.tools.onboarding.resolve_caller_scope", new=AsyncMock(side_effect=_unauth)):
        _assert_unauthenticated(await tools["get_onboarding_status"](project_name="bobs-portal", ctx=None))
    with patch("server.tools.onboarding.resolve_caller_scope", new=AsyncMock(return_value=ALICE)):
        mine = await tools["get_onboarding_status"](project_name="acme-api", ctx=None)
        theirs = await tools["get_onboarding_status"](project_name="bobs-portal", ctx=None)
        ghost = await tools["get_onboarding_status"](project_name="ghost", ctx=None)
    assert mine["registered_in_engine"] is True
    # Someone else's project answers exactly like a project that does not exist.
    assert theirs["registered_in_engine"] is False and ghost["registered_in_engine"] is False
    _assert_no_foreign_data(theirs)


async def test_ac03_get_version_matrix(tmp_path):
    _seed(tmp_path)
    tools = await _onboarding_tools(tmp_path)
    with patch("server.tools.onboarding.resolve_caller_scope", new=AsyncMock(side_effect=_unauth)):
        _assert_unauthenticated(await tools["get_version_matrix"](ctx=None))
    with patch("server.tools.onboarding.resolve_caller_scope", new=AsyncMock(return_value=BOB)):
        result = await tools["get_version_matrix"](ctx=None)
    assert [p["project"] for p in result["projects"]] == ["bobs-portal"]
    assert result["total_projects"] == 1
    assert "acme" not in json.dumps(result)


async def test_ac03_upgrade_project(tmp_path):
    _seed(tmp_path)
    tools = await _onboarding_tools(tmp_path)
    with patch("server.tools.onboarding.resolve_caller_scope", new=AsyncMock(side_effect=_unauth)):
        _assert_unauthenticated(await tools["upgrade_project"](project="acme-api", ctx=None))
    with patch("server.tools.onboarding.resolve_caller_scope", new=AsyncMock(return_value=ALICE)):
        theirs = await tools["upgrade_project"](project="bobs-portal", ctx=None)
        ghost = await tools["upgrade_project"](project="ghost", ctx=None)
        mine = await tools["upgrade_project"](project="acme-api", ctx=None)
    assert theirs["code"] == "PROJECT_NOT_VISIBLE" and ghost["code"] == "PROJECT_NOT_VISIBLE"
    # The "available" list never names other people's projects.
    assert theirs["available"] == ["acme-api"] and ghost["available"] == ["acme-api"]
    _assert_no_foreign_data(theirs)
    assert mine["project"] == "acme-api" and "files" in mine
    # Bob's meta was not touched by Alice's sweep.
    bob_meta = json.loads((tmp_path / "projects" / "bobs-portal" / "meta.json").read_text())
    assert "last_upgraded_at" not in bob_meta


async def test_ac03_upgrade_all_projects(tmp_path):
    _seed(tmp_path)
    tools = await _onboarding_tools(tmp_path)
    with patch("server.tools.onboarding.resolve_caller_scope", new=AsyncMock(side_effect=_unauth)):
        _assert_unauthenticated(await tools["upgrade_all_projects"](ctx=None))
    with patch("server.tools.onboarding.resolve_caller_scope", new=AsyncMock(return_value=ALICE)):
        result = await tools["upgrade_all_projects"](ctx=None)
    assert result["total"] == 1 and result["succeeded"] == 1
    assert [r["project"] for r in result["results"]] == ["acme-api"]
    _assert_no_foreign_data(result)


async def test_ac03_archive_project(tmp_path):
    _seed(tmp_path)
    tools = await _onboarding_tools(tmp_path)
    with patch("server.tools.onboarding.resolve_caller_scope", new=AsyncMock(side_effect=_unauth)):
        _assert_unauthenticated(await tools["archive_project"](project="acme-api", ctx=None))
    with patch("server.tools.onboarding.resolve_caller_scope", new=AsyncMock(return_value=ALICE)):
        theirs = await tools["archive_project"](project="bobs-portal", ctx=None)
        mine = await tools["archive_project"](project="acme-api", ctx=None)
    assert theirs["code"] == "PROJECT_NOT_VISIBLE"
    assert mine["status"] == "archived"
    registry = json.loads((tmp_path / "registry.json").read_text())
    assert registry["projects"]["acme-api"]["status"] == "archived"
    assert "status" not in registry["projects"]["bobs-portal"]


async def test_ac03_onboard_project_registers_attributed_and_refuses_taken_names(tmp_path):
    _seed(tmp_path)
    tools = await _onboarding_tools(tmp_path)
    with patch("server.tools.onboarding.resolve_caller_scope", new=AsyncMock(side_effect=_unauth)):
        result = await tools["onboard_project"](project="new-one", stack="python", backend_type="freeform")
    _assert_unauthenticated(result)
    assert not (tmp_path / "projects" / "new-one").exists()

    with patch("server.tools.onboarding.resolve_caller_scope", new=AsyncMock(return_value=ALICE)):
        taken = await tools["onboard_project"](project="bobs-portal", stack="python", backend_type="freeform")
        fresh = await tools["onboard_project"](
            project="new-one", stack="python", backend_type="native", native_project_id="acme/api"
        )
        bad = await tools["onboard_project"](project="x", backend_type="native", native_project_id="not canonical!")
    assert taken["code"] == "PROJECT_NAME_TAKEN" and "files" not in taken
    assert fresh["registered_in_state"] is True
    assert bad["code"] == "INVALID_PROJECT_ID"
    registry = json.loads((tmp_path / "registry.json").read_text())
    entry = registry["projects"]["new-one"]
    assert entry[REGISTERED_BY_FIELD] == "alice" and entry["native_project_id"] == "acme/api"
    assert "description" not in entry  # AC-04
    # Bob's entry survived untouched.
    assert registry["projects"]["bobs-portal"]["registered_by"] == "bob"


async def test_ac03_register_project(tmp_path):
    _seed(tmp_path)
    tools = await _state_tools(tmp_path)
    with patch("server.tools.state.resolve_caller_scope", new=AsyncMock(side_effect=_unauth)):
        _assert_unauthenticated(await tools["register_project"](project="mine", ctx=None))
    with patch("server.tools.state.resolve_caller_scope", new=AsyncMock(return_value=ALICE)):
        taken = await tools["register_project"](project="bobs-portal", ctx=None)
        fresh = await tools["register_project"](
            project="mine", stack="go", repo_url="https://github.com/acme/mine",
            description="Cliente secreto 99k€", ctx=None,
        )
        again = await tools["register_project"](project="mine", stack="go", ctx=None)
    assert taken["code"] == "PROJECT_NAME_TAKEN"
    assert fresh["action"] == "registered" and fresh[REGISTERED_BY_FIELD] == "alice"
    assert "description" in fresh["ignored"]  # AC-04: accepted, never stored
    assert again["action"] == "updated"
    registry = json.loads((tmp_path / "registry.json").read_text())
    entry = registry["projects"]["mine"]
    assert entry[REGISTERED_BY_FIELD] == "alice" and "description" not in entry
    meta = json.loads((tmp_path / "projects" / "mine" / "meta.json").read_text())
    assert "description" not in meta and meta[REGISTERED_BY_FIELD] == "alice"
    assert "99k" not in (tmp_path / "registry.json").read_text()


async def test_ac03_update_project_meta(tmp_path):
    _seed(tmp_path)
    tools = await _state_tools(tmp_path)
    with patch("server.tools.state.resolve_caller_scope", new=AsyncMock(side_effect=_unauth)):
        _assert_unauthenticated(await tools["update_project_meta"](project="acme-api", stack="go", ctx=None))
    with patch("server.tools.state.resolve_caller_scope", new=AsyncMock(return_value=ALICE)):
        theirs = await tools["update_project_meta"](project="bobs-portal", stack="go", ctx=None)
        mine = await tools["update_project_meta"](project="acme-api", stack="go", description="nuevo texto", ctx=None)
    assert theirs["code"] == "PROJECT_NOT_VISIBLE" and theirs["available"] == ["acme-api"]
    assert mine["status"] == "ok" and mine["meta"]["stack"] == "go"
    assert "description" in mine["ignored"]
    registry = json.loads((tmp_path / "registry.json").read_text())
    assert registry["projects"]["acme-api"]["stack"] == "go"
    assert "description" not in registry["projects"]["acme-api"]  # legacy field purged on write (AC-04)
    assert registry["projects"]["bobs-portal"]["stack"] == "react"


# ── AC-03: migration tools on the shared switch registry ───────────────


def _seed_switch_registry(state_path: Path) -> None:
    state_path.mkdir(parents=True, exist_ok=True)
    (state_path / "projects.json").write_text(
        json.dumps({"projects": {
            "bobs-portal": {"spec_backend": "trello", "board_id": "b1", "registered_by": "bob"},
            "acme-api": {"spec_backend": "freeform", "board_id": "ff", "registered_by": "alice"},
        }}),
        encoding="utf-8",
    )


async def test_ac03_switch_backend(tmp_path, monkeypatch):
    from server.tools.migration import switch_backend

    _seed_switch_registry(tmp_path)
    monkeypatch.setenv("STATE_PATH", str(tmp_path))
    ctx = AsyncMock()
    with patch("server.tools.migration.resolve_caller_scope", new=AsyncMock(side_effect=_unauth)):
        _assert_unauthenticated(await switch_backend("acme-api", "trello", "b9", ctx))
    with patch("server.tools.migration.resolve_caller_scope", new=AsyncMock(return_value=ALICE)):
        theirs = await switch_backend("bobs-portal", "plane", "p1", ctx)
    assert theirs["code"] == "PROJECT_NOT_VISIBLE" and theirs["available"] == ["acme-api"]
    # Bob's entry is untouched.
    registry = json.loads((tmp_path / "projects.json").read_text())
    assert registry["projects"]["bobs-portal"]["spec_backend"] == "trello"


async def test_ac03_switch_project_backend(tmp_path, monkeypatch):
    from server.tools.migration import switch_project_backend

    _seed_switch_registry(tmp_path)
    monkeypatch.setenv("STATE_PATH", str(tmp_path))
    ctx = AsyncMock()
    with patch("server.tools.migration.resolve_caller_scope", new=AsyncMock(side_effect=_unauth)):
        result = await switch_project_backend("acme-api", "freeform", "trello", ctx, source_content="[]")
    _assert_unauthenticated(result)
    with patch("server.tools.migration.resolve_caller_scope", new=AsyncMock(return_value=ALICE)):
        theirs = await switch_project_backend("bobs-portal", "trello", "plane", ctx, dry_run=True)
    assert theirs["code"] == "PROJECT_NOT_VISIBLE"
    assert "b1" not in json.dumps(theirs)


async def test_ac03_enable_and_disable_mirror(tmp_path, monkeypatch):
    from server.tools import migration as migration_tools

    _seed_switch_registry(tmp_path)
    monkeypatch.setenv("STATE_PATH", str(tmp_path))
    ctx = AsyncMock()
    ctx.get_state = AsyncMock(return_value={"backend_type": "trello", "api_key": "k", "token": "t"})

    async def fake_provision(pool, dev_token, target_project_id):
        return True

    async def fake_auth(pool, *, token, project_id):
        return None

    async def fake_pool():
        return object()

    monkeypatch.setattr(migration_tools, "_maybe_auto_provision", fake_provision)
    import server.coordination.identity as identity_mod
    import server.db.pool as pool_mod

    monkeypatch.setattr(identity_mod, "authenticate_and_authorize_cached", fake_auth)
    monkeypatch.setattr(pool_mod, "get_pool", fake_pool)

    with patch("server.tools.migration.resolve_caller_scope", new=AsyncMock(side_effect=_unauth)):
        _assert_unauthenticated(await migration_tools.enable_mirror("acme-api", "acme/api", "spbx_t", ctx))
        _assert_unauthenticated(await migration_tools.disable_mirror("acme-api", ctx))
    with patch("server.tools.migration.resolve_caller_scope", new=AsyncMock(return_value=ALICE)):
        theirs = await migration_tools.enable_mirror("bobs-portal", "acme/api", "spbx_t", ctx)
        theirs_off = await migration_tools.disable_mirror("bobs-portal", ctx)
    assert theirs["code"] == "PROJECT_NOT_VISIBLE" and theirs_off["code"] == "PROJECT_NOT_VISIBLE"
    registry = json.loads((tmp_path / "projects.json").read_text())
    assert "mirror" not in registry["projects"]["bobs-portal"]


def test_ac03_mirror_auto_seeded_entry_is_attributed(tmp_path):
    from server.migration.transactional_switch import _write_registry_mirror

    _write_registry_mirror("fresh", "acme/api", str(tmp_path), "trello", "b1", registered_by="alice")
    registry = json.loads((tmp_path / "projects.json").read_text())
    entry = registry["projects"]["fresh"]
    assert entry["registered_by"] == "alice" and entry["mirror"]["project_id"] == "acme/api"
    assert ALICE.can_see("fresh", entry) and not BOB.can_see("fresh", entry)


# ── AC-04: writers never store description / local paths ───────────────


def test_ac04_auto_register_stores_no_description(tmp_path):
    from server.tools.state import _auto_register

    _auto_register(tmp_path, "telemetry-only")
    entry = json.loads((tmp_path / "registry.json").read_text())["projects"]["telemetry-only"]
    assert "description" not in entry and REGISTERED_BY_FIELD not in entry
    # Unattributed: invisible to everyone until claimed or registered explicitly.
    assert not ALICE.can_see("telemetry-only", entry)
