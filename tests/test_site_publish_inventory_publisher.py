"""Tests del publicador de inventario (UC-2002, US-20).

Cubren AC-06 (UPSERT idempotente merge-duplicates a las 4 tablas), AC-07 (credencial
service-role nunca logueada) y AC-08 (fallo HTTP → PublishResult(ok=False) sin excepción).
"""

import pytest

from server.site_publish.inventory import (
    AgentInfo,
    CapabilityInventory,
    SkillInfo,
    ToolInfo,
    VscodeExtInfo,
    build_inventory_publish_requests,
    publish_inventory,
)
from server.site_publish.publisher import MissingCredentialsError, PublishCredentials


class _FakeResp:
    def __init__(self, status_code=200, text="ok"):
        self.status_code = status_code
        self.text = text


class _FakeClient:
    """Captura las requests; responde 200 salvo que se configure un fallo en un índice."""

    def __init__(self, fail_on=None, fail_status=500, fail_text="boom"):
        self.calls = []
        self.fail_on = fail_on
        self.fail_status = fail_status
        self.fail_text = fail_text

    def request(self, method, url, params=None, json=None, headers=None):
        self.calls.append(
            {"method": method, "url": url, "params": params, "json": json, "headers": headers}
        )
        if self.fail_on is not None and len(self.calls) - 1 == self.fail_on:
            return _FakeResp(self.fail_status, self.fail_text)
        return _FakeResp(200, "ok")


CREDS = PublishCredentials(url="https://x.supabase.co", service_role_key="svc_secret_key_123")


def _inventory() -> CapabilityInventory:
    return CapabilityInventory(
        agents=[AgentInfo(agent_key="orchestrator", name="Orchestrator", role="Coordina.")],
        tools=[ToolInfo(tool_name="get_engine_version", module="server/tools/engine.py")],
        skills=[SkillInfo(skill_key="prd", command="/prd", description="Generate PRDs.")],
        vscode_ext=VscodeExtInfo(
            marketplace_id="EmbedBuild.specbox-engine",
            name="specbox-engine",
            publisher="EmbedBuild",
            version="6.11.0",
        ),
    )


# ---------------------------------------------------------------------------
# AC-06 — UPSERT idempotente a las 4 tablas
# ---------------------------------------------------------------------------
def test_requests_target_four_tables():
    reqs = build_inventory_publish_requests(_inventory())
    paths = [r.path for r in reqs]
    assert paths == [
        "/rest/v1/engine_agent",
        "/rest/v1/engine_tool",
        "/rest/v1/engine_skill",
        "/rest/v1/engine_vscode_ext",
    ]


def test_all_upserts_use_merge_duplicates():
    reqs = build_inventory_publish_requests(_inventory())
    assert reqs, "debe haber upserts"
    for r in reqs:
        assert r.method == "POST"
        assert r.prefer == "resolution=merge-duplicates"


def test_idempotent_same_requests_twice():
    inv = _inventory()
    a = build_inventory_publish_requests(inv)
    b = build_inventory_publish_requests(inv)
    assert [r.path for r in a] == [r.path for r in b]
    assert [r.json for r in a] == [r.json for r in b]


def test_empty_inventory_no_requests():
    assert build_inventory_publish_requests(CapabilityInventory()) == []


def test_empty_surfaces_skipped():
    """Una superficie vacía no genera petición (evita POST con body [])."""
    inv = CapabilityInventory(
        agents=[AgentInfo(agent_key="o", name="O")],  # solo agentes
    )
    reqs = build_inventory_publish_requests(inv)
    assert [r.path for r in reqs] == ["/rest/v1/engine_agent"]


# ---------------------------------------------------------------------------
# AC-07 — credencial service-role nunca logueada
# ---------------------------------------------------------------------------
def test_missing_credentials_raises():
    with pytest.raises(MissingCredentialsError):
        PublishCredentials.from_env({})


def test_publish_inventory_ok_sends_all():
    client = _FakeClient()
    result = publish_inventory(_inventory(), CREDS, client)
    assert result.ok is True
    assert result.steps == 4
    assert len(client.calls) == 4
    # la credencial viaja en headers pero el resultado nunca la expone
    assert "svc_secret_key_123" not in result.message


def test_credential_redacted_on_error():
    # El servidor devuelve un body que contiene la credencial → debe redactarse.
    client = _FakeClient(fail_on=0, fail_status=401, fail_text="bad key svc_secret_key_123 here")
    result = publish_inventory(_inventory(), CREDS, client)
    assert result.ok is False
    assert "svc_secret_key_123" not in result.message
    assert "***REDACTED***" in result.message


# ---------------------------------------------------------------------------
# AC-08 — fallo HTTP → PublishResult(ok=False) sin excepción
# ---------------------------------------------------------------------------
def test_http_failure_returns_result_not_raises():
    client = _FakeClient(fail_on=1, fail_status=500)
    result = publish_inventory(_inventory(), CREDS, client)
    assert result.ok is False
    assert result.failed_step == 1
    assert "HTTP 500" in result.message
