/**
 * lib/handoff-builder.mjs — Builds .quality/handoff.md from local state.
 *
 * Used by:
 *   - .claude/skills/handoff/SKILL.md (skill flow)
 *   - .claude/hooks/on-session-end.mjs (auto fallback)
 *
 * Public API:
 *   buildHandoffData(opts) → object with all fields needed by the template
 *   renderHandoff(data, narrative) → final Markdown string
 *   writeHandoff(narrative, opts) → writes to .quality/handoff.md and returns { path, data }
 *
 * Design: all "mechanical" fields are auto-populated. The skill is responsible
 * for asking the model to fill the narrative parts (what_this_session_did,
 * decisions_taken, open_questions, next_concrete_step) and passing them in.
 *
 * Engram and heartbeat side-effects live in the skill, not here. This module
 * is pure I/O on the local filesystem so it's testable in isolation.
 */

import { readFileSync, writeFileSync, existsSync, statSync, readdirSync } from 'fs';
import { createHash } from 'crypto';
import { basename, join } from 'path';
import {
  git,
  readJsonFile,
  findFiles,
  fileExists,
  mkdir,
  now,
} from './utils.mjs';

const HANDOFF_PATH = '.quality/handoff.md';
const MAX_CHARS = 14000;
const MAX_HOT_FILES = 8;

/**
 * Generate a deterministic 12-char session_id from cwd + date.
 * Same cwd on the same day yields the same id (useful for de-dup).
 */
export function computeSessionId(cwd, date) {
  const d = (date || new Date().toISOString()).slice(0, 10);
  return createHash('sha256').update(`${cwd}:${d}`).digest('hex').slice(0, 12);
}

/**
 * Read the most recent checkpoint and return { feature, phase, phase_name }.
 */
function readLatestCheckpoint() {
  const files = findFiles('.quality/evidence', /^checkpoint\.json$/);
  if (files.length === 0) return null;
  let latest = null;
  let latestMtime = 0;
  for (const f of files) {
    try {
      const m = statSync(f).mtimeMs;
      if (m > latestMtime) {
        latestMtime = m;
        latest = f;
      }
    } catch { /* ignore */ }
  }
  if (!latest) return null;
  const cp = readJsonFile(latest);
  if (!cp) return null;
  return {
    path: latest,
    feature: cp.feature || '',
    phase: cp.phase || null,
    phase_name: cp.phase_name || '',
    branch: cp.branch || '',
    timestamp: cp.timestamp || '',
  };
}

/**
 * Read .quality/active_uc.json if present.
 */
function readActiveUC() {
  const data = readJsonFile('.quality/active_uc.json');
  if (!data) return null;
  return {
    uc_id: data.uc_id || data.feature || null,
    started_at: data.started_at || null,
  };
}

/**
 * Detect the configured backend from .claude/settings.local.json or app_spec.md.
 * Returns 'freeform' | 'trello' | 'plane' | 'unknown'.
 */
function detectBackend() {
  const settings = readJsonFile('.claude/settings.local.json');
  if (settings?.specbox?.backend_type) return settings.specbox.backend_type;
  if (settings?.trello?.boardId) return 'trello';
  if (settings?.plane?.projectId) return 'plane';
  if (existsSync('doc/tracking/items.json')) return 'freeform';
  return 'unknown';
}

/**
 * Count healing events from latest healing.jsonl.
 */
function countHealingEvents() {
  const files = findFiles('.quality/evidence', /^healing\.jsonl$/);
  if (files.length === 0) return 0;
  let total = 0;
  for (const f of files) {
    try {
      total += readFileSync(f, 'utf-8').split('\n').filter(Boolean).length;
    } catch { /* ignore */ }
  }
  return total;
}

/**
 * Count blocking feedback (severity critical|major and status=open).
 */
function countBlockingFeedback() {
  const files = findFiles('.quality/evidence', /^FB-.*\.json$/);
  let blocking = 0;
  for (const f of files) {
    const fb = readJsonFile(f);
    if (!fb) continue;
    if ((fb.status || 'open') !== 'open') continue;
    const sev = fb.severity || 'minor';
    if (sev === 'critical' || sev === 'major') blocking++;
  }
  return blocking;
}

/**
 * Estimate context tokens used in this session by summing chars of changed files.
 * Same heuristic on-session-end.mjs uses (chars / 4).
 */
function estimateContextTokens() {
  const changed = new Set();
  const diff = git('diff --name-only HEAD');
  const cached = git('diff --cached --name-only');
  if (diff) diff.split('\n').filter(Boolean).forEach((f) => changed.add(f));
  if (cached) cached.split('\n').filter(Boolean).forEach((f) => changed.add(f));
  let chars = 0;
  for (const f of changed) {
    if (existsSync(f)) {
      try {
        chars += readFileSync(f, 'utf-8').length;
      } catch { /* ignore */ }
    }
  }
  return Math.floor(chars / 4);
}

/**
 * Top N changed files by patch size in current diff.
 */
function topHotFiles(limit = MAX_HOT_FILES) {
  const stat = git(`diff --stat HEAD`);
  if (!stat) return [];
  const files = [];
  for (const line of stat.split('\n')) {
    const m = line.match(/^\s*([^|]+?)\s*\|\s*(\d+)/);
    if (m) {
      files.push({ path: m[1].trim(), changes: Number(m[2]) });
    }
  }
  files.sort((a, b) => b.changes - a.changes);
  return files.slice(0, limit).map((f) => f.path);
}

/** The newest of `paths` whose text names `ucId` (UC-11006: a plan or PRD covers several UCs). */
function newestMentioning(paths, ucId) {
  if (!/^UC-/i.test(ucId || '')) return null;
  const named = new RegExp(`\\b${ucId.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'i');
  const withTime = paths.flatMap((p) => {
    try {
      return [{ p, t: statSync(p).mtimeMs }];
    } catch {
      return [];
    }
  });
  for (const { p } of withTime.sort((a, b) => b.t - a.t)) {
    try {
      if (named.test(readFileSync(p, 'utf-8').slice(0, 400_000))) return p;
    } catch { /* unreadable: next */ }
  }
  return null;
}

function listDir(dir) {
  try {
    return readdirSync(dir);
  } catch {
    return [];
  }
}

/**
 * Resolve known pointer paths: plan, prd, checkpoint.
 *
 * UC-11006: /prd writes doc/prd/<feature>/prd.md and /plan doc/plans/<name>_plan.md, where
 * <feature> and <name> are the feature slug of the checkpoint or a story id, not the active UC.
 * Exact paths for the UC and the feature first (the old doc/prds/… and uc_… ones still count);
 * then the newest plan or PRD that names the active UC. Nothing found → null, never a guess.
 */
function resolvePointers(active) {
  const keys = [...new Set([active?.feature, active?.checkpointFeature].filter(Boolean))];
  const out = { plan: null, prd: null, checkpoint: null };
  if (keys.length === 0) return out;

  const exact = (paths) => paths.find((p) => existsSync(p)) || null;
  const slugs = keys.flatMap((k) => [k, k.toLowerCase().replace(/^uc-/, 'uc_')]);

  out.plan = exact(slugs.map((k) => `doc/plans/${k}_plan.md`))
    || newestMentioning(listDir('doc/plans').filter((f) => f.endsWith('.md')).map((f) => join('doc/plans', f)), active?.feature);

  out.prd = exact(keys.flatMap((k) => [`doc/prd/${k}/prd.md`]).concat(slugs.map((k) => `doc/prds/${k}_prd.md`)))
    || newestMentioning(listDir('doc/prd').map((d) => join('doc/prd', d, 'prd.md')).filter((p) => existsSync(p)), active?.feature);

  out.checkpoint = exact(keys.map((k) => `.quality/evidence/${k}/checkpoint.json`));
  return out;
}

/**
 * Build the mechanical part of the handoff (everything except narrative bullets).
 *
 * @param {object} opts
 * @param {string} [opts.trigger='manual']
 * @param {string} [opts.cwd=process.cwd()]
 * @returns {object} data structure for the template
 */
export function buildHandoffData(opts = {}) {
  const trigger = opts.trigger || 'manual';
  const cwd = opts.cwd || process.cwd();
  const project = basename(cwd).replace(/_/g, '-');
  const generatedAt = now();
  const sessionId = computeSessionId(cwd, generatedAt);

  const branch = git('branch --show-current') || 'unknown';
  const lastCommitSha = git('log -1 --pretty=format:%h') || 'unknown';
  const lastCommitSubject = git('log -1 --pretty=format:%s') || '';

  const activeUC = readActiveUC();
  const checkpoint = readLatestCheckpoint();

  let activeUCDisplay = 'none';
  let activeUCId = null;
  if (activeUC?.uc_id) {
    activeUCId = activeUC.uc_id;
    if (checkpoint?.feature === activeUC.uc_id && checkpoint.phase) {
      activeUCDisplay = `${activeUC.uc_id} (Phase ${checkpoint.phase} — ${checkpoint.phase_name})`;
    } else {
      activeUCDisplay = activeUC.uc_id;
    }
  } else if (checkpoint?.feature) {
    activeUCId = checkpoint.feature;
    activeUCDisplay = checkpoint.phase
      ? `${checkpoint.feature} (Phase ${checkpoint.phase} — ${checkpoint.phase_name})`
      : checkpoint.feature;
  }

  const hotFiles = topHotFiles();
  const pointers = resolvePointers({ feature: activeUCId, checkpointFeature: checkpoint?.feature });

  return {
    generated_at: generatedAt,
    schema_version: 1,
    project,
    session_id: sessionId,
    trigger,
    ttl_minutes: 1440,
    branch,
    active_uc: activeUCId,
    active_uc_display: activeUCDisplay,
    backend: detectBackend(),
    last_commit_sha: lastCommitSha,
    last_commit_subject: lastCommitSubject,
    healing_events: countHealingEvents(),
    blocking_feedback: countBlockingFeedback(),
    context_tokens_est: estimateContextTokens(),
    hot_files: hotFiles,
    pointers,
  };
}

function renderBullets(items, fallback = '_(none)_') {
  if (!items || items.length === 0) return fallback;
  return items.map((s) => `- ${s}`).join('\n');
}

function redactSecrets(text) {
  if (!text) return text;
  return text
    .replace(/sk_live_[A-Za-z0-9_-]+/g, '<redacted-stripe-key>')
    .replace(/sk_test_[A-Za-z0-9_-]+/g, '<redacted-stripe-test-key>')
    .replace(/(?:^|[^A-Za-z0-9_])([A-Za-z0-9_-]{32,})(?=[^A-Za-z0-9_]|$)/g, (m, tok) => {
      if (/^[a-f0-9]{40,}$/i.test(tok)) return m;
      return m.replace(tok, '<redacted-token>');
    });
}

/**
 * Render the full Markdown using the data + narrative bullets supplied by the skill.
 *
 * @param {object} data — output of buildHandoffData
 * @param {object} narrative
 * @param {string[]} [narrative.what_this_session_did]
 * @param {string[]} [narrative.decisions_taken]
 * @param {string[]} [narrative.open_questions]
 * @param {string} [narrative.next_concrete_step]
 * @returns {string} the rendered Markdown
 */
export function renderHandoff(data, narrative = {}) {
  const what = renderBullets(narrative.what_this_session_did);
  const decisions = renderBullets(narrative.decisions_taken);
  const questions = renderBullets(narrative.open_questions);
  const nextStep = redactSecrets(narrative.next_concrete_step) || '_(none)_';

  const hotFilesBlock = renderBullets(data.hot_files);

  const pointerLines = [];
  if (data.pointers.plan) pointerLines.push(`Plan: ${data.pointers.plan}`);
  if (data.pointers.prd) pointerLines.push(`PRD: ${data.pointers.prd}`);
  if (data.pointers.checkpoint) pointerLines.push(`Checkpoint: ${data.pointers.checkpoint}`);
  if (narrative.engram_obs_id) pointerLines.push(`Engram observation_id: ${narrative.engram_obs_id}`);
  const pointers = renderBullets(pointerLines);

  const md = `---
generated_at: ${data.generated_at}
generator: specbox-handoff-v1
schema_version: ${data.schema_version}
project: ${data.project}
session_id: ${data.session_id}
trigger: ${data.trigger}
ttl_minutes: ${data.ttl_minutes}
branch: ${data.branch}
active_uc: ${data.active_uc === null ? 'null' : data.active_uc}
---

# SpecBox Handoff — ${data.project}

## State snapshot
- **Branch**: ${data.branch}
- **Active UC**: ${data.active_uc_display}
- **Backend**: ${data.backend}
- **Last commit**: ${data.last_commit_sha} "${data.last_commit_subject}"
- **Healing events this session**: ${data.healing_events}
- **Open feedback (blocking)**: ${data.blocking_feedback}
- **Context tokens estimated this session**: ${data.context_tokens_est}

## What this session did
${redactSecrets(what)}

## Decisions taken (with key)
${redactSecrets(decisions)}

## Open questions
${redactSecrets(questions)}

## Hot files (top N by edits this session)
${hotFilesBlock}

## Next concrete step
${nextStep}

## Pointers para la próxima sesión
${pointers}
`;

  if (md.length > MAX_CHARS) {
    return md.slice(0, MAX_CHARS - 100) + '\n\n_(truncated to fit max size)_\n';
  }
  return md;
}

/**
 * Write handoff to .quality/handoff.md.
 *
 * @param {object} narrative — narrative bullets (see renderHandoff)
 * @param {object} [opts]
 * @returns {{ path: string, data: object }}
 */
export function writeHandoff(narrative = {}, opts = {}) {
  mkdir('.quality');
  const data = buildHandoffData(opts);
  const md = renderHandoff(data, narrative);
  writeFileSync(HANDOFF_PATH, md, 'utf-8');
  return { path: HANDOFF_PATH, data };
}
