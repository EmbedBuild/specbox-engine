import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';
import { CLAUDE_SETTINGS_LOCAL } from './constants';
import { REMOTE_MCP_URL } from './mcp';

// US-CONN-UPGRADE (UC-664/665/666) — client-config migration after an engine update.
//
// Same shape as prerequisites.ts: a PURE core (detectClientConfigCase,
// planMigration, buildMigrationSummary, applyMigrationToSettings) with no
// vscode import needed at call time, plus a thin vscode UI/IO layer. Tests
// import the pure core from out/migration.js with vscode stubbed.
//
// Why this exists: v6.7.0 (#82) shipped a regression where existing clients kept
// an obsolete "Local mode" MCP config that no longer works (the local server was
// removed — see mcp.ts REMOTE_MCP_URL). After an update the extension must detect
// that stale config and migrate transport to the hosted endpoint, WITHOUT ever
// auto-moving tracking data (that stays behind an explicit confirmation gate).

// --- Domain types ---

/** The 5 canonical client-config cases (AC-01 of UC-664). */
export type ClientConfigCase =
  | 'freeform_local_obsolete'   // FreeForm but MCP still points at a local/legacy server → migrate transport
  | 'freeform_remote_ok'        // FreeForm already on the hosted endpoint → nothing to do
  | 'trello_plane_unchanged'    // Trello/Plane backend → transport not affected, nothing to do
  | 'native_oauth_unchanged'    // Native + OAuth → nothing to do
  | 'onboarding_incomplete';    // No backend / no MCP configured yet → defer to onboarding

/** Minimal shape of ~/.claude/settings.local.json the detector reads. */
export interface ClaudeSettingsLocal {
  specbox?: {
    backend_type?: string;
    [k: string]: unknown;
  };
  mcpServers?: Record<string, { command?: string; args?: string[]; env?: Record<string, string>; [k: string]: unknown }>;
  [k: string]: unknown;
}

/** A single migration action proposed for a case. */
export interface MigrationAction {
  kind: 'reconfigure_transport' | 'move_tracking_data';
  description: string;
  /** Destructive actions (data movement) require explicit user confirmation (AC-04). */
  destructive: boolean;
}

/** The migration plan for a detected case (AC-02 of UC-664). */
export interface MigrationPlan {
  case: ClientConfigCase;
  /** Engine version that produced this plan (origin version, sent to the server). */
  fromVersion: string | null;
  actions: MigrationAction[];
  /** True when the plan can be applied automatically (no destructive actions). */
  autoApplicable: boolean;
  /** True when at least one action moves data and needs explicit confirmation. */
  requiresConfirmation: boolean;
}

// --- Pure detection (AC-01) ---

/**
 * Is the SpecBox-MCP entry pointing at the hosted endpoint? An entry is "remote
 * ok" when its args reference REMOTE_MCP_URL (directly, or wrapped by the
 * SecretStorage launcher whose inner config carries the same URL).
 */
function isRemoteMcp(settings: ClaudeSettingsLocal): boolean {
  const entry = settings.mcpServers?.['SpecBox-MCP'];
  if (!entry) { return false; }
  const haystack = JSON.stringify(entry);
  return haystack.includes(REMOTE_MCP_URL);
}

/** Does the SpecBox-MCP entry look like the removed local mode? */
function isLocalMcp(settings: ClaudeSettingsLocal): boolean {
  const entry = settings.mcpServers?.['SpecBox-MCP'];
  if (!entry) { return false; }
  const cmd = String(entry.command ?? '');
  const args = (entry.args ?? []).map(String);
  const blob = JSON.stringify(entry);
  // Legacy local mode launched the server via python/uv or a local module path,
  // and never referenced the hosted URL.
  if (blob.includes(REMOTE_MCP_URL)) { return false; }
  if (cmd === 'uv' || cmd === 'python' || cmd === 'python3') { return true; }
  if (args.some((a) => a.includes('server.server') || a.includes('-m server'))) { return true; }
  if (args.some((a) => a === 'run' && cmd === 'uv')) { return true; }
  return false;
}

/**
 * Classify the client config into one of the 5 canonical cases. Pure: takes the
 * parsed settings (and the parsed MCP config when stored separately). Deterministic
 * and total — every input maps to exactly one case.
 */
export function detectClientConfigCase(settings: ClaudeSettingsLocal | null): ClientConfigCase {
  const s = settings ?? {};
  const backend = s.specbox?.backend_type;
  const hasMcp = Boolean(s.mcpServers?.['SpecBox-MCP']);

  // No backend declared AND no MCP server → the project never finished onboarding.
  if (!backend && !hasMcp) { return 'onboarding_incomplete'; }

  switch (backend) {
    case 'trello':
    case 'plane':
      return 'trello_plane_unchanged';
    case 'native':
      return 'native_oauth_unchanged';
    case 'freeform':
      if (isRemoteMcp(s)) { return 'freeform_remote_ok'; }
      if (isLocalMcp(s)) { return 'freeform_local_obsolete'; }
      // FreeForm with no usable MCP entry → treat as obsolete so we reconfigure transport.
      return hasMcp ? 'freeform_local_obsolete' : 'onboarding_incomplete';
    default:
      // Backend missing but an MCP entry exists: if it's the stale local one,
      // it needs migrating; otherwise onboarding is still incomplete.
      if (isLocalMcp(s)) { return 'freeform_local_obsolete'; }
      return 'onboarding_incomplete';
  }
}

// --- Pure planning (AC-02 + AC-04) ---

/**
 * Build the migration plan for a case. The server (upgrade_project /
 * detect_*_migration_case) may enrich this, but the client computes a safe
 * default locally so the flow works even if the server call fails.
 *
 * Only `freeform_local_obsolete` produces an actionable plan; the rest are
 * no-ops. Transport reconfiguration is non-destructive (autoApplicable); any
 * data movement is flagged destructive and blocks auto-apply (AC-04).
 */
export function planMigration(detected: ClientConfigCase, fromVersion: string | null): MigrationPlan {
  const base: MigrationPlan = {
    case: detected,
    fromVersion,
    actions: [],
    autoApplicable: false,
    requiresConfirmation: false,
  };

  if (detected === 'freeform_local_obsolete') {
    base.actions = [{
      kind: 'reconfigure_transport',
      description: 'Switch the SpecBox MCP server from the removed local mode to the hosted endpoint (transport only — your tracking data is untouched).',
      destructive: false,
    }];
    base.autoApplicable = true;
    base.requiresConfirmation = false;
    return base;
  }

  // freeform_remote_ok / trello_plane_unchanged / native_oauth_unchanged /
  // onboarding_incomplete → no migration actions.
  base.autoApplicable = false;
  base.requiresConfirmation = false;
  return base;
}

/**
 * Merge a server-provided plan into the locally-computed one. If the server
 * proposes any data-movement action, the plan becomes confirmation-gated and is
 * NOT auto-applicable (AC-04 — the destructive gate is inviolable regardless of
 * what the server returns).
 */
export function reconcileServerPlan(local: MigrationPlan, serverActions: MigrationAction[] | null | undefined): MigrationPlan {
  if (!serverActions || serverActions.length === 0) { return local; }
  const actions = [...local.actions, ...serverActions];
  const hasDestructive = actions.some((a) => a.destructive || a.kind === 'move_tracking_data');
  return {
    ...local,
    actions,
    autoApplicable: !hasDestructive && actions.length > 0,
    requiresConfirmation: hasDestructive,
  };
}

// --- Pure settings transform (AC-01 of UC-665) ---

/**
 * Produce the migrated settings object: SpecBox-MCP pointed at the hosted
 * endpoint. Pure — does not touch disk. Preserves every other key (backend_type,
 * other MCP servers, unknown fields) byte-for-byte so revert is exact.
 */
export function applyMigrationToSettings(settings: ClaudeSettingsLocal | null): ClaudeSettingsLocal {
  const next: ClaudeSettingsLocal = settings ? structuredClone(settings) : {};
  if (!next.mcpServers) { next.mcpServers = {}; }
  next.mcpServers['SpecBox-MCP'] = { command: 'npx', args: ['mcp-remote', REMOTE_MCP_URL] };
  return next;
}

// --- Pure pedagogical summary (AC-02 of UC-665 + AC-02 of UC-666) ---

export interface MigrationSummary {
  /** What changed. */
  changed: string;
  /** What was migrated automatically. */
  migrated: string;
  /** Where the backup lives (null when nothing was backed up). */
  backup: string | null;
  /** What — if anything — the user must do. */
  action: string;
  /** True for the "nothing changed" minimal message (AC-02 of UC-666). */
  minimal: boolean;
}

/**
 * Build the per-case pedagogical summary. For actionable cases it carries the 4
 * sections (changed / migrated / backup / action). For no-op cases it is the
 * minimal "updated, nothing to do for your config" message.
 */
export function buildMigrationSummary(
  plan: MigrationPlan,
  ctx: { toVersion: string; backupPath: string | null },
): MigrationSummary {
  const v = ctx.toVersion;
  switch (plan.case) {
    case 'freeform_local_obsolete':
      return {
        changed: `SpecBox updated to v${v}. The local MCP server mode was removed; your FreeForm project now talks to the free hosted endpoint.`,
        migrated: 'Your MCP transport config was switched to the hosted endpoint automatically. Your tracking data in doc/tracking/ was not touched.',
        backup: ctx.backupPath,
        action: 'Nothing required — reload the window if Claude Code does not pick up the new MCP config. To undo, run "SpecBox: Revert last migration".',
        minimal: false,
      };
    case 'freeform_remote_ok':
      return minimalSummary(v, 'FreeForm (already on the hosted endpoint)');
    case 'trello_plane_unchanged':
      return minimalSummary(v, 'Trello/Plane');
    case 'native_oauth_unchanged':
      return minimalSummary(v, 'Native (GitHub OAuth)');
    case 'onboarding_incomplete':
      return {
        changed: `SpecBox updated to v${v}.`,
        migrated: 'No migration ran — this project has not finished onboarding yet.',
        backup: null,
        action: 'Run the SpecBox setup wizard to finish onboarding.',
        minimal: false,
      };
  }
}

function minimalSummary(version: string, _backendLabel: string): MigrationSummary {
  return {
    changed: `Updated to v${version} — no changes needed for your configuration.`,
    migrated: 'Nothing to migrate.',
    backup: null,
    action: 'Nothing to do.',
    minimal: true,
  };
}

/** Flatten a summary into the user-facing notification text. */
export function renderSummaryText(s: MigrationSummary): string {
  if (s.minimal) { return s.changed; }
  const lines = [s.changed, '', `• ${s.migrated}`];
  if (s.backup) { lines.push(`• Backup: ${s.backup}`); }
  lines.push(`• ${s.action}`);
  return lines.join('\n');
}

// --- vscode IO layer (backup / apply / revert) ---

/** Timestamped backup path for settings.local.json (AC-01 of UC-665). */
export function backupPathFor(settingsPath: string, stamp: string): string {
  return `${settingsPath}.bak-${stamp}`;
}

/**
 * Back up settings.local.json to a timestamped .bak BEFORE any mutation, then
 * write the migrated settings. Returns the backup path, or null when there was
 * no file to back up (fresh client). Pure-ish: takes an explicit timestamp so
 * tests are deterministic.
 */
export function backupAndMigrate(settingsPath: string, stamp: string): { backupPath: string | null; migrated: ClaudeSettingsLocal } {
  let original: ClaudeSettingsLocal | null = null;
  let backupPath: string | null = null;
  if (fs.existsSync(settingsPath)) {
    const raw = fs.readFileSync(settingsPath, 'utf-8');
    backupPath = backupPathFor(settingsPath, stamp);
    fs.writeFileSync(backupPath, raw, 'utf-8');
    try { original = JSON.parse(raw) as ClaudeSettingsLocal; } catch { original = null; }
  }
  const migrated = applyMigrationToSettings(original);
  fs.mkdirSync(path.dirname(settingsPath), { recursive: true });
  fs.writeFileSync(settingsPath, JSON.stringify(migrated, null, 2) + '\n', 'utf-8');
  return { backupPath, migrated };
}

/** Find the most recent settings.local.json.bak-* file, or null. */
export function findLatestBackup(settingsPath: string): string | null {
  const dir = path.dirname(settingsPath);
  const base = path.basename(settingsPath);
  let entries: string[];
  try {
    entries = fs.readdirSync(dir).filter((f) => f.startsWith(`${base}.bak-`));
  } catch {
    return null;
  }
  if (entries.length === 0) { return null; }
  // bak suffix is a sortable UTC stamp YYYYMMDDTHHMMSSZ → lexical sort = chronological.
  entries.sort();
  return path.join(dir, entries[entries.length - 1]);
}

/**
 * Restore settings.local.json from the most recent backup, byte-for-byte
 * (AC-03 of UC-665). Returns true on success.
 */
export function revertLastMigration(settingsPath: string): boolean {
  const latest = findLatestBackup(settingsPath);
  if (!latest) { return false; }
  const content = fs.readFileSync(latest, 'utf-8');
  fs.writeFileSync(settingsPath, content, 'utf-8');
  return true;
}

// --- vscode orchestration entry points (used by updater.ts in UC-666) ---

/** Resolve the canonical settings.local.json path (override for tests). */
export function settingsLocalPath(): string {
  return CLAUDE_SETTINGS_LOCAL;
}

/** Read + parse settings.local.json, or null. */
export function readClientSettings(settingsPath: string): ClaudeSettingsLocal | null {
  try {
    return JSON.parse(fs.readFileSync(settingsPath, 'utf-8')) as ClaudeSettingsLocal;
  } catch {
    return null;
  }
}

/**
 * Register the "SpecBox: Revert last migration" command (AC-03 of UC-665).
 * Idempotent registration is the caller's responsibility (called once from
 * activate()).
 */
export function registerRevertCommand(context: vscode.ExtensionContext): void {
  context.subscriptions.push(
    vscode.commands.registerCommand('specbox.revertMigration', async () => {
      const settingsPath = settingsLocalPath();
      const latest = findLatestBackup(settingsPath);
      if (!latest) {
        vscode.window.showInformationMessage(
          vscode.l10n.t('No migration backup found — nothing to revert.'),
        );
        return;
      }
      const ok = revertLastMigration(settingsPath);
      if (ok) {
        vscode.window.showInformationMessage(
          vscode.l10n.t('Reverted last migration from {0}. Reload the window to apply.', path.basename(latest)),
        );
      } else {
        vscode.window.showErrorMessage(
          vscode.l10n.t('Could not revert the last migration.'),
        );
      }
    }),
  );
}
