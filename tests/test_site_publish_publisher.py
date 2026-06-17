"""Tests del publicador de site_publish (UC-1602, US-16).

Cubren AC-01 (UPSERT idempotente — merge-duplicates), AC-02 (is_current reset + current
true), AC-03 (credencial de servicio, nunca impresa). Sin red: cliente HTTP mock.
"""

import pytest

from server.site_publish.parser import (
    ChangelogEntry,
    EngineState,
    FeatureInfo,
    ReleaseInfo,
)
from server.site_publish.publisher import (
    MissingCredentialsError,
    PublishCredentials,
    build_publish_requests,
    publish,
    _redact,
)


def _state() -> EngineState:
    return EngineState(
        release=ReleaseInfo(version="6.11.0", codename="Self Update",
                            release_date="2026-06-14", min_claude_code="1.0.0"),
        features=[FeatureInfo("agent-skills", since_version="3.9.1")],
        stacks={"python": "3.12+"},
        services=["supabase"],
        project_managers=["trello"],
        changelog=[
            ChangelogEntry(version="6.11.0", codename="Self Update",
                          release_date="2026-06-14", public_highlights=["A", "B"]),
            ChangelogEntry(version="6.10.2", codename="Mirror Bootstrap",
                          release_date="2026-06-12", public_highlights=["C"]),
        ],
    )


class _FakeResp:
    def __init__(self, status_code=200, text="ok"):
        self.status_code = status_code
        self.text = text


class _FakeClient:
    """Captura las requests; responde 200 salvo que se configure un fallo."""

    def __init__(self, fail_on=None, fail_status=500):
        self.calls = []
        self.fail_on = fail_on
        self.fail_status = fail_status

    def request(self, method, url, params=None, json=None, headers=None):
        self.calls.append({"method": method, "url": url, "params": params,
                           "json": json, "headers": headers})
        if self.fail_on is not None and len(self.calls) - 1 == self.fail_on:
            return _FakeResp(self.fail_status, "boom")
        return _FakeResp(200, "ok")


CREDS = PublishCredentials(url="https://x.supabase.co", service_role_key="svc_secret_key_123")


# ---------------------------------------------------------------------------
# AC-01 — UPSERT idempotente
# ---------------------------------------------------------------------------

def test_all_upserts_use_merge_duplicates():
    reqs = build_publish_requests(_state())
    # Todo POST (upsert) debe llevar Prefer: resolution=merge-duplicates.
    posts = [r for r in reqs if r.method == "POST"]
    assert posts, "debe haber upserts"
    for r in posts:
        assert r.prefer == "resolution=merge-duplicates"


def test_requests_are_deterministic():
    a = build_publish_requests(_state())
    b = build_publish_requests(_state())
    assert [(r.method, r.path, r.json) for r in a] == [(r.method, r.path, r.json) for r in b]


def test_publish_runs_all_steps_ok():
    client = _FakeClient()
    result = publish(_state(), CREDS, client)
    assert result.ok
    assert result.steps == len(client.calls)
    # Targets esperados.
    paths = {c["url"].rsplit("/rest/v1/", 1)[-1].split("?")[0] for c in client.calls}
    assert {"engine_release", "engine_feature", "engine_changelog_entry"} <= {
        c["url"].split("/rest/v1/")[-1] for c in client.calls
    }


# ---------------------------------------------------------------------------
# AC-02 — is_current
# ---------------------------------------------------------------------------

def test_first_step_resets_is_current():
    reqs = build_publish_requests(_state())
    first = reqs[0]
    assert first.method == "PATCH"
    assert first.path.endswith("/engine_release")
    assert first.params.get("is_current") == "eq.true"
    assert first.json == {"is_current": False}


def test_current_release_marked_current_others_not():
    reqs = build_publish_requests(_state())
    # El upsert de la versión actual lleva is_current=true.
    current_upserts = [
        r for r in reqs
        if r.method == "POST" and r.path.endswith("/engine_release")
        and isinstance(r.json, list) and len(r.json) == 1
        and r.json[0]["version"] == "6.11.0"
    ]
    assert len(current_upserts) == 1
    assert current_upserts[0].json[0]["is_current"] is True
    # El histórico (varias filas) va con is_current=false.
    history = [
        r for r in reqs
        if r.method == "POST" and r.path.endswith("/engine_release")
        and isinstance(r.json, list) and len(r.json) > 1
    ]
    for r in history:
        for row in r.json:
            assert row["is_current"] is False


# ---------------------------------------------------------------------------
# AC-03 — credencial de servicio, nunca impresa
# ---------------------------------------------------------------------------

def test_uses_service_role_in_headers():
    client = _FakeClient()
    publish(_state(), CREDS, client)
    for call in client.calls:
        assert call["headers"]["apikey"] == "svc_secret_key_123"
        assert call["headers"]["Authorization"] == "Bearer svc_secret_key_123"


def test_error_message_redacts_secret():
    client = _FakeClient(fail_on=2)  # falla en un paso intermedio
    result = publish(_state(), CREDS, client)
    assert not result.ok
    assert result.failed_step == 2
    assert "svc_secret_key_123" not in result.message
    assert "REDACTED" in _redact("token svc_secret_key_123 leaked", "svc_secret_key_123")


def test_missing_credentials_raises():
    with pytest.raises(MissingCredentialsError):
        PublishCredentials.from_env({})  # sin URL ni key


def test_credentials_from_env_ok():
    creds = PublishCredentials.from_env({
        "SUPABASE_URL": "https://x.supabase.co/",
        "SUPABASE_SERVICE_ROLE_KEY": "k",
    })
    assert creds.url == "https://x.supabase.co"  # trailing slash recortado
    assert creds.service_role_key == "k"
