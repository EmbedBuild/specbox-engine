/**
 * lib/autopilot.mjs — Autopilot policy engine for SpecBox skills and hooks (v5.29.0).
 *
 * Reads `.claude/settings.local.json` → `specbox.autopilot` and decides whether
 * a given decision_key should be auto-confirmed, queued (deferred), asked
 * synchronously, or always blocked.
 *
 * Policy tiers:
 *   low           — every decision asks (v5.28 behavior, default if config absent)
 *   conservador   — only cosmetic (tokens, stitch_design_per_screen) auto-confirm
 *   equilibrado   — cosmetic + visual derived (veg_preview, image_cost_under_budget) when high confidence
 *   agresivo      — equilibrado + lenient definition_quality_gate when AC score >=0.7
 *
 * Inviolable: destructive_action, branch_to_main_push, image_cost_over_budget
 * never auto-confirm regardless of tier.
 */

import { readJsonFile, appendLine } from './utils.mjs';
import { join } from 'path';

// ── Decision keys catalog ────────────────────────────────────────────
//
// Each entry maps a decision_key (used in skills/hooks) to its family,
// rule per tier, and inviolable status. Skills consult this table via
// `evaluateDecision(decisionKey, context)` instead of hardcoding policy.

export const DECISION_KEYS = {
  // Cosmetic — safe to auto-confirm: regenerable, no monetary cost.
  tokens_confirmation:        { family: 'cosmetic', tiers: { low: 'ask', conservador: 'auto', equilibrado: 'auto', agresivo: 'auto' } },
  stitch_design_per_screen:   { family: 'cosmetic', tiers: { low: 'ask', conservador: 'auto', equilibrado: 'auto', agresivo: 'auto' } },
  design_system_update_check: { family: 'cosmetic', tiers: { low: 'ask', conservador: 'auto', equilibrado: 'auto', agresivo: 'auto' } },

  // VEG / visual derived — auto-confirm only when confidence is high enough.
  veg_preview:                { family: 'visual_derived', tiers: { low: 'ask', conservador: 'ask', equilibrado: 'auto_if_score_high', agresivo: 'auto_if_score_low' }, scoreThreshold: { equilibrado: 0.8, agresivo: 0.7 } },
  image_cost_under_budget:    { family: 'visual_derived', tiers: { low: 'ask', conservador: 'ask', equilibrado: 'auto_if_under_budget', agresivo: 'auto_if_under_budget' } },

  // Calidad de spec — sólo el modo agresivo deja pasar AC con score alto.
  definition_quality_gate:    { family: 'spec_quality', tiers: { low: 'ask', conservador: 'ask', equilibrado: 'ask', agresivo: 'auto_if_score_high' }, scoreThreshold: { agresivo: 0.7 } },
  feature_problem_definition: { family: 'spec_quality', tiers: { low: 'ask', conservador: 'ask', equilibrado: 'ask', agresivo: 'ask' } },
  feature_ui_interaction_profile: { family: 'spec_quality', tiers: { low: 'ask', conservador: 'ask', equilibrado: 'auto_if_app_prd', agresivo: 'auto_if_app_prd' } },
  feedback_field_classification: { family: 'spec_quality', tiers: { low: 'ask', conservador: 'ask', equilibrado: 'ask', agresivo: 'ask' } },

  // Arquitectónico — heredables desde app_prd/app_spec si están definidos.
  feature_aesthetic_direction: { family: 'architectural', tiers: { low: 'ask', conservador: 'ask', equilibrado: 'auto_if_app_spec', agresivo: 'auto_if_app_spec' } },
  backend_selection:           { family: 'architectural', tiers: { low: 'ask', conservador: 'ask', equilibrado: 'auto_freeform_default', agresivo: 'auto_freeform_default' } },
  veg_mode_selection:          { family: 'architectural', tiers: { low: 'ask', conservador: 'ask', equilibrado: 'auto_if_app_spec', agresivo: 'auto_if_app_spec' } },

  // Operativo — preguntas de aclaración / advertencia.
  origin_detection:               { family: 'operational', tiers: { low: 'ask', conservador: 'ask', equilibrado: 'auto_if_unique', agresivo: 'auto_if_unique' } },
  uncommitted_changes_warning:    { family: 'operational', tiers: { low: 'ask', conservador: 'ask', equilibrado: 'ask', agresivo: 'ask' } },
  stitch_api_key_missing:         { family: 'operational', tiers: { low: 'ask', conservador: 'ask', equilibrado: 'ask', agresivo: 'ask' } },
  stitch_config_decision:         { family: 'operational', tiers: { low: 'ask', conservador: 'ask', equilibrado: 'ask', agresivo: 'ask' } },
  // US-29 — visual provider del VEG (stitch/claude_design). Elección del usuario: siempre ask.
  visual_provider_selection:      { family: 'operational', tiers: { low: 'ask', conservador: 'ask', equilibrado: 'ask', agresivo: 'ask' } },
  claude_design_config_check:     { family: 'operational', tiers: { low: 'ask', conservador: 'ask', equilibrado: 'ask', agresivo: 'ask' } },

  // Inviolables — siempre síncronos.
  destructive_action:        { family: 'destructive', tiers: { low: 'ask', conservador: 'ask', equilibrado: 'ask', agresivo: 'ask' }, inviolable: true },
  image_cost_over_budget:    { family: 'destructive', tiers: { low: 'ask', conservador: 'ask', equilibrado: 'ask', agresivo: 'ask' }, inviolable: true },
  branch_to_main_push:       { family: 'destructive', tiers: { low: 'block', conservador: 'block', equilibrado: 'block', agresivo: 'block' }, inviolable: true },
};

// ── Config loading ───────────────────────────────────────────────────

const VALID_TIERS = ['low', 'conservador', 'equilibrado', 'agresivo'];
const DEFAULT_BUDGET_EUR = 5;

/**
 * Load autopilot config from .claude/settings.local.json.
 * Returns a normalized object with `level`, `image_budget_eur_per_feature`,
 * `auto_confirm_overrides`, `always_ask_overrides`. Falls back to safe
 * defaults (`level: "low"`) when no config exists — matches v5.28 behavior.
 *
 * @param {string} [projectPath] - Project root (default: cwd).
 */
export function loadAutopilotConfig(projectPath = '.') {
  const settings = readJsonFile(join(projectPath, '.claude/settings.local.json')) || {};
  const cfg = settings.specbox?.autopilot || {};
  const level = VALID_TIERS.includes(cfg.level) ? cfg.level : 'low';
  return {
    level,
    image_budget_eur_per_feature: typeof cfg.image_budget_eur_per_feature === 'number'
      ? cfg.image_budget_eur_per_feature
      : DEFAULT_BUDGET_EUR,
    auto_confirm_overrides: Array.isArray(cfg.auto_confirm_overrides) ? cfg.auto_confirm_overrides : [],
    always_ask_overrides: Array.isArray(cfg.always_ask_overrides) ? cfg.always_ask_overrides : [],
    queue_enabled: cfg.queue_enabled === true, // off by default in v5.29.0
    queue_auto_resolve_days: typeof cfg.queue_auto_resolve_days === 'number' ? cfg.queue_auto_resolve_days : 7,
    raw: cfg,
  };
}

// ── Decision evaluation ──────────────────────────────────────────────

/**
 * Evaluate a single decision against the active autopilot policy.
 *
 * @param {string} decisionKey - Key from DECISION_KEYS.
 * @param {object} context - Optional signals: { score, costEur, hasAppPrd, hasAppSpec, isUnique, projectPath }.
 * @returns {object} { autoConfirm, action: 'auto'|'ask'|'block'|'queue', reason, decisionKey, level }.
 */
export function evaluateDecision(decisionKey, context = {}) {
  const def = DECISION_KEYS[decisionKey];
  if (!def) {
    return { autoConfirm: false, action: 'ask', reason: 'unknown_decision_key', decisionKey, level: null };
  }
  const config = loadAutopilotConfig(context.projectPath);
  const level = config.level;

  // 1) always_ask_overrides take precedence (user pinned).
  if (config.always_ask_overrides.includes(decisionKey)) {
    return { autoConfirm: false, action: 'ask', reason: 'user_override_always_ask', decisionKey, level };
  }

  // 2) Inviolable rules cannot be auto-confirmed by any tier or override.
  if (def.inviolable) {
    const action = def.tiers[level] || 'ask';
    return { autoConfirm: false, action, reason: 'inviolable_rule', decisionKey, level };
  }

  // 3) auto_confirm_overrides: user explicitly opted-in for this key.
  if (config.auto_confirm_overrides.includes(decisionKey)) {
    return { autoConfirm: true, action: 'auto', reason: 'user_override_auto_confirm', decisionKey, level };
  }

  // 4) Tier rule.
  const rule = def.tiers[level] || 'ask';
  const decision = applyRule(rule, def, context, level);
  return { ...decision, decisionKey, level };
}

function applyRule(rule, def, ctx, level) {
  switch (rule) {
    case 'auto':
      return { autoConfirm: true, action: 'auto', reason: 'tier_default' };
    case 'ask':
      return { autoConfirm: false, action: 'ask', reason: 'tier_default' };
    case 'block':
      return { autoConfirm: false, action: 'block', reason: 'destructive_blocked' };
    case 'auto_if_score_high':
    case 'auto_if_score_low': {
      const threshold = def.scoreThreshold?.[level];
      if (typeof ctx.score !== 'number' || typeof threshold !== 'number') {
        return { autoConfirm: false, action: 'ask', reason: 'missing_score_or_threshold' };
      }
      return ctx.score >= threshold
        ? { autoConfirm: true, action: 'auto', reason: `score_${ctx.score}_meets_${threshold}` }
        : { autoConfirm: false, action: 'ask', reason: `score_${ctx.score}_below_${threshold}` };
    }
    case 'auto_if_under_budget': {
      const config = loadAutopilotConfig(ctx.projectPath);
      const budget = config.image_budget_eur_per_feature;
      if (typeof ctx.costEur !== 'number') {
        return { autoConfirm: false, action: 'ask', reason: 'missing_cost' };
      }
      return ctx.costEur <= budget
        ? { autoConfirm: true, action: 'auto', reason: `cost_${ctx.costEur}_within_budget_${budget}` }
        : { autoConfirm: false, action: 'ask', reason: `cost_${ctx.costEur}_over_budget_${budget}` };
    }
    case 'auto_if_app_prd':
      return ctx.hasAppPrd
        ? { autoConfirm: true, action: 'auto', reason: 'app_prd_provides_value' }
        : { autoConfirm: false, action: 'ask', reason: 'no_app_prd_to_inherit_from' };
    case 'auto_if_app_spec':
      return ctx.hasAppSpec
        ? { autoConfirm: true, action: 'auto', reason: 'app_spec_provides_value' }
        : { autoConfirm: false, action: 'ask', reason: 'no_app_spec_to_inherit_from' };
    case 'auto_if_unique':
      return ctx.isUnique
        ? { autoConfirm: true, action: 'auto', reason: 'unique_match' }
        : { autoConfirm: false, action: 'ask', reason: 'ambiguous_match' };
    case 'auto_freeform_default':
      // backend_selection: default to freeform when no other backend is configured.
      return { autoConfirm: true, action: 'auto', reason: 'freeform_default_v5_29' };
    default:
      return { autoConfirm: false, action: 'ask', reason: `unknown_rule_${rule}` };
  }
}

// ── Audit logging ────────────────────────────────────────────────────

/**
 * Append an autopilot decision to `.quality/autopilot_decisions.jsonl`.
 * Every auto-confirmed decision MUST log here so the user can audit and
 * `/queue review --recent N` can revert recent automatic choices.
 *
 * @param {object} decision - Result from evaluateDecision().
 * @param {object} extra - { feature, value, ref, projectPath }.
 */
export function logAutoDecision(decision, extra = {}) {
  const projectPath = extra.projectPath || '.';
  const logPath = join(projectPath, '.quality', 'autopilot_decisions.jsonl');
  const entry = {
    ts: new Date().toISOString(),
    decision_key: decision.decisionKey,
    level: decision.level,
    action: decision.action,
    auto_confirm: decision.autoConfirm,
    reason: decision.reason,
    feature: extra.feature || null,
    value: extra.value !== undefined ? extra.value : null,
    ref: extra.ref || null,
  };
  appendLine(logPath, JSON.stringify(entry));
  return entry;
}

/**
 * Convenience: evaluate + log in one call. Returns the decision unchanged.
 */
export function evaluateAndLog(decisionKey, context = {}, extra = {}) {
  const decision = evaluateDecision(decisionKey, context);
  if (decision.autoConfirm) {
    logAutoDecision(decision, { ...extra, projectPath: context.projectPath });
  }
  return decision;
}
