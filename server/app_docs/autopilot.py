"""Python port of the autopilot policy engine for MCP tools (v5.29.0 PR-5).

Mirrors `.claude/hooks/lib/autopilot.mjs` so skills (Markdown instructions
interpreted by Claude) can consult the policy via MCP tools without
needing a Node.js shell-out from inside the skill.

The catalogue is the single source of truth, and the JS and Python
implementations are kept in sync by hand. PR-5 ships both because:

* Hooks need synchronous, low-latency decision evaluation in JS.
* Skills + Python tools need async-friendly access in the same process
  as the MCP server.

If you change `DECISION_KEYS` here, mirror the change in `autopilot.mjs`
and update both test suites.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastmcp import FastMCP


# ── Catalog (mirror of autopilot.mjs DECISION_KEYS) ──────────────────


VALID_TIERS = ("low", "conservador", "equilibrado", "agresivo")

DECISION_KEYS: dict[str, dict[str, Any]] = {
    "tokens_confirmation": {
        "family": "cosmetic",
        "tiers": {"low": "ask", "conservador": "auto", "equilibrado": "auto", "agresivo": "auto"},
    },
    "stitch_design_per_screen": {
        "family": "cosmetic",
        "tiers": {"low": "ask", "conservador": "auto", "equilibrado": "auto", "agresivo": "auto"},
    },
    "design_system_update_check": {
        "family": "cosmetic",
        "tiers": {"low": "ask", "conservador": "auto", "equilibrado": "auto", "agresivo": "auto"},
    },
    "veg_preview": {
        "family": "visual_derived",
        "tiers": {"low": "ask", "conservador": "ask", "equilibrado": "auto_if_score_high", "agresivo": "auto_if_score_low"},
        "score_threshold": {"equilibrado": 0.8, "agresivo": 0.7},
    },
    "image_cost_under_budget": {
        "family": "visual_derived",
        "tiers": {"low": "ask", "conservador": "ask", "equilibrado": "auto_if_under_budget", "agresivo": "auto_if_under_budget"},
    },
    "definition_quality_gate": {
        "family": "spec_quality",
        "tiers": {"low": "ask", "conservador": "ask", "equilibrado": "ask", "agresivo": "auto_if_score_high"},
        "score_threshold": {"agresivo": 0.7},
    },
    "feature_problem_definition": {
        "family": "spec_quality",
        "tiers": {"low": "ask", "conservador": "ask", "equilibrado": "ask", "agresivo": "ask"},
    },
    "feature_ui_interaction_profile": {
        "family": "spec_quality",
        "tiers": {"low": "ask", "conservador": "ask", "equilibrado": "auto_if_app_prd", "agresivo": "auto_if_app_prd"},
    },
    "feedback_field_classification": {
        "family": "spec_quality",
        "tiers": {"low": "ask", "conservador": "ask", "equilibrado": "ask", "agresivo": "ask"},
    },
    "feature_aesthetic_direction": {
        "family": "architectural",
        "tiers": {"low": "ask", "conservador": "ask", "equilibrado": "auto_if_app_spec", "agresivo": "auto_if_app_spec"},
    },
    "backend_selection": {
        "family": "architectural",
        "tiers": {"low": "ask", "conservador": "ask", "equilibrado": "auto_freeform_default", "agresivo": "auto_freeform_default"},
    },
    "veg_mode_selection": {
        "family": "architectural",
        "tiers": {"low": "ask", "conservador": "ask", "equilibrado": "auto_if_app_spec", "agresivo": "auto_if_app_spec"},
    },
    "origin_detection": {
        "family": "operational",
        "tiers": {"low": "ask", "conservador": "ask", "equilibrado": "auto_if_unique", "agresivo": "auto_if_unique"},
    },
    "uncommitted_changes_warning": {
        "family": "operational",
        "tiers": {"low": "ask", "conservador": "ask", "equilibrado": "ask", "agresivo": "ask"},
    },
    "stitch_api_key_missing": {
        "family": "operational",
        "tiers": {"low": "ask", "conservador": "ask", "equilibrado": "ask", "agresivo": "ask"},
    },
    "stitch_config_decision": {
        "family": "operational",
        "tiers": {"low": "ask", "conservador": "ask", "equilibrado": "ask", "agresivo": "ask"},
    },
    "destructive_action": {
        "family": "destructive",
        "tiers": {"low": "ask", "conservador": "ask", "equilibrado": "ask", "agresivo": "ask"},
        "inviolable": True,
    },
    "image_cost_over_budget": {
        "family": "destructive",
        "tiers": {"low": "ask", "conservador": "ask", "equilibrado": "ask", "agresivo": "ask"},
        "inviolable": True,
    },
    "branch_to_main_push": {
        "family": "destructive",
        "tiers": {"low": "block", "conservador": "block", "equilibrado": "block", "agresivo": "block"},
        "inviolable": True,
    },
}

DEFAULT_BUDGET_EUR = 5.0


# ── Config ───────────────────────────────────────────────────────────


def load_autopilot_config(project_path: str | Path = ".") -> dict[str, Any]:
    """Read `.claude/settings.local.json` -> `specbox.autopilot`."""
    settings_path = Path(project_path) / ".claude" / "settings.local.json"
    cfg: dict[str, Any] = {}
    if settings_path.exists():
        try:
            data = json.loads(settings_path.read_text(encoding="utf-8"))
            cfg = (data.get("specbox") or {}).get("autopilot") or {}
        except (json.JSONDecodeError, OSError):
            cfg = {}

    level = cfg.get("level") if cfg.get("level") in VALID_TIERS else "low"
    return {
        "level": level,
        "image_budget_eur_per_feature": float(
            cfg.get("image_budget_eur_per_feature", DEFAULT_BUDGET_EUR)
        ) if isinstance(cfg.get("image_budget_eur_per_feature"), (int, float)) else DEFAULT_BUDGET_EUR,
        "auto_confirm_overrides": list(cfg.get("auto_confirm_overrides") or []),
        "always_ask_overrides": list(cfg.get("always_ask_overrides") or []),
        "queue_enabled": cfg.get("queue_enabled") is True,
        "queue_auto_resolve_days": int(cfg.get("queue_auto_resolve_days", 7))
        if isinstance(cfg.get("queue_auto_resolve_days"), int)
        else 7,
        "raw": cfg,
    }


# ── Evaluation ───────────────────────────────────────────────────────


def _apply_rule(
    rule: str,
    definition: dict[str, Any],
    ctx: dict[str, Any],
    level: str,
    budget: float,
) -> dict[str, Any]:
    if rule == "auto":
        return {"autoConfirm": True, "action": "auto", "reason": "tier_default"}
    if rule == "ask":
        return {"autoConfirm": False, "action": "ask", "reason": "tier_default"}
    if rule == "block":
        return {"autoConfirm": False, "action": "block", "reason": "destructive_blocked"}
    if rule in ("auto_if_score_high", "auto_if_score_low"):
        threshold = (definition.get("score_threshold") or {}).get(level)
        score = ctx.get("score")
        if not isinstance(score, (int, float)) or not isinstance(threshold, (int, float)):
            return {"autoConfirm": False, "action": "ask", "reason": "missing_score_or_threshold"}
        if score >= threshold:
            return {"autoConfirm": True, "action": "auto", "reason": f"score_{score}_meets_{threshold}"}
        return {"autoConfirm": False, "action": "ask", "reason": f"score_{score}_below_{threshold}"}
    if rule == "auto_if_under_budget":
        cost = ctx.get("costEur")
        if not isinstance(cost, (int, float)):
            return {"autoConfirm": False, "action": "ask", "reason": "missing_cost"}
        if cost <= budget:
            return {"autoConfirm": True, "action": "auto", "reason": f"cost_{cost}_within_budget_{budget}"}
        return {"autoConfirm": False, "action": "ask", "reason": f"cost_{cost}_over_budget_{budget}"}
    if rule == "auto_if_app_prd":
        return (
            {"autoConfirm": True, "action": "auto", "reason": "app_prd_provides_value"}
            if ctx.get("hasAppPrd")
            else {"autoConfirm": False, "action": "ask", "reason": "no_app_prd_to_inherit_from"}
        )
    if rule == "auto_if_app_spec":
        return (
            {"autoConfirm": True, "action": "auto", "reason": "app_spec_provides_value"}
            if ctx.get("hasAppSpec")
            else {"autoConfirm": False, "action": "ask", "reason": "no_app_spec_to_inherit_from"}
        )
    if rule == "auto_if_unique":
        return (
            {"autoConfirm": True, "action": "auto", "reason": "unique_match"}
            if ctx.get("isUnique")
            else {"autoConfirm": False, "action": "ask", "reason": "ambiguous_match"}
        )
    if rule == "auto_freeform_default":
        return {"autoConfirm": True, "action": "auto", "reason": "freeform_default_v5_29"}
    return {"autoConfirm": False, "action": "ask", "reason": f"unknown_rule_{rule}"}


def evaluate_decision(decision_key: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Pure-Python equivalent of the JS evaluateDecision."""
    ctx = dict(context or {})
    project_path = ctx.pop("projectPath", ".")
    # ``level_override`` lets a caller pin the autopilot level inline instead of
    # reading it from ``.claude/settings.local.json`` — needed when the MCP
    # server is remote and cannot see the client's settings (the pre-flight
    # triage tool, US-06). When absent (the default), behaviour is unchanged.
    level_override = ctx.pop("level_override", None)
    config = load_autopilot_config(project_path)
    level = level_override if level_override in VALID_TIERS else config["level"]

    definition = DECISION_KEYS.get(decision_key)
    if definition is None:
        return {
            "autoConfirm": False,
            "action": "ask",
            "reason": "unknown_decision_key",
            "decisionKey": decision_key,
            "level": None,
        }

    if decision_key in config["always_ask_overrides"]:
        return {
            "autoConfirm": False,
            "action": "ask",
            "reason": "user_override_always_ask",
            "decisionKey": decision_key,
            "level": level,
        }

    if definition.get("inviolable"):
        action = definition["tiers"].get(level, "ask")
        return {
            "autoConfirm": False,
            "action": action,
            "reason": "inviolable_rule",
            "decisionKey": decision_key,
            "level": level,
        }

    if decision_key in config["auto_confirm_overrides"]:
        return {
            "autoConfirm": True,
            "action": "auto",
            "reason": "user_override_auto_confirm",
            "decisionKey": decision_key,
            "level": level,
        }

    rule = definition["tiers"].get(level, "ask")
    result = _apply_rule(rule, definition, ctx, level, config["image_budget_eur_per_feature"])
    return {**result, "decisionKey": decision_key, "level": level}


def log_auto_decision(
    decision: dict[str, Any],
    *,
    project_path: str | Path = ".",
    feature: str | None = None,
    value: Any = None,
    ref: str | None = None,
) -> dict[str, Any]:
    """Append a JSONL entry to `.quality/autopilot_decisions.jsonl`."""
    log_path = Path(project_path) / ".quality" / "autopilot_decisions.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "decision_key": decision["decisionKey"],
        "level": decision.get("level"),
        "action": decision["action"],
        "auto_confirm": decision["autoConfirm"],
        "reason": decision["reason"],
        "feature": feature,
        "value": value,
        "ref": ref,
    }
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def evaluate_and_log(
    decision_key: str,
    context: dict[str, Any] | None = None,
    *,
    feature: str | None = None,
    value: Any = None,
    ref: str | None = None,
) -> dict[str, Any]:
    """Evaluate + log auto-decisions in one call."""
    decision = evaluate_decision(decision_key, context)
    project_path = (context or {}).get("projectPath", ".")
    if decision["autoConfirm"]:
        log_auto_decision(decision, project_path=project_path, feature=feature, value=value, ref=ref)
    return decision


# ── MCP registration ─────────────────────────────────────────────────


def register_autopilot_tools(mcp: FastMCP, engine_path: Path) -> None:
    """Expose autopilot evaluation as MCP tools so skills can call it."""

    @mcp.tool
    def evaluate_autopilot_decision(
        decision_key: str,
        project_path: str = ".",
        score: float | None = None,
        cost_eur: float | None = None,
        has_app_prd: bool | None = None,
        has_app_spec: bool | None = None,
        is_unique: bool | None = None,
        feature: str | None = None,
        log: bool = True,
    ) -> dict[str, Any]:
        """Evaluate one autopilot decision against the project policy.

        Skills call this before each gate or question. Returns
        `{autoConfirm, action, reason, decisionKey, level}`. When the
        decision auto-confirms and `log=True`, an entry is appended to
        `.quality/autopilot_decisions.jsonl` automatically.

        action ∈ {"auto", "ask", "block"}.

        Args:
            decision_key: One of the keys in DECISION_KEYS.
            project_path: Project root for loading settings (default cwd).
            score: Confidence score for veg_preview / definition_quality_gate.
            cost_eur: Image cost for image_cost_under_budget.
            has_app_prd: Whether doc/app/app_prd.md exists and has content.
            has_app_spec: Whether doc/app/app_spec.md exists and has content.
            is_unique: Whether the inferred match is unique (origin_detection).
            feature: Feature name to record in the audit log.
            log: Whether to append to autopilot_decisions.jsonl on auto.
        """
        ctx: dict[str, Any] = {"projectPath": project_path}
        if score is not None:
            ctx["score"] = score
        if cost_eur is not None:
            ctx["costEur"] = cost_eur
        if has_app_prd is not None:
            ctx["hasAppPrd"] = has_app_prd
        if has_app_spec is not None:
            ctx["hasAppSpec"] = has_app_spec
        if is_unique is not None:
            ctx["isUnique"] = is_unique
        if log:
            return evaluate_and_log(decision_key, ctx, feature=feature)
        return evaluate_decision(decision_key, ctx)

    @mcp.tool
    def list_decision_keys() -> dict[str, Any]:
        """List the catalogue of autopilot decision_keys with their tiers.

        Useful for skills that want to introspect available keys, and for
        operators auditing policy. Returns a dict keyed by decision_key.
        """
        return {
            "keys": {
                key: {
                    "family": d["family"],
                    "tiers": d["tiers"],
                    "inviolable": d.get("inviolable", False),
                    "score_threshold": d.get("score_threshold"),
                }
                for key, d in DECISION_KEYS.items()
            },
            "valid_levels": list(VALID_TIERS),
        }
