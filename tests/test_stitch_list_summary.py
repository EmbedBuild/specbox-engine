"""The list of Stitch projects does not fill the conversation (UC-11303).

With 38 real projects, ``stitch_list_projects`` answered 412 KB: the theme and
the position of every screen were 93 % of it. By default each project is now a
summary (enough to pick one); ``full=True`` gives Stitch's answer untouched.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastmcp import Client, FastMCP

from server.stitch_client import StitchClient
from server.tools.stitch import register_stitch_tools, summarize_project_list

PROJECT = "demo"


def stitch_answer(projects: int = 38, screens: int = 141) -> dict:
    """The shape Stitch answers with, sized like the account of the report."""

    return {
        "projects": [
            {
                "name": f"projects/{5000000000000000000 + i}",
                "title": f"Proyecto {i + 1}",
                "visibility": "PRIVATE",
                "createTime": "2026-02-06T22:03:48.324742Z",
                "updateTime": "2026-10-24T13:28:38.422274Z",
                "projectType": "TEXT_TO_UI_PRO",
                "thumbnailScreenshot": {"name": f"projects/{i}/files/t", "downloadUrl": "https://x.test/" + "t" * 300},
                "origin": "STITCH",
                "deviceType": "DESKTOP" if i % 2 else "MOBILE",
                "designTheme": {"colorMode": "LIGHT", "font": "INTER", "roundness": "ROUND_EIGHT",
                                "customColor": "#3B82F6", "designMd": "x" * 4800},
                "screenInstances": [
                    {"id": f"s{i}-{k}", "sourceScreen": f"projects/{i}/screens/{k}", "y": 900 * k, "width": 1440, "height": 900}
                    for k in range(screens if i % 3 == 0 else 12)
                ],
                "metadata": {"userRole": "OWNER"},
            }
            for i in range(projects)
        ]
    }


@pytest.fixture
def server(monkeypatch, tmp_path: Path) -> FastMCP:
    monkeypatch.delenv("STITCH_API_KEY", raising=False)
    monkeypatch.setenv("MCP_TRANSPORT", "http")  # as on the hosted MCP: no usage log on disk

    async def fake_list_projects(self, view=None):
        return stitch_answer()

    monkeypatch.setattr(StitchClient, "list_projects", fake_list_projects)
    mcp = FastMCP("stitch-list-test")
    register_stitch_tools(mcp, tmp_path)
    return mcp


async def _list(server: FastMCP, **args) -> tuple[dict, int]:
    async with Client(server) as client:
        await client.call_tool("stitch_set_api_key", {"project": PROJECT, "api_key": "key-for-the-test-1234"})
        result = await client.call_tool("stitch_list_projects", {"project": PROJECT, **args}, raise_on_error=False)
    payload = result.structured_content
    return payload, len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))


async def test_ac01_38_projects_take_less_than_20_kb(server):
    payload, size = await _list(server)
    _, full_size = await _list(server, full=True)
    assert len(payload["result"]["projects"]) == 38
    assert size < 20_000, size
    assert full_size > 300_000  # what it answered before


async def test_ac02_each_project_shows_what_it_takes_to_pick_it(server):
    payload, _ = await _list(server)
    first, second = payload["result"]["projects"][:2]
    assert first == {
        "id": "5000000000000000000",
        "name": "projects/5000000000000000000",
        "title": "Proyecto 1",
        "updateTime": "2026-10-24T13:28:38.422274Z",
        "createTime": "2026-02-06T22:03:48.324742Z",
        "deviceType": "MOBILE",
        "projectType": "TEXT_TO_UI_PRO",
        "visibility": "PRIVATE",
        "screens": 141,
    }
    assert second["screens"] == 12 and second["deviceType"] == "DESKTOP"
    assert payload["result"]["detail"] == "summary"


async def test_ac03_full_true_gives_the_whole_answer_as_before(server):
    payload, _ = await _list(server, full=True)
    assert payload["result"] == stitch_answer()


def test_an_answer_that_is_not_a_project_list_is_left_alone():
    for answer in ({"text": "hola"}, {"content": [], "isError": False}, ["x"], None):
        assert summarize_project_list(answer) == answer
    assert summarize_project_list({"projects": [], "nextPageToken": "t"}) == {"projects": [], "nextPageToken": "t", "detail": "summary"}
