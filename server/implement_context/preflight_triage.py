"""Pre-flight autonomy triage for ``/implement`` (US-06).

The autopilot rarely fails at *executing*; it fails when it **guesses a
decision that was the user's** (an API contract, a naming choice, an
architectural trade-off, a library) and drags that wrong guess through the
whole branch→phases→QA→PR chain, where fixing it costs a full PR instead of
~50 tokens up front.

The policy engine in :mod:`server.app_docs.autopilot` already answers, for a
*known* ``decision_key``, whether the current autopilot level says ``auto`` /
``ask`` / ``block``. What it does **not** do is look at *this particular task*
and discover which decisions it actually contains — the 19 ``DECISION_KEYS``
are a generic catalogue, the same for every feature.

This module adds the missing **dynamic** step that precedes the static lookup:
given a plan, build an *inventory* of the decisions the task really contains
(UC-601, this file), classify each one ``autonomous`` vs. ``user_dependent``
(UC-602), and let ``/implement``'s pre-flight gate (UC-603) resolve the
``user_dependent`` ones with the user **before** the branch is created.

UC-601 scope (this file): the **inventory**. Detection is deliberately
conservative and explainable — every entry carries the ``source`` snippet of
the plan that triggered it, and every entry is tagged with the catalogued
``decision_key`` when it maps to one, or ``ad_hoc`` when it does not. The
classification itself lives in UC-602 (same module, separate function) so the
inventory is testable in isolation.

This module reuses :data:`server.app_docs.autopilot.DECISION_KEYS` as the
single source of truth for the catalogue — it never re-declares the keys.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..app_docs.autopilot import DECISION_KEYS, evaluate_decision

#: Classification outcomes (UC-602).
AUTONOMOUS: str = "autonomous"
USER_DEPENDENT: str = "user_dependent"

#: Sentinel for a decision the task contains that does NOT map to one of the
#: catalogued ``DECISION_KEYS``. Task-specific decisions (an undocumented API
#: contract, a naming choice) are the whole reason the static catalogue is not
#: enough — they get this marker and a conservative default in UC-602.
AD_HOC: str = "ad_hoc"


@dataclass
class DecisionEntry:
    """One decision the task contains.

    ``decision_key`` is either a key of
    :data:`server.app_docs.autopilot.DECISION_KEYS` (catalogued) or
    :data:`AD_HOC` (task-specific). ``family`` mirrors the catalogue family
    for catalogued keys and is ``"ad_hoc"`` otherwise, so a consumer can group
    without re-reading the catalogue. ``source`` is the verbatim plan snippet
    that triggered the entry — the inventory must always be explainable.
    """

    id: str
    description: str
    source: str
    decision_key: str = AD_HOC
    family: str = "ad_hoc"
    # Free-form bag the classifier (UC-602) fills in later; kept here so the
    # entry is a single carrier through the pipeline.
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable view (AC-01: the inventory is verifiable)."""
        out: dict[str, Any] = {
            "id": self.id,
            "description": self.description,
            "source": self.source,
            "decision_key": self.decision_key,
            "family": self.family,
        }
        # Surface classification fields at the top level when present (UC-602),
        # so the gate (UC-603) and the audit log (UC-604) read them directly.
        for k in ("classification", "action", "reason"):
            if k in self.meta:
                out[k] = self.meta[k]
        return out


# ── Catalogue cue mapping ──────────────────────────────────────────────────
#
# Phrases that, when present in a plan line, signal a decision that maps to a
# catalogued ``decision_key``. Kept intentionally small and high-precision:
# the cost of a false *catalogued* match is a wrong policy lookup, whereas an
# unmatched real decision still falls through to ``ad_hoc`` (conservative).
# Order matters — first match wins, so list the more specific cues first.

_CATALOGUE_CUES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("backend_selection", ("tracking backend", "freeform", "trello", "plane", "backend type")),
    ("veg_mode_selection", ("veg mode", "modo veg", "visual experience")),
    ("feature_aesthetic_direction", ("aesthetic", "brand direction", "design system")),
    ("definition_quality_gate", ("acceptance criteria quality", "ac quality", "definition gate")),
    ("destructive_action", ("delete ", "drop table", "rm -rf", "destructive", "overwrite")),
    ("branch_to_main_push", ("push to main", "push a main", "merge to main")),
    ("image_cost_over_budget", ("image budget", "over budget", "image cost")),
    ("stitch_config_decision", ("stitch project", "stitch config", "stitch api key")),
)

#: Phrases that signal a decision *exists* even when it does not map to the
#: catalogue — these become ``ad_hoc`` entries. They capture the canonical
#: "the autopilot guessed it" failure modes from the discovery.
_AD_HOC_CUES: tuple[str, ...] = (
    "api contract",
    "contrato de api",
    "endpoint shape",
    "naming",
    "nombrar",
    "library",
    "librería",
    "libreria",
    "dependency choice",
    "trade-off",
    "tradeoff",
    "schema design",
    "data model",
    "to decide",
    "a decidir",
    "tbd",
    "decision:",
    "decisión:",
    "decidir",
)


def _match_catalogue(line_lower: str) -> str | None:
    """Return the catalogued ``decision_key`` a line maps to, or ``None``."""
    for key, cues in _CATALOGUE_CUES:
        if any(cue in line_lower for cue in cues):
            # Defensive: only return keys that really live in the catalogue,
            # so a typo here can never invent a key the policy engine rejects.
            if key in DECISION_KEYS:
                return key
    return None


def _is_ad_hoc_decision(line_lower: str) -> bool:
    """Whether a non-catalogued line still signals a real decision."""
    return any(cue in line_lower for cue in _AD_HOC_CUES)


def _family_for(decision_key: str) -> str:
    """Catalogue family for a key, or ``"ad_hoc"``."""
    if decision_key == AD_HOC:
        return "ad_hoc"
    return DECISION_KEYS.get(decision_key, {}).get("family", "ad_hoc")


def _clean(line: str) -> str:
    """Trim markdown/list noise so ``source`` reads cleanly."""
    return re.sub(r"^[\s\-\*\d\.\)#>|]+", "", line).strip()


def build_decision_inventory(
    plan_content: str | None,
    *,
    extra_decisions: list[dict[str, Any]] | None = None,
) -> list[DecisionEntry]:
    """Scan a plan and return the inventory of decisions it contains (UC-601).

    Each line of ``plan_content`` is inspected: a line that mentions a
    catalogued cue becomes a catalogued :class:`DecisionEntry` (AC-02), a line
    that mentions an ad-hoc cue (an undocumented API contract, a naming choice)
    becomes an ``ad_hoc`` entry (AC-01/AC-02). Every entry records the plan
    line as ``source`` so the inventory is explainable and verifiable.

    ``extra_decisions`` lets a caller inject decisions discovered outside the
    plan text (e.g. surfaced by another tool) as ``{"description", "source",
    "decision_key"?}`` dicts; an unknown/absent ``decision_key`` falls to
    ``ad_hoc``.

    Determinism: ids are assigned by order of appearance (``D1``, ``D2``…), so
    the same plan always yields the same inventory — required for stable tests
    and for the audit log (UC-604).
    """

    entries: list[DecisionEntry] = []
    seen_sources: set[str] = set()

    def _add(description: str, source: str, decision_key: str) -> None:
        # De-duplicate on the cleaned source so a decision mentioned twice in
        # the plan does not inflate the inventory (and the gate count).
        norm = source.lower()
        if norm in seen_sources:
            return
        seen_sources.add(norm)
        key = decision_key if (decision_key == AD_HOC or decision_key in DECISION_KEYS) else AD_HOC
        entries.append(
            DecisionEntry(
                id=f"D{len(entries) + 1}",
                description=description,
                source=source,
                decision_key=key,
                family=_family_for(key),
            )
        )

    for raw_line in (plan_content or "").splitlines():
        line = _clean(raw_line)
        if not line:
            continue
        line_lower = line.lower()

        catalogued = _match_catalogue(line_lower)
        if catalogued is not None:
            _add(line, line, catalogued)
            continue

        if _is_ad_hoc_decision(line_lower):
            _add(line, line, AD_HOC)

    for extra in extra_decisions or []:
        desc = str(extra.get("description", "")).strip()
        if not desc:
            continue
        _add(desc, str(extra.get("source", desc)), str(extra.get("decision_key", AD_HOC)))

    return entries


# ── Classification (UC-602) ────────────────────────────────────────────────


def _is_inviolable(decision_key: str) -> bool:
    """Whether a catalogued key is marked ``inviolable`` in the catalogue.

    Inviolable keys (``destructive_action``, ``image_cost_over_budget``,
    ``branch_to_main_push``) must NEVER be classified ``autonomous``, at any
    autopilot level — "more autonomy" can never mean "less safety" (AC-05).
    """
    if decision_key == AD_HOC:
        return False
    return bool(DECISION_KEYS.get(decision_key, {}).get("inviolable", False))


def classify_decision(
    entry: DecisionEntry,
    *,
    context: dict[str, Any] | None = None,
) -> DecisionEntry:
    """Classify one decision ``autonomous`` vs. ``user_dependent`` (UC-602).

    Catalogued decisions delegate to
    :func:`server.app_docs.autopilot.evaluate_decision` — the engine's single
    source of truth for tier policy — so the triage never re-implements the
    autopilot levels or the inviolable rules. ``action == "auto"`` →
    ``autonomous`` and the verbatim ``reason`` from the policy engine is
    propagated (AC-03); ``ask`` / ``block`` → ``user_dependent``.

    ``ad_hoc`` decisions (task-specific, e.g. an undocumented API contract) get
    a **conservative default**: ``user_dependent`` unless an explicit
    inheritable in ``context`` backs them as safe (AC-04). A false autonomous
    brings the original bug back; a false user_dependent is merely one extra
    question — so the asymmetry is resolved toward asking.

    Inviolable keys are pinned ``user_dependent`` with a defensive guard
    (AC-05): even if a mis-configured policy ever returned ``auto`` for one,
    the triage refuses to mark it autonomous. The guard makes the safety
    guarantee independent of configuration.

    Mutates and returns ``entry`` (its ``meta`` carries ``classification``,
    ``action`` and ``reason``).
    """
    ctx = dict(context or {})

    # AC-05: inviolable keys can never be autonomous, regardless of policy.
    if _is_inviolable(entry.decision_key):
        decision = evaluate_decision(entry.decision_key, ctx)
        entry.meta.update(
            classification=USER_DEPENDENT,
            action=decision.get("action", "ask"),
            reason="inviolable_never_autonomous",
        )
        return entry

    if entry.decision_key != AD_HOC:
        # AC-03: delegate to the policy engine; propagate its reason verbatim.
        decision = evaluate_decision(entry.decision_key, ctx)
        action = decision.get("action", "ask")
        classification = AUTONOMOUS if action == "auto" else USER_DEPENDENT
        entry.meta.update(
            classification=classification,
            action=action,
            reason=decision.get("reason", ""),
        )
        return entry

    # AC-04: ad_hoc → conservative default user_dependent, unless an explicit
    # inheritable backs it. ``ad_hoc_inheritable`` is an opt-in escape hatch a
    # caller sets only when ``app_spec`` (or equivalent) genuinely resolves the
    # decision — absent it, we always ask.
    inheritable = bool(ctx.get("ad_hoc_inheritable", False))
    entry.meta.update(
        classification=AUTONOMOUS if inheritable else USER_DEPENDENT,
        action="auto" if inheritable else "ask",
        reason="ad_hoc_inheritable_resolved" if inheritable else "ad_hoc_conservative_default",
    )
    return entry


def classify_inventory(
    entries: list[DecisionEntry],
    *,
    context: dict[str, Any] | None = None,
) -> list[DecisionEntry]:
    """Classify every entry of an inventory in place (UC-602)."""
    return [classify_decision(e, context=context) for e in entries]


def inventory_to_dict(entries: list[DecisionEntry]) -> dict[str, Any]:
    """Package an inventory as a JSON-serializable payload (AC-01).

    When the entries have been classified (UC-602), the payload also reports
    the ``user_dependent`` count and a ``verdict`` the gate (UC-603) consumes:
    ``needs_user_input`` when any decision is user-dependent, else
    ``no_user_decisions`` (so a fully-autonomous task does not interrupt —
    AC-08).
    """
    user_dependent = sum(
        1 for e in entries if e.meta.get("classification") == USER_DEPENDENT
    )
    classified = any("classification" in e.meta for e in entries)
    payload: dict[str, Any] = {
        "decisions": [e.to_dict() for e in entries],
        "total": len(entries),
        "catalogued": sum(1 for e in entries if e.decision_key != AD_HOC),
        "ad_hoc": sum(1 for e in entries if e.decision_key == AD_HOC),
    }
    if classified:
        payload["user_dependent"] = user_dependent
        payload["autonomous"] = sum(
            1 for e in entries if e.meta.get("classification") == AUTONOMOUS
        )
        payload["verdict"] = (
            "needs_user_input" if user_dependent > 0 else "no_user_decisions"
        )
    return payload
