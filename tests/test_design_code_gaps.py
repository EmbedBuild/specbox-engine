"""US-49 · UC-4902 — the design gate blocks what leaves the system.

AC-01: the visual gap report finds, in the code, colours written directly,
fonts outside the system, weights above 600 and gradients, with their location.
AC-02: in autopilot, an implementation with design gaps is blocked before it
goes to review, and the block says what was found and what to do.
AC-03: a clean implementation gets the gate green — 0 findings, no warnings.

The scanner exists twice (Python for the report, JS for the hook); both must
return exactly the expected findings of code_gap_cases.json.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from fastmcp import FastMCP

from server.design_system import SYSTEM_TOKENS_CANDIDATE_PATHS, parse_system_tokens
from server.design_system.code_gaps import DesignSystemRules, is_ui_source, scan_file

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "design_system"
TOKENS_FILE = FIXTURES / "tinta.design-system.tokens.json"
CASES = json.loads((FIXTURES / "code_gap_cases.json").read_text(encoding="utf-8"))["cases"]
HOOK = ROOT / ".claude" / "hooks" / "design-system-gate.mjs"
LIB = ROOT / ".claude" / "hooks" / "lib" / "design-gaps.mjs"
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")

GAPPY = (
    "export const Promo = () => (\n"
    '  <div className="bg-gradient-to-r font-bold" style={{ color: \'#FF0000\', fontFamily: \'Poppins\' }}>\n'
    "    oferta\n"
    "  </div>\n"
    ");\n"
)
CLEAN = 'export const Promo = () => <div className="bg-paper-100 text-ink-900 font-semibold">oferta</div>;\n'


@pytest.fixture(scope="module")
def rules() -> DesignSystemRules:
    return DesignSystemRules.from_tokens(parse_system_tokens(TOKENS_FILE.read_text(encoding="utf-8")))


def _key(items) -> list[tuple[str, int, str]]:
    return sorted((i["kind"], i["line"], i["value"]) for i in items)


# ── AC-01: the scanner ──────────────────────────────────────────────────


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_python_scanner_meets_the_shared_cases(case, rules):
    got = scan_file(case["file"], case["content"], rules) if is_ui_source(case["file"]) else []
    assert _key(g.to_dict() for g in got) == _key(case["expected"])


@needs_node
def test_js_scanner_meets_the_same_cases():
    script = f"""
import {{ readFileSync }} from 'fs';
import {{ scanFiles, rulesFromTokens, SYSTEM_TOKENS_CANDIDATE_PATHS }} from '{LIB.as_posix()}';
const rules = rulesFromTokens(JSON.parse(readFileSync('{TOKENS_FILE.as_posix()}', 'utf-8')));
const cases = JSON.parse(readFileSync('{(FIXTURES / "code_gap_cases.json").as_posix()}', 'utf-8')).cases;
const out = {{}};
for (const c of cases) out[c.name] = scanFiles({{ [c.file]: c.content }}, rules);
console.log(JSON.stringify({{ out, rules: {{ families: [...rules.families].sort(), maxWeight: rules.maxWeight }},
  paths: SYSTEM_TOKENS_CANDIDATE_PATHS }}));
"""
    res = subprocess.run([NODE, "--input-type=module", "-e", script], capture_output=True, text=True, check=True)
    data = json.loads(res.stdout)
    for case in CASES:
        assert _key(data["out"][case["name"]]) == _key(case["expected"]), case["name"]
    py_rules = DesignSystemRules.from_tokens(parse_system_tokens(TOKENS_FILE.read_text(encoding="utf-8")))
    assert data["rules"] == {"families": sorted(py_rules.families), "maxWeight": py_rules.max_weight}
    assert data["paths"] == list(SYSTEM_TOKENS_CANDIDATE_PATHS)


def test_each_finding_says_where(rules):
    gaps = scan_file("src/Promo.tsx", GAPPY, rules)
    assert {(g.kind, g.value) for g in gaps} == {
        ("gradient", "bg-gradient-to-r"),
        ("weight_above", "font-bold"),
        ("direct_color", "#FF0000"),
        ("font_outside", "poppins"),
    }
    assert all(g.to_dict()["location"] == "src/Promo.tsx:2" for g in gaps)


# ── AC-01 + AC-03: the visual gap report ────────────────────────────────


@pytest.fixture
def report(tmp_path):
    from server.tools.onboarding import register_onboarding_tools

    mcp = FastMCP(name="test-uc4902")
    register_onboarding_tools(mcp, engine_path=ROOT, state_path=tmp_path)
    tool = asyncio.run(mcp.get_tool("get_visual_gap_report"))
    tokens = TOKENS_FILE.read_text(encoding="utf-8")

    def call(**kwargs: Any) -> dict:
        kwargs.setdefault("system_tokens_content", tokens)
        kwargs.setdefault("system_tokens_path", "src/styles/tokens/design-system.tokens.json")
        return tool.fn(**kwargs)

    return call


class TestReport:
    def test_lists_every_gap_with_location_and_fix(self, report):
        res = report(code_files={"src/Promo.tsx": GAPPY, "src/styles/tokens/theme.css": "a{color:#000}"})
        design = res["design_gaps"]
        assert res["design_gate"] == "block"
        assert design["status"] == "gaps"
        assert design["by_kind"] == {"direct_color": 1, "font_outside": 1, "weight_above": 1, "gradient": 1}
        for finding in design["findings"]:
            assert finding["location"] == "src/Promo.tsx:2"
            assert finding["fix"]
        assert "600" in design["how_to_fix"]["weight_above"]
        assert design["checked_files"] == ["src/Promo.tsx"]
        assert design["skipped_files"] == ["src/styles/tokens/theme.css"]
        assert "Design gate: BLOCK" in res["summary"]

    def test_a_clean_implementation_gets_the_gate_green(self, report):
        res = report(code_files={"src/Promo.tsx": CLEAN})
        design = res["design_gaps"]
        assert res["design_gate"] == "pass"
        assert design["total"] == 0
        assert design["findings"] == []
        assert design["warnings"] == []

    def test_with_system_tokens_the_brand_kit_is_not_a_gap(self, report):
        res = report(code_files={"src/Promo.tsx": CLEAN})
        brand_kit = {k: v for k, v in res["artifacts"].items() if k.startswith("brand_kit")}
        assert brand_kit and all(v["exists"] for v in brand_kit.values())
        assert res["system_tokens"]["found"] is True

    def test_without_tokens_the_gate_is_not_applicable_and_says_why(self, report):
        res = report(code_files={"src/Promo.tsx": GAPPY}, system_tokens_content=None)
        design = res["design_gaps"]
        assert design["status"] == "not_applicable"
        assert "design-system.tokens.json" in design["warnings"][0]

    def test_without_code_files_the_report_is_unchanged(self, report):
        res = report(system_tokens_content=None)
        assert "design_gaps" not in res and "design_gate" not in res


# ── AC-02 + AC-03: the hook that blocks before review ───────────────────


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path) -> Path:
    root = tmp_path / "app"
    (root / "src" / "styles" / "tokens").mkdir(parents=True)
    (root / "src" / "styles" / "tokens" / "design-system.tokens.json").write_text(
        TOKENS_FILE.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (root / ".claude").mkdir()
    (root / "src" / "Base.tsx").write_text(CLEAN, encoding="utf-8")
    _git(root, "init", "-q", "-b", "main")
    _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "add", ".")
    _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base")
    _git(root, "checkout", "-q", "-b", "feature/UC-1")
    return root


def _settings(root: Path, **specbox: Any) -> None:
    (root / ".claude" / "settings.local.json").write_text(json.dumps({"specbox": specbox}), encoding="utf-8")


def _run_hook(root: Path, tool_name: str, tool_input: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [NODE, str(HOOK)],
        input=json.dumps({"tool_name": tool_name, "tool_input": tool_input}),
        cwd=root,
        capture_output=True,
        text=True,
        timeout=30,
    )


MOVE_TO_REVIEW = ("mcp__SpecBox-MCP__move_uc", {"board_id": "b", "uc_id": "UC-1", "target": "review"})


@needs_node
class TestHook:
    def test_blocks_an_implementation_with_gaps_in_autopilot(self, repo):
        _settings(repo, autopilot={"level": "agresivo"})
        (repo / "src" / "Promo.tsx").write_text(GAPPY, encoding="utf-8")
        res = _run_hook(repo, *MOVE_TO_REVIEW)
        assert res.returncode == 2
        # What was found, with location…
        assert "src/Promo.tsx:2  color escrito: #FF0000" in res.stderr
        assert "fuente fuera del sistema: poppins" in res.stderr
        assert "peso por encima del máximo: font-bold" in res.stderr
        assert "gradiente: bg-gradient-to-r" in res.stderr
        # …and what to do.
        assert "Qué hacer:" in res.stderr
        assert "El peso máximo del sistema es 600" in res.stderr
        assert "design-gate:ignore" in res.stderr

    def test_committed_changes_on_the_branch_count_too(self, repo):
        _settings(repo, autopilot={"level": "equilibrado"})
        (repo / "src" / "Promo.tsx").write_text(GAPPY, encoding="utf-8")
        _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "add", ".")
        _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "promo")
        assert _run_hook(repo, *MOVE_TO_REVIEW).returncode == 2

    @pytest.mark.parametrize(
        ("tool_name", "tool_input"),
        [
            ("mcp__SpecBox-MCP__complete_uc", {"board_id": "b", "uc_id": "UC-1"}),
            ("mcp__SpecBox-MCP__move_uc", {"board_id": "b", "uc_id": "UC-1", "target": "done"}),
            ("Bash", {"command": "gh pr create --base main --title x --body y"}),
        ],
    )
    def test_every_way_to_review_is_gated(self, repo, tool_name, tool_input):
        _settings(repo, autopilot={"level": "agresivo"})
        (repo / "src" / "Promo.tsx").write_text(GAPPY, encoding="utf-8")
        assert _run_hook(repo, tool_name, tool_input).returncode == 2

    def test_a_clean_implementation_passes_silently(self, repo):
        _settings(repo, autopilot={"level": "agresivo"})
        (repo / "src" / "Promo.tsx").write_text(CLEAN, encoding="utf-8")
        res = _run_hook(repo, *MOVE_TO_REVIEW)
        assert res.returncode == 0
        assert res.stdout.strip() == "" and res.stderr.strip() == ""

    def test_outside_autopilot_it_warns_without_blocking(self, repo):
        (repo / "src" / "Promo.tsx").write_text(GAPPY, encoding="utf-8")
        res = _run_hook(repo, *MOVE_TO_REVIEW)
        assert res.returncode == 0
        assert "DESIGN GATE (aviso)" in res.stdout

    def test_the_mode_can_be_set_explicitly(self, repo):
        (repo / "src" / "Promo.tsx").write_text(GAPPY, encoding="utf-8")
        _settings(repo, autopilot={"level": "agresivo"}, design_gate={"mode": "off"})
        assert _run_hook(repo, *MOVE_TO_REVIEW).returncode == 0
        _settings(repo, design_gate={"mode": "block"})
        assert _run_hook(repo, *MOVE_TO_REVIEW).returncode == 2

    def test_other_transitions_are_not_gated(self, repo):
        _settings(repo, autopilot={"level": "agresivo"})
        (repo / "src" / "Promo.tsx").write_text(GAPPY, encoding="utf-8")
        assert _run_hook(repo, "mcp__SpecBox-MCP__move_uc", {"uc_id": "UC-1", "target": "in_progress"}).returncode == 0
        assert _run_hook(repo, "Bash", {"command": "git push"}).returncode == 0

    def test_without_system_tokens_there_is_nothing_to_compare(self, repo):
        _settings(repo, autopilot={"level": "agresivo"})
        (repo / "src" / "styles" / "tokens" / "design-system.tokens.json").unlink()
        (repo / "src" / "Promo.tsx").write_text(GAPPY, encoding="utf-8")
        assert _run_hook(repo, *MOVE_TO_REVIEW).returncode == 0

    def test_hook_is_registered_before_review(self):
        for path in (ROOT / ".claude" / "settings.json", ROOT / "templates" / "settings.json.template"):
            pre = json.loads(path.read_text(encoding="utf-8"))["hooks"]["PreToolUse"]
            mcp = [e for e in pre if e.get("matcher") == "mcp__SpecBox-MCP__(move_uc|complete_uc)"]
            assert mcp and "design-system-gate.mjs" in mcp[0]["hooks"][0]["command"], path
            bash = next(e for e in pre if e.get("matcher") == "Bash")
            assert any(
                h.get("if") == "Bash(*gh pr create*)" and "design-system-gate.mjs" in h["command"]
                for h in bash["hooks"]
            ), path
