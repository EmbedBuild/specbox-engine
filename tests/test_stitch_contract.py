"""US-84 · UC-8408 — every call of the Stitch client matches the Stitch schema.

The snapshot of ``tools/list`` (``.quality/evidence/stitch_smoke/
mcp_tools_schema.json``, refreshed with ``python -m server.stitch_schema``)
already required ``name``, ``designSystem`` and ``selectedScreenIds`` in May,
but nothing checked the client against it: the smoke tests called the API by
hand and the unit tests mocked the client's own arguments. Here each method
sends its request to a mock, and the ``arguments`` are validated with JSON
Schema against the snapshot: a missing required field, an unknown field or a
value outside an enum fails.

A call that is still known to be wrong is marked ``xfail(strict=True)`` with
the use case that fixes it: when the fix lands the test passes, strict xfail
turns that into a failure, and the mark has to go. ``pytest --runxfail``
shows every known break at once.
"""

from __future__ import annotations

import contextlib
import inspect
import json

import httpx
import pytest
import respx
from jsonschema import Draft202012Validator

from server.stitch_client import STITCH_MCP_URL, StitchClient, StitchClientError
from server.stitch_schema import closed, input_schema, load_schema

SCHEMA = load_schema()
THEME = {
    "colorMode": "LIGHT",
    "headlineFont": "INTER",
    "bodyFont": "INTER",
    "roundness": "ROUND_EIGHT",
    "customColor": "#0EA5E9",
}
INSTANCE = {"id": "inst-1", "sourceScreen": "projects/123/screens/abc"}


def _known_break(uc: str, why: str):
    return pytest.mark.xfail(strict=True, reason=f"{uc}: {why}")


# (method, positional args, keyword args) — one representative call per method.
CASES = [
    pytest.param("create_project", ("Demo",), {}, id="create_project"),
    pytest.param("list_projects", (), {}, id="list_projects"),
    pytest.param("list_projects", ("shared",), {}, id="list_projects_shared"),
    pytest.param("get_project", ("123",), {}, id="get_project"),
    pytest.param("list_screens", ("123",), {}, id="list_screens"),
    pytest.param("get_screen", ("123", "abc"), {}, id="get_screen"),
    pytest.param("fetch_screen_code", ("123", "abc"), {}, id="fetch_screen_code"),
    pytest.param("fetch_screen_image", ("123", "abc"), {}, id="fetch_screen_image"),
    pytest.param("generate_screen_from_text", ("123", "A login page in light mode"), {}, id="generate_screen_from_text"),
    pytest.param(
        "generate_screen_from_text", ("123", "A login page"), {"design_system": "9", "device_type": "AGNOSTIC"},
        id="generate_screen_with_design_system",
    ),
    pytest.param("edit_screens", ("123", "abc", "Make the button blue"), {}, id="edit_screens"),
    pytest.param(
        "generate_variants", ("123", "abc"),
        {"prompt": "More playful", "aspects": ["LAYOUT"], "device_type": "MOBILE", "model_id": "GEMINI_3_8_FLASH"},
        id="generate_variants",
    ),
    pytest.param("upload_design_md", ("123", "# Design\n"), {}, id="upload_design_md"),
    pytest.param("create_design_system", ("123", "Tinta", THEME), {}, id="create_design_system"),
    pytest.param(
        "create_design_system_from_design_md", ("123", INSTANCE), {}, id="create_design_system_from_design_md",
    ),
    pytest.param(
        "update_design_system", ("assets/1", "123", THEME), {"display_name": "Tinta"}, id="update_design_system",
    ),
    pytest.param("list_design_systems", ("123",), {}, id="list_design_systems"),
    pytest.param("list_design_systems", (None,), {}, id="list_design_systems_global"),
    pytest.param("create_design_system", (None, "Tinta", THEME), {}, id="create_design_system_global"),
    pytest.param("apply_design_system", ("123", "1", [INSTANCE]), {}, id="apply_design_system"),
]


def _ok() -> httpx.Response:
    return httpx.Response(
        200, json={"jsonrpc": "2.0", "id": "x", "result": {"content": [{"type": "text", "text": "{}"}]}}
    )


async def _sent(method: str, args: tuple, kwargs: dict) -> tuple[str, dict]:
    """The first tool call a method makes (the fetch_* methods then download a URL)."""
    client = StitchClient(api_key="test-api-key-12345678")
    with respx.mock:
        route = respx.post(STITCH_MCP_URL).mock(return_value=_ok())
        with contextlib.suppress(StitchClientError):
            await getattr(client, method)(*args, **kwargs)
        params = json.loads(route.calls[0].request.content)["params"]
    await client.close()
    return params["name"], params["arguments"]


@pytest.mark.parametrize(("method", "args", "kwargs"), CASES)
async def test_call_matches_stitch_schema(method, args, kwargs):
    tool, arguments = await _sent(method, args, kwargs)
    schema = input_schema(tool, SCHEMA)
    assert schema is not None, f"{method} calls «{tool}», which Stitch does not have"
    errors = sorted(
        Draft202012Validator(closed(schema)).iter_errors(arguments),
        key=lambda e: list(e.absolute_path),
    )
    assert not errors, f"{method} → {tool}: " + "; ".join(
        f"{'/'.join(map(str, e.absolute_path)) or '(root)'}: {e.message}" for e in errors
    )


def test_every_client_call_has_a_case():
    """A new method that calls Stitch needs its contract case."""
    covered = {case.values[0] for case in CASES}
    not_mcp = {"close", "upload_via_rest_batch_create"}  # REST upload, no MCP tool
    calls_stitch = {
        name
        for name, _ in inspect.getmembers(StitchClient, inspect.iscoroutinefunction)
        if not name.startswith("_") and name not in not_mcp
    }
    assert calls_stitch == covered, (
        f"without a case: {sorted(calls_stitch - covered)}; stale cases: {sorted(covered - calls_stitch)}"
    )


def test_snapshot_is_the_current_api():
    assert SCHEMA["tool_count"] == len(SCHEMA["tools"]) == 15
    assert SCHEMA["fetched_at"] >= "2026-10-05"
    names = {t["name"] for t in SCHEMA["tools"]}
    assert {"get_project", "get_screen", "delete_project", "generate_variants"} <= names
    assert not names & {"fetch_screen_code", "fetch_screen_image"}


class TestClosedSchema:
    """The validator rejects what Stitch rejects."""

    def _validator(self, tool: str) -> Draft202012Validator:
        return Draft202012Validator(closed(input_schema(tool, SCHEMA)))

    def test_unknown_field_fails(self):
        assert list(self._validator("list_screens").iter_errors({"projectId": "1", "extra": True}))

    def test_missing_required_fails(self):
        assert list(self._validator("get_screen").iter_errors({}))

    def test_value_outside_enum_fails(self):
        args = {"projectId": "1", "prompt": "x", "modelId": "GEMINI_3_PRO"}
        assert list(self._validator("generate_screen_from_text").iter_errors(args))

    def test_nested_definition_is_closed(self):
        args = {"designSystem": {"displayName": "x", "theme": {**THEME, "font": "INTER"}}}
        assert list(self._validator("create_design_system").iter_errors(args))
