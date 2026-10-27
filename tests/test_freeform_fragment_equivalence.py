"""FreeForm fragments give the same answers and boards as the whole items.json (UC-11103, UC-11102).

Each tool of the hook's FRAGMENT_TOOLS table runs twice against the real server
tool: once with the whole board (what clients send today) and once with the
fragment the hook builds, merged back by the hook's own code (run with node).
The answer and the resulting board must be the same. The same board shape is
used to measure what a call sends (AC-01..03) and to check that a board sent in
parts never repeats an id (UC-11102).
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from server.backends.freeform_backend import FreeformBackend
from server.tools.board_operations import set_ac_internal, set_ac_metadata
from server.tools.epics import add_epic
from server.tools.milestone_management import set_uc_satellite
from server.tools.spec_driven import (
    complete_uc,
    get_ac_status,
    get_uc,
    get_us,
    import_spec,
    mark_ac,
    mark_ac_batch,
    move_uc,
    move_us,
    start_uc,
)
from server.tools.spec_mutations import add_ac, add_uc, delete_ac, update_ac, update_uc, update_us

ENGINE = Path(__file__).resolve().parents[1]
LIB = ENGINE / ".claude" / "hooks" / "lib" / "freeform-fragment.mjs"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="the hook runs on node")

TOOLS = {
    "add_uc": add_uc, "add_ac": add_ac, "update_ac": update_ac, "delete_ac": delete_ac,
    "set_ac_metadata": set_ac_metadata, "set_ac_internal": set_ac_internal, "get_ac_status": get_ac_status,
    "get_uc": get_uc, "start_uc": start_uc, "mark_ac": mark_ac, "mark_ac_batch": mark_ac_batch,
    "update_uc": update_uc, "set_uc_satellite": set_uc_satellite, "move_uc": move_uc, "complete_uc": complete_uc,
    "get_us": get_us, "move_us": move_us, "update_us": update_us, "import_spec": import_spec, "add_epic": add_epic,
}


class FakeCtx:
    """A content-only FreeForm session, as on the hosted MCP."""

    def __init__(self):
        self._s = {"spec_backend_config": {"backend_type": "freeform", "content_only": True}}

    async def get_state(self, key):
        return self._s.get(key)

    async def set_state(self, key, value):
        self._s[key] = value


def _text(label: str, size: int) -> str:
    base = f"{label}: el sistema registra cada paso, muestra el estado y deja la evidencia en el panel. "
    return (base * (size // len(base) + 1))[:size]


def build_board(stories: int = 6, ucs_per_story: int = 4, acs: int = 104, *, done_story: int | None = None) -> list[dict]:
    """A board shaped like Miguel's: 134 items and ~103 KB with the defaults."""

    async def _build() -> str:
        backend = FreeformBackend(items_content="[]")
        await backend.create_epic("ff", name="Cobros", objective="Cobrar sin fricción")
        ac_left = acs
        uc_total = stories * ucs_per_story
        uc_n = 0
        for s in range(1, stories + 1):
            us = await backend.create_item(
                "ff", name=f"US-{s:02d}: Historia {s}", description=_text(f"US-{s:02d}", 1000),
                state="user_stories", labels=["US"], meta={"us_id": f"US-{s:02d}", "tipo": "US", "epic_id": "EP-01"},
            )
            for _ in range(ucs_per_story):
                uc_n += 1
                state = "done" if done_story == s and uc_n % ucs_per_story != 0 else ("in_progress" if uc_n % 5 == 0 else "backlog")
                uc = await backend.create_item(
                    "ff", name=f"UC-{100 + uc_n}: Caso {uc_n}", description=_text(f"UC-{100 + uc_n}", 1400),
                    state=state, labels=["UC"], parent_id=us.id,
                    meta={"uc_id": f"UC-{100 + uc_n}", "us_id": f"US-{s:02d}", "tipo": "UC", "context": _text("ctx", 300)},
                )
                n = ac_left // (uc_total - uc_n + 1)
                ac_left -= n
                await backend.create_acceptance_criteria(
                    "ff", uc.id, [(f"AC-{i:02d}", _text(f"Criterio {i}", 120)) for i in range(1, n + 1)]
                )
        return backend.get_items_content()

    return json.loads(asyncio.run(_build()) if not _in_loop() else _sync(_build()))


def _in_loop() -> bool:
    try:
        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False


def _sync(coro):
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(1) as pool:
        return pool.submit(asyncio.run, coro).result()


def _node(op: str, payload: dict) -> Any:
    script = (
        "import { readFileSync } from 'node:fs';"
        f"import * as f from {json.dumps(LIB.as_uri())};"
        "const p = JSON.parse(readFileSync(0, 'utf-8'));"
        "let out;"
        "if (p.op === 'build') { const b = f.buildItemsContent(p); out = { itemsContent: b.itemsContent, sent: b.sent, whole: b.whole, reserves: b.reserves }; }"
        "else if (p.op === 'merge') out = f.mergeFragment(p.local, p.sent, p.returned);"
        "else if (p.op === 'tools') out = { content: [...f.CONTENT_TOOLS], fragment: Object.keys(f.FRAGMENT_TOOLS) };"
        "process.stdout.write(JSON.stringify(out));"
    )
    done = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        input=json.dumps({"op": op, **payload}), capture_output=True, text=True, timeout=60,
    )
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def build(tool: str, args: dict, items: list[dict], reserved: dict | None = None) -> dict:
    return _node("build", {"tool": tool, "args": args, "items": items, "raw": json.dumps(items), "reserved": reserved or {}})


def merge(local: list[dict], sent: list[dict], returned: list[dict]) -> list[dict]:
    return _node("merge", {"local": local, "sent": sent, "returned": returned})


async def call(tool: str, args: dict, items_content: str) -> dict:
    return await TOOLS[tool](board_id="ff", ctx=FakeCtx(), items_content=items_content, **args)


async def via_fragment(tool: str, args: dict, board: list[dict], reserved: dict | None = None) -> tuple[dict, list[dict], dict]:
    built = build(tool, args, board, reserved)
    result = await call(tool, args, built["itemsContent"])
    content = result.get("items_content")
    if content is None:
        return result, board, built
    back = json.loads(content)
    returned = back if isinstance(back, list) else back["items"]
    return result, merge(board, built["sent"], returned), built


_TS = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?")
_NEW = re.compile(r"\b(item|ac)-[0-9a-f]{8}\b")


def normalize(value: Any, known: set[str]) -> Any:
    if isinstance(value, dict):
        return {k: normalize(v, known) for k, v in value.items() if k not in ("items_content", "backend_item_url")}
    if isinstance(value, list):
        return [normalize(v, known) for v in value]
    if isinstance(value, str):
        value = _TS.sub("<ts>", value)
        return _NEW.sub(lambda m: m.group(0) if m.group(0) in known else "<new>", value)
    return value


def _ids(board: list[dict]) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in board:
        meta = item.get("meta") or {}
        for kind in ("us", "uc"):
            if f"{kind}_id" in meta and kind.upper() in item.get("labels", []):
                out[meta[f"{kind}_id"]] = item["id"]
    return out


def _first_ac(board: list[dict], uc_item: str) -> str:
    return next(i["meta"]["ac_id"] for i in board if i.get("parent_id") == uc_item and "AC" in i["labels"])


SCENARIOS = [
    ("add_uc", lambda b: {"us_id": "US-03", "name": "Cobro nuevo", "description": "d", "acceptance_criteria": ["El cobro queda registrado"]}),
    ("add_ac", lambda b: {"uc_id": "UC-110", "text": "El recibo aparece en el panel"}),
    ("update_ac", lambda b: {"uc_id": "UC-110", "ac_id": "AC-01", "text": "Texto nuevo del criterio"}),
    ("delete_ac", lambda b: {"uc_id": "UC-110", "ac_id": "AC-02", "reason": "duplicado"}),
    ("set_ac_metadata", lambda b: {"uc_id": "UC-110", "ac_id": "AC-01", "evidence_url": "https://x.test/e", "verdict": "PASS"}),
    ("set_ac_internal", lambda b: {"uc_id": "UC-110", "ac_id": "AC-01", "internal": True}),
    ("get_ac_status", lambda b: {"uc_id": "UC-110"}),
    ("get_uc", lambda b: {"uc_id": "UC-110"}),
    ("start_uc", lambda b: {"uc_id": "UC-110"}),
    ("mark_ac", lambda b: {"uc_id": "UC-110", "ac_id": "AC-01", "passed": True}),
    ("mark_ac_batch", lambda b: {"uc_id": "UC-110", "results": [{"ac_id": "AC-01", "passed": True}, {"ac_id": "AC-02", "passed": False}]}),
    ("update_uc", lambda b: {"uc_id": "UC-110", "hours": 6, "actor": "Developer"}),
    ("set_uc_satellite", lambda b: {"uc_id": "UC-110", "satellite": "engine"}),
    ("move_uc", lambda b: {"uc_id": "UC-110", "target": "review"}),
    ("move_uc", lambda b: {"uc_id": "UC-112", "target": "done"}),
    ("complete_uc", lambda b: {"uc_id": "UC-112"}),
    ("complete_uc", lambda b: {"uc_id": "UC-110"}),
    ("get_us", lambda b: {"us_id": "US-03"}),
    ("move_us", lambda b: {"us_id": "US-03", "target": "review"}),
    ("update_us", lambda b: {"us_id": "US-03", "hours": 20}),
    ("import_spec", lambda b: {"spec": {"user_stories": [
        {"us_id": "US-03", "name": "Historia 3 (revisada)", "use_cases": [
            {"uc_id": "UC-110", "name": "Caso 10", "acceptance_criteria": ["Uno", "Dos"]},
            {"uc_id": "UC-200", "name": "Caso nuevo", "acceptance_criteria": ["El caso nuevo registra su evidencia"]}]},
        {"us_id": "US-09", "name": "Historia nueva", "use_cases": [
            {"uc_id": "UC-201", "name": "Otro caso", "acceptance_criteria": ["Queda registrado"]}]}]}}),
    ("add_epic", lambda b: {"name": "Informes"}),
]


@pytest.mark.parametrize(("tool", "make_args"), SCENARIOS, ids=[f"{t}-{i}" for i, (t, _) in enumerate(SCENARIOS)])
async def test_a_fragment_gives_the_same_answer_and_board_as_the_whole_items_json(tool, make_args):
    # Story 3 has all its UCs done but its last one (UC-112): closing it closes the story.
    board = build_board(done_story=3)
    args = make_args(board)
    known = {i["id"] for i in board}

    whole_result = await call(tool, args, json.dumps(board))
    whole_board = json.loads(whole_result["items_content"]) if "items_content" in whole_result else board
    frag_result, frag_board, built = await via_fragment(tool, args, board)

    assert built["whole"] is False
    assert normalize(frag_result, known) == normalize(whole_result, known)
    assert normalize(frag_board, known) == normalize(whole_board, known)


# ── AC-01..03: what a call sends ───────────────────────────────────────

ADD_UC = {"us_id": "US-03", "name": "Cobrar con tarjeta", "description": "Cobro con tarjeta",
          "acceptance_criteria": ["El pago queda registrado", "El recibo aparece en el panel"]}


def _sent_bytes(tool: str, args: dict, board: list[dict]) -> int:
    built = build(tool, args, board)
    return len(json.dumps({**args, "items_content": built["itemsContent"]}, ensure_ascii=False).encode("utf-8"))


def test_the_test_board_is_shaped_like_the_reported_one():
    board = build_board()
    size = len(json.dumps(board, indent=2, ensure_ascii=False).encode("utf-8"))
    assert len(board) == 135  # 134 stories, UCs and criteria, plus the epic
    assert 90_000 < size < 125_000


def test_uc11103_ac01_creating_a_uc_sends_less_than_10_kb():
    board = build_board()
    whole = len(json.dumps({**ADD_UC, "items_content": json.dumps(board, indent=2)}).encode("utf-8"))
    sent = _sent_bytes("add_uc", ADD_UC, board)
    assert sent < 10_000, sent
    assert whole > 90_000  # what the model wrote before


@pytest.mark.parametrize("tool", ["get_uc", "start_uc"])
def test_uc11103_ac02_reading_or_starting_a_uc_sends_less_than_10_kb(tool):
    assert _sent_bytes(tool, {"uc_id": "UC-110"}, build_board()) < 10_000


def test_uc11103_ac03_creating_a_uc_costs_the_same_with_10_or_134_items():
    small = build_board(stories=3, ucs_per_story=1, acs=4)  # 3 US + 3 UC + 4 AC = 10
    assert len([i for i in small if "EP" not in i["labels"]]) == 10
    args = {**ADD_UC, "us_id": "US-03"}
    a, b = _sent_bytes("add_uc", args, small), _sent_bytes("add_uc", args, build_board())
    assert abs(a - b) / max(a, b) < 0.20, (a, b)


# ── UC-11102: a board sent in parts never repeats an id ────────────────


def _repeated(board: list[dict]) -> list[str]:
    seen: dict[str, int] = {}
    for item in board:
        meta = item.get("meta") or {}
        labels = item.get("labels", [])
        key = None
        if "US" in labels:
            key = meta.get("us_id")
        elif "UC" in labels:
            key = meta.get("uc_id")
        elif "EP" in labels:
            key = item["id"]
        elif "AC" in labels:
            key = f"{item.get('parent_id')}/{meta.get('ac_id')}"
        if key:
            seen[key] = seen.get(key, 0) + 1
    return [k for k, n in seen.items() if n > 1]


async def test_uc11102_ac01_the_id_add_uc_assigns_from_a_fragment_is_not_on_the_board():
    board = build_board()
    result, merged, built = await via_fragment("add_uc", ADD_UC, board)
    assert json.loads(built["itemsContent"])["max_ids"]["UC"] == 124
    assert result["uc_id"] == "UC-125"
    assert "UC-125" not in _ids(board) and _repeated(merged) == []


async def test_uc11102_ac02_134_items_in_two_lots_then_add_uc_and_add_ac_repeat_no_id():
    source = build_board()
    stories = []
    for us in (i for i in source if "US" in i["labels"]):
        ucs = [i for i in source if i.get("parent_id") == us["id"] and "UC" in i["labels"]]
        stories.append({
            "us_id": us["meta"]["us_id"], "name": us["name"].split(": ", 1)[1],
            "use_cases": [{
                "uc_id": uc["meta"]["uc_id"], "name": uc["name"].split(": ", 1)[1],
                "acceptance_criteria": [ac["name"].split("] ", 1)[1] for ac in source
                                        if ac.get("parent_id") == uc["id"] and "AC" in ac["labels"]],
            } for uc in ucs],
        })
    board: list[dict] = []
    for lot in (stories[:3], stories[3:]):
        _, board, built = await via_fragment("import_spec", {"spec": {"user_stories": lot}}, board)
        assert built["whole"] is False
    assert len(board) == 134 and _repeated(board) == []

    for n in range(3):
        _, board, _ = await via_fragment("add_uc", {**ADD_UC, "us_id": f"US-0{n + 1}"}, board)
    _, board, _ = await via_fragment("add_ac", {"uc_id": "UC-125", "text": "El recibo aparece"}, board)
    # Re-importing a lot that already exists updates it instead of duplicating it.
    _, board, _ = await via_fragment("import_spec", {"spec": {"user_stories": stories[:1]}}, board)

    assert _repeated(board) == []
    assert sorted(k for k in _ids(board) if k.startswith("UC-"))[-3:] == ["UC-125", "UC-126", "UC-127"]


async def test_uc11102_two_add_uc_in_flight_take_different_numbers():
    board = build_board()
    first = build("add_uc", ADD_UC, board)
    second = build("add_uc", {**ADD_UC, "us_id": "US-04"}, board, reserved={"UC": [first["reserves"]["UC"]]})
    a = await call("add_uc", ADD_UC, first["itemsContent"])
    b = await call("add_uc", {**ADD_UC, "us_id": "US-04"}, second["itemsContent"])
    assert (a["uc_id"], b["uc_id"]) == ("UC-125", "UC-126")
    merged = merge(board, first["sent"], json.loads(a["items_content"])["items"])
    merged = merge(merged, second["sent"], json.loads(b["items_content"])["items"])
    assert _repeated(merged) == [] and {"UC-125", "UC-126"} <= set(_ids(merged))


async def test_uc11102_ac03_a_628_board_opens_without_migration():
    # The shape the 6.28 server wrote: no fragment metadata anywhere in the file.
    board = build_board()
    assert all(set(i) <= {"id", "name", "description", "state", "parent_id", "labels", "priority", "meta",
                          "created_at", "updated_at", "external_source", "external_id"} for i in board)
    result, merged, built = await via_fragment("start_uc", {"uc_id": "UC-110"}, board)
    assert built["whole"] is False and result["status"] == "in_progress"
    assert next(i for i in merged if i["id"] == _ids(board)["UC-110"])["state"] == "in_progress"
    # Untouched items keep every byte, descriptions of context items included.
    untouched = [i for i in board if i["id"] not in {_ids(board)["UC-110"], _ids(board)["US-03"]}]
    assert all(i in merged for i in untouched)


# ── The hook knows the same tools as the server ────────────────────────


def test_the_hook_lists_exactly_the_tools_that_take_the_board():
    from server.server import mcp

    async def _content_tools() -> set[str]:
        tools = await mcp.list_tools()
        return {t.name for t in tools if "items_content" in (t.parameters or {}).get("properties", {})}

    server_side = asyncio.run(_content_tools()) if not _in_loop() else _sync(_content_tools())
    hook = _node("tools", {})
    assert set(hook["content"]) == server_side
    assert set(hook["fragment"]) <= server_side
