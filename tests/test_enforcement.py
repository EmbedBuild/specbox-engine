"""US-122 / UC-12212 — cada medida de EP-20 tiene un modo por proyecto.

- **AC-01**: el tablero guarda el modo (off/warn/block) de cada medida; una tool lo muestra y lo cambia.
- **AC-02**: un tablero nuevo toma el modo de proyecto nuevo; uno que ya existía queda en «warn».
- **AC-03**: en «warn» hay aviso y la operación sigue; en «off» la respuesta queda igual.
- **AC-04**: hooks y servidor leen el mismo modo, también en FreeForm; Trello y Plane, «warn» como máximo.
- **AC-05**: saltar un bloqueo exige motivo; queda quién, cuándo y por qué; la tool pide confirmación.
- **AC-06**: los errores nuevos llevan en su texto la medida, el motivo y cómo seguir.
- **AC-07**: el changelog de una versión que activa una medida cuenta qué cambia para los existentes.

Las de Postgres están en ``tests/test_enforcement_native.py``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from server.coordination import enforcement as pol
from server.tools.enforcement import get_enforcement_policy, set_enforcement_mode, skip_enforcement

ENGINE = Path(__file__).resolve().parent.parent
AT = "2026-11-18T10:00:00+00:00"


class _Ctx:
    """Contexto de FastMCP con la configuración de backend de la sesión."""

    def __init__(self, config: dict | None) -> None:
        self._config = config

    async def get_state(self, key: str):
        return self._config


# ── Lo puro ─────────────────────────────────────────────────────────


def test_a_board_without_policy_is_an_existing_one_with_everything_in_warn():
    """AC-02: un tablero que ya existía no amanece bloqueado."""
    policy = pol.effective_policy(None, backend_type="native")
    assert policy["origin"] == "existing"
    assert set(policy["measures"]) == set(pol.MEASURES)
    assert {m["mode"] for m in policy["measures"].values()} == {"warn"}
    assert all(m["source"] == "default" for m in policy["measures"].values())
    assert "ninguna pasa a «block» sin que una persona lo cambie" in policy["notice"]


def test_a_new_board_takes_the_new_project_mode_of_each_measure(monkeypatch):
    """AC-02: «block» solo si la medida superó la prueba (su new_default); hoy todas en «warn»."""
    assert {m.new_default for m in pol.MEASURES.values()} == {"warn"}
    policy = pol.effective_policy(pol.new_policy(), backend_type="native")
    assert policy["origin"] == "new" and {m["mode"] for m in policy["measures"].values()} == {"warn"}

    hardened = dict(pol.MEASURES)
    hardened["spec_quality"] = pol.Measure("spec_quality", "calidad", "US-123", new_default="block")
    monkeypatch.setattr(pol, "MEASURES", hardened)
    nuevo = pol.effective_policy(pol.new_policy(), backend_type="native")
    existente = pol.effective_policy(None, backend_type="native")
    assert nuevo["measures"]["spec_quality"]["mode"] == "block"
    assert existente["measures"]["spec_quality"]["mode"] == "warn"


def test_a_person_changes_a_mode_and_it_is_recorded():
    """AC-01: queda el modo, quién, cuándo y desde cuándo bloquea."""
    stored, previous = pol.with_mode(None, "spec_quality", "block", by="ana", at=AT, backend_type="native")
    assert previous == "warn"
    entry = stored["measures"]["spec_quality"]
    assert entry == {"mode": "block", "set_by": "ana", "set_at": AT, "block_since": AT}
    later, _ = pol.with_mode(stored, "spec_quality", "block", by="luis", at="2026-11-19T00:00:00+00:00",
                             backend_type="native")
    assert later["measures"]["spec_quality"]["block_since"] == AT  # sigue bloqueando desde entonces
    policy = pol.effective_policy(later, backend_type="native")
    assert policy["measures"]["spec_quality"]["source"] == "set"
    assert policy["origin"] == "existing"  # cambiar un modo no convierte el tablero en nuevo


@pytest.mark.parametrize("measure,mode,code", [
    ("no_existe", "warn", "UNKNOWN_MEASURE"),
    ("spec_quality", "estricto", "INVALID_MODE"),
])
def test_what_cannot_be_set(measure, mode, code):
    with pytest.raises(pol.PolicyError) as e:
        pol.with_mode(None, measure, mode, by="ana", at=AT, backend_type="native")
    assert e.value.code == code


@pytest.mark.parametrize("backend", ["trello", "plane"])
def test_trello_and_plane_stay_in_warn_at_most_and_say_so(backend):
    """AC-04 (D20)."""
    stored = {"origin": "new", "measures": {"spec_quality": {"mode": "block"}}}
    policy = pol.effective_policy(stored, backend_type=backend)
    assert policy["max_mode"] == "warn"
    assert policy["measures"]["spec_quality"] == {**policy["measures"]["spec_quality"], "mode": "warn", "capped": True}
    assert "avisa pero no detiene" in policy["notice"]
    with pytest.raises(pol.PolicyError) as e:
        pol.with_mode(None, "spec_quality", "block", by="ana", at=AT, backend_type=backend)
    assert e.value.code == "NOT_SUPPORTED"


def test_warn_tells_and_goes_on_off_leaves_the_answer_as_before():
    """AC-03."""
    answer = {"uc_id": "UC-1", "status": "in_progress"}
    for mode, outcome in (("off", "off"), ("warn", "warned"), ("block", "blocked")):
        stored, _ = pol.with_mode(None, "spec_quality", mode, by="ana", at=AT, backend_type="native")
        policy = pol.effective_policy(stored, backend_type="native")
        verdict = pol.check(policy, "spec_quality", failed=True, reason="Hay 2 criterios vagos.",
                            how_to_continue="Reescríbelos con validate_ac_quality.")
        assert verdict["outcome"] == outcome
        warnings = [verdict["warning"]] if "warning" in verdict else []
        out = pol.attach_warnings(answer, warnings)
        if mode == "off":
            assert out == answer and out is answer
        if mode == "warn":
            assert out == {**answer, "enforcement_warnings": [verdict["warning"]]}
            assert "Hay 2 criterios vagos." in verdict["warning"]["message"]
    passed = pol.check(pol.effective_policy(None, backend_type="native"), "spec_quality", failed=False)
    assert passed == {"outcome": "pass"}


def test_a_blocking_error_explains_itself_to_an_old_client():
    """AC-06: medida, motivo y cómo seguir están en el texto, no solo en campos nuevos."""
    stored, _ = pol.with_mode(None, "closing_evidence", "block", by="ana", at=AT, backend_type="native")
    verdict = pol.check(
        pol.effective_policy(stored, backend_type="native"), "closing_evidence", failed=True,
        reason="AC-02 no tiene evidencia que pase.", how_to_continue="Adjunta la prueba con mark_ac.",
    )
    error = verdict["error"]
    assert error["success"] is False and error["code"] == "ENFORCEMENT_BLOCKED"
    for part in ("closing_evidence", "AC-02 no tiene evidencia que pase.", "Adjunta la prueba con mark_ac."):
        assert part in error["error"]
    assert (error["measure"], error["reason"], error["how_to_continue"]) == (
        "closing_evidence", "AC-02 no tiene evidencia que pase.", "Adjunta la prueba con mark_ac."
    )


def test_a_skip_needs_a_reason_and_passes_once():
    """AC-05."""
    stored, _ = pol.with_mode(None, "spec_quality", "block", by="ana", at=AT, backend_type="native")
    for reason, code in (("", "REASON_REQUIRED"), ("porque sí", "REASON_REQUIRED"),
                         ("x" * 501, "REASON_TOO_LONG"),
                         ("La contraseña de la cuenta de revisión es hunter2", "SENSITIVE_DATA")):
        with pytest.raises(pol.PolicyError) as e:
            pol.with_skip(stored, "spec_quality", "UC-12212", reason, by="luis", at=AT, backend_type="native")
        assert e.value.code == code
    with pytest.raises(pol.PolicyError) as e:
        pol.with_skip(stored, "spec_quality", "12212", "Motivo con detalle suficiente", by="luis", at=AT,
                      backend_type="native")
    assert e.value.code == "INVALID_UC_ID"

    motivo = "El cliente aprobó estos criterios en la reunión del martes."
    stored, skip = pol.with_skip(stored, "spec_quality", "UC-12212", motivo, by="luis", at=AT, backend_type="native")
    assert skip == {"measure": "spec_quality", "uc_id": "UC-12212", "reason": motivo, "by": "luis", "at": AT}
    assert pol.effective_policy(stored, backend_type="native")["pending_skips"] == 1

    policy = pol.effective_policy(stored, backend_type="native")
    stored, used = pol.take_skip(stored, "spec_quality", "UC-12212")
    verdict = pol.check(policy, "spec_quality", failed=True, reason="Criterios vagos.", how_to_continue="x", skip=used)
    assert verdict["outcome"] == "skipped" and motivo in verdict["warning"]["message"]
    _, again = pol.take_skip(stored, "spec_quality", "UC-12212")
    assert again is None  # una sola vez


def test_nothing_to_skip_when_the_measure_does_not_block():
    with pytest.raises(pol.PolicyError) as e:
        pol.with_skip(None, "spec_quality", "UC-1", "Un motivo suficientemente largo", by="a", at=AT,
                      backend_type="native")
    assert e.value.code == "NOTHING_TO_SKIP" and "«warn»" in str(e.value)


def test_a_damaged_policy_reads_as_an_existing_board():
    raw = {"origin": "nuevo", "measures": {"spec_quality": {"mode": "estricto"}, "otra": {"mode": "block"}},
           "skips": "x"}
    policy = pol.effective_policy(raw, backend_type="native")
    assert policy["origin"] == "existing" and policy["measures"]["spec_quality"]["mode"] == "warn"
    assert "otra" not in policy["measures"] and policy["pending_skips"] == 0


# ── Hooks y servidor, el mismo catálogo ─────────────────────────────


def test_the_hooks_know_the_same_measures_with_the_same_new_project_mode():
    """AC-04: el catálogo de los hooks es el del servidor."""
    source = (ENGINE / ".claude" / "hooks" / "lib" / "enforcement-policy.mjs").read_text(encoding="utf-8")
    block = re.search(r"export const MEASURES = \{(.*?)\};", source, re.S).group(1)
    js = dict(re.findall(r"(\w+): '(\w+)'", block))
    assert list(js) == list(pol.MEASURES)
    assert js == {k: m.new_default for k, m in pol.MEASURES.items()}


# ── FreeForm ────────────────────────────────────────────────────────


async def test_freeform_content_round_trip_shows_and_changes_the_mode():
    """AC-01 y AC-04: el fichero que leen los hooks es el que recibe y devuelve el servidor."""
    out = await get_enforcement_policy(None, policy_content="")
    assert out["success"] and out["policy"]["origin"] == "existing"

    content = json.dumps(pol.new_policy())
    changed = await set_enforcement_mode(None, "spec_quality", "block", policy_content=content, actor="Ana")
    assert changed["success"] and changed["previous"] == "warn" and changed["mode"] == "block"
    saved = json.loads(changed["policy_content"])
    assert saved["origin"] == "new"
    assert saved["measures"]["spec_quality"]["mode"] == "block"
    assert saved["measures"]["spec_quality"]["set_by"] == "Ana"

    shown = await get_enforcement_policy(None, policy_content=changed["policy_content"])
    assert shown["policy"]["measures"]["spec_quality"]["mode"] == "block"

    skipped = await skip_enforcement(
        None, "spec_quality", "UC-7", "Criterios revisados con el cliente ayer.",
        policy_content=changed["policy_content"], actor="Luis",
    )
    assert skipped["success"] and skipped["skip"]["by"] == "Luis"
    assert json.loads(skipped["policy_content"])["skips"][0]["reason"] == "Criterios revisados con el cliente ayer."


async def test_freeform_errors_carry_the_measure():
    out = await set_enforcement_mode(None, "spec_quality", "duro", policy_content="")
    assert out == {"success": False, "code": "INVALID_MODE", "measure": "spec_quality",
                   "error": out["error"]} and "off, warn, block" in out["error"]
    bad = await get_enforcement_policy(None, policy_content="[1, 2]")
    assert bad["code"] == "INVALID_POLICY_CONTENT"


async def test_freeform_disk_mode_reads_and_writes_policy_json(tmp_path):
    ctx = _Ctx({"backend_type": "freeform", "root_path": str(tmp_path)})
    out = await get_enforcement_policy(ctx)
    assert out["policy"]["origin"] == "existing"
    changed = await set_enforcement_mode(ctx, "drift_gate", "off", actor="Ana")
    assert changed["success"] and "policy_content" not in changed
    saved = json.loads((tmp_path / "policy.json").read_text())
    assert saved["measures"]["drift_gate"]["mode"] == "off"


async def test_freeform_remote_without_content_asks_for_it(monkeypatch):
    monkeypatch.setenv("SPECBOX_TRANSPORT", "http")
    ctx = _Ctx({"backend_type": "freeform", "content_only": True})
    out = await get_enforcement_policy(ctx)
    assert out["code"] == "POLICY_CONTENT_REQUIRED" and "policy_content" in out["error"]


async def test_a_new_freeform_board_is_born_with_its_policy(tmp_path):
    """AC-02 en FreeForm: setup_board en disco escribe policy.json con origin «new», sin pisar uno previo."""
    from server.backends.freeform_backend import FreeformBackend

    backend = FreeformBackend(str(tmp_path / "tracking"))
    await backend.setup_board("Nuevo")
    saved = json.loads((tmp_path / "tracking" / "policy.json").read_text())
    assert saved["origin"] == "new"

    (tmp_path / "tracking" / "policy.json").write_text(json.dumps({"origin": "existing", "measures": {}}))
    await backend.setup_board("Otra vez")
    assert json.loads((tmp_path / "tracking" / "policy.json").read_text())["origin"] == "existing"


async def test_setup_board_in_content_mode_returns_the_new_policy(monkeypatch):
    """AC-02 con el MCP remoto: un tablero vacío vuelve con su política; uno con trabajo, sin ella."""
    from server.tools.spec_driven import setup_board

    ctx = _Ctx({"backend_type": "freeform", "content_only": True})
    nuevo = await setup_board("Nuevo", ctx, items_content="[]")
    assert json.loads(nuevo["policy_content"])["origin"] == "new"
    item = {"id": "ff-1", "name": "US-01: Algo", "labels": ["US"], "status": "backlog", "meta": {"us_id": "US-01"}}
    con_trabajo = await setup_board("Viejo", ctx, items_content=json.dumps([item]))
    assert "policy_content" not in con_trabajo


def test_onboarding_a_freeform_project_hands_its_policy(tmp_path):
    from server.tools.onboarding import _generate_onboarding_files  # noqa: F401 — firma estable

    source = (ENGINE / "server" / "tools" / "onboarding.py").read_text(encoding="utf-8")
    assert 'files[f"doc/tracking/{POLICY_FILE}"]' in source


@pytest.mark.parametrize("backend", ["trello", "plane"])
async def test_trello_and_plane_tools_say_warn_at_most(backend):
    ctx = _Ctx({"backend_type": backend})
    out = await get_enforcement_policy(ctx)
    assert out["success"] and out["policy"]["max_mode"] == "warn"
    changed = await set_enforcement_mode(ctx, "spec_quality", "block")
    assert changed["code"] == "NOT_SUPPORTED" and "native o en FreeForm" in changed["error"]
    skipped = await skip_enforcement(ctx, "spec_quality", "UC-1", "Un motivo suficientemente largo")
    assert skipped["code"] == "NOTHING_TO_SKIP"


# ── Confirmación de una persona (AC-05) ─────────────────────────────


def test_changing_a_mode_and_skipping_ask_a_person_in_claude_code():
    template = json.loads((ENGINE / "templates" / "settings.json.template").read_text(encoding="utf-8"))
    perms = template["permissions"]
    assert {"mcp__SpecBox-MCP__set_enforcement_mode", "mcp__SpecBox-MCP__skip_enforcement"} <= set(perms["ask"])
    assert "mcp__SpecBox-MCP__get_enforcement_policy" in perms["allow"]
    for name in ("set_enforcement_mode", "skip_enforcement"):
        assert f"mcp__SpecBox-MCP__{name}" not in perms["allow"]


# ── El changelog de cada medida (AC-07) ─────────────────────────────


def _changelog_entry(version: str) -> str:
    text = (ENGINE / "CHANGELOG.md").read_text(encoding="utf-8")
    m = re.search(rf"^## \[{re.escape(version)}\].*?(?=^## \[)", text, re.S | re.M)
    return m.group(0) if m else ""


def measures_missing_from_changelog(measures=None, entry=_changelog_entry) -> list[str]:
    """Las medidas activas cuya versión no cuenta qué cambia para los proyectos que ya existían."""
    missing = []
    for key, measure in (measures or pol.MEASURES).items():
        if not measure.since:
            continue
        body = entry(measure.since)
        section = re.search(r"^### Para los proyectos que ya existían\n(.*?)(?=^### |\Z)", body, re.S | re.M)
        if not section or key not in section.group(1) or "block" not in section.group(1):
            missing.append(key)
    return missing


def test_every_active_measure_has_its_note_for_existing_projects():
    """AC-07: la versión que activa una medida dice qué cambia para los existentes y cómo pasarla a «block»."""
    assert measures_missing_from_changelog() == []


def test_the_changelog_check_catches_a_missing_note():
    fake = {"spec_quality": pol.Measure("spec_quality", "calidad", "US-123", since="9.9.0")}
    sin_nota = lambda v: "## [9.9.0]\n\n### Added\n\n- spec_quality\n"  # noqa: E731
    con_nota = lambda v: (  # noqa: E731
        "## [9.9.0]\n\n### Para los proyectos que ya existían\n\n- `spec_quality` queda en «warn»; "
        "para que bloquee: set_enforcement_mode(measure=\"spec_quality\", mode=\"block\").\n"
    )
    assert measures_missing_from_changelog(fake, sin_nota) == ["spec_quality"]
    assert measures_missing_from_changelog(fake, con_nota) == []
