"""Test fixtures shared across unit and integration suites."""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

_SRC = Path(__file__).parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


@pytest.fixture(autouse=True)
def _isolate_heartbeat(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Prevent tests from hitting the real SpecBox engine URL."""
    monkeypatch.delenv("SPECBOX_ENGINE_MCP_URL", raising=False)
    monkeypatch.delenv("SPECBOX_SYNC_TOKEN", raising=False)
    yield


def pytest_collection_modifyitems(config, items):  # type: ignore[no-untyped-def]
    """Skip integration tests unless STRIPE_CI_SECRET_KEY is set."""
    if os.getenv("STRIPE_CI_SECRET_KEY"):
        return
    skip_mark = pytest.mark.skip(reason="STRIPE_CI_SECRET_KEY not set")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_mark)
