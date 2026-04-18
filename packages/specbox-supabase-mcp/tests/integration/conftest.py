"""Integration-only fixtures: real Supabase Management API teardown.

Skipped unless SUPABASE_CI_ACCESS_TOKEN + SUPABASE_CI_PROJECT_REF are set.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import httpx
import pytest


def _teardown_specbox_ci(access_token: str, project_ref: str) -> None:
    """Delete every secret whose name starts with SPECBOX_CI_."""
    url = f"https://api.supabase.com/v1/projects/{project_ref}/secrets"
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        list_resp = httpx.get(url, headers=headers, timeout=10.0)
        if list_resp.status_code != 200:
            return
        names_to_delete = [
            item["name"]
            for item in (list_resp.json() or [])
            if str(item.get("name", "")).startswith("SPECBOX_CI_")
        ]
        if names_to_delete:
            httpx.request(
                "DELETE", url, headers=headers, json=names_to_delete, timeout=10.0
            )
    except Exception:
        # Best-effort cleanup; never raise from teardown.
        pass


@pytest.fixture
def ci_credentials() -> tuple[str, str]:
    token = os.environ["SUPABASE_CI_ACCESS_TOKEN"]
    ref = os.environ["SUPABASE_CI_PROJECT_REF"]
    return token, ref


@pytest.fixture(autouse=True)
def supabase_teardown(ci_credentials: tuple[str, str]) -> Iterator[None]:
    token, ref = ci_credentials
    _teardown_specbox_ci(token, ref)
    try:
        yield
    finally:
        _teardown_specbox_ci(token, ref)
