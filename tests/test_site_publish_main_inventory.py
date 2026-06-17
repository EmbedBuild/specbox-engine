"""Tests del entrypoint __main__ con inventario (UC-2003, US-20).

Cubren AC-09 (una sola invocación publica release/changelog E inventario — peticiones a las 4
tablas engine_* nuevas además de las 3 existentes) y AC-10 (resumen con conteos, exit codes,
credencial no filtrada). El cliente httpx se mockea vía monkeypatch para no tocar la red.
"""

from pathlib import Path

import pytest

from server.site_publish import __main__ as main_mod

ENGINE_ROOT = Path(__file__).resolve().parents[1]


class _FakeResp:
    def __init__(self, status_code=200, text="ok"):
        self.status_code = status_code
        self.text = text


class _FakeClient:
    """Cliente httpx-compatible que captura todas las requests. Context manager."""

    instances = []

    def __init__(self, *args, fail_on=None, **kwargs):
        self.calls = []
        self.fail_on = fail_on
        _FakeClient.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def request(self, method, url, params=None, json=None, headers=None):
        self.calls.append({"method": method, "url": url, "path": url})
        if self.fail_on is not None and len(self.calls) - 1 == self.fail_on:
            return _FakeResp(500, "boom")
        return _FakeResp(200, "ok")


@pytest.fixture(autouse=True)
def _reset_instances():
    _FakeClient.instances = []
    yield
    _FakeClient.instances = []


@pytest.fixture
def _env(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "svc_secret_key_123")


# ---------------------------------------------------------------------------
# AC-09 — una invocación publica release/changelog E inventario
# ---------------------------------------------------------------------------
def test_main_publishes_release_and_inventory(monkeypatch, _env, capsys):
    monkeypatch.setattr(main_mod.httpx, "Client", _FakeClient)
    rc = main_mod.main([str(ENGINE_ROOT)])
    assert rc == 0

    # Todas las requests emitidas en la run (mismo cliente reutilizado para ambos).
    all_paths = [c["url"] for inst in _FakeClient.instances for c in inst.calls]
    # Las 4 tablas nuevas del inventario.
    for table in ("engine_agent", "engine_tool", "engine_skill", "engine_vscode_ext"):
        assert any(table in p for p in all_paths), f"falta publicar {table}"
    # Y las 3 existentes de release/changelog.
    for table in ("engine_release", "engine_feature", "engine_changelog_entry"):
        assert any(table in p for p in all_paths), f"falta publicar {table}"


# ---------------------------------------------------------------------------
# AC-10 — resumen con conteos, sin filtrar credencial
# ---------------------------------------------------------------------------
def test_main_prints_inventory_counts(monkeypatch, _env, capsys):
    monkeypatch.setattr(main_mod.httpx, "Client", _FakeClient)
    rc = main_mod.main([str(ENGINE_ROOT)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "agentes" in out and "tools" in out and "skills" in out
    assert "svc_secret_key_123" not in out  # credencial nunca impresa


# ---------------------------------------------------------------------------
# AC-08/AC-10 — exit codes
# ---------------------------------------------------------------------------
def test_main_missing_credentials_exit_2(monkeypatch, capsys):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.setattr(main_mod.httpx, "Client", _FakeClient)
    rc = main_mod.main([str(ENGINE_ROOT)])
    assert rc == 2


def test_main_http_failure_exit_3(monkeypatch, _env):
    # Falla en la primera request (release) → exit 3, no aborta con excepción.
    monkeypatch.setattr(
        main_mod.httpx, "Client", lambda *a, **k: _FakeClient(fail_on=0)
    )
    rc = main_mod.main([str(ENGINE_ROOT)])
    assert rc == 3
