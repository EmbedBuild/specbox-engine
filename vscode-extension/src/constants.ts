import * as path from 'path';
import * as os from 'os';

export const CLAUDE_DIR = path.join(os.homedir(), '.claude');
export const CLAUDE_SKILLS_DIR = path.join(CLAUDE_DIR, 'skills');
export const CLAUDE_HOOKS_DIR = path.join(CLAUDE_DIR, 'hooks');
export const CLAUDE_HOOKS_LIB_DIR = path.join(CLAUDE_HOOKS_DIR, 'lib');
export const CLAUDE_COMMANDS_DIR = path.join(CLAUDE_DIR, 'commands');
export const CLAUDE_SETTINGS = path.join(CLAUDE_DIR, 'settings.json');
export const CLAUDE_SETTINGS_LOCAL = path.join(CLAUDE_DIR, 'settings.local.json');
/** Where Claude Code keeps MCP servers (user and local scope) — not the settings files. */
export const CLAUDE_JSON = path.join(os.homedir(), '.claude.json');

/** UC-3902 AC-04 — where the person disconnects a device when the account already has five. */
export const PANEL_DEVICES_URL = 'https://cloud.specbox.build/profile';

/** UC-3904 AC-06 — "How SpecBox connects", public page of the panel (ES / EN). */
export function howToConnectUrl(language: string | undefined): string {
	return (language ?? '').toLowerCase().startsWith('es')
		? 'https://cloud.specbox.build/como-se-conecta'
		: 'https://cloud.specbox.build/how-to-connect';
}

// Canonical list of SpecBox engine skills. Used as the categorization source
// of truth (every entry here must be mapped in skill-categories.ts) and as a
// drift detector in tests. The runtime sidebar reads skills from the filesystem
// via skill-loader.ts — this array is NOT the source of truth for what the
// TreeView displays.
export const KNOWN_SKILLS = [
	'acceptance-check', 'adapt-ui', 'app-init', 'app-sync', 'audit',
	'check-designs', 'compliance', 'discovery', 'explore', 'feedback',
	'handoff', 'implement', 'manual-test', 'optimize-agents', 'plan',
	'prd', 'quality-gate', 'queue-review', 'quickstart', 'release',
	'stripe-connect', 'stripe-standard', 'stripe-switch-account',
	'switch-backend', 'visual-setup',
];

export const REQUIRED_NODE_VERSION = 18;

// US-26 (UC-2601) — Funnel telemetry. The extension emits an `activation` event
// to the same public Supabase project the site uses, via the RPC
// `public.ingest_site_event` (deployed in US-25). The anon JWT below is the
// legacy public anon key — identical to the one shipped in the site bundle, safe
// to embed (RLS restricts what it can do; the RPC only ingests funnel events).
export const SUPABASE_URL = 'https://nywjsvumsvxlpflpbord.supabase.co';
export const SUPABASE_ANON_KEY =
	'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im55d2pzdnVtc3Z4bHBmbHBib3JkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzk0MDA1OTYsImV4cCI6MjA5NDk3NjU5Nn0.v3uN9mPotaSV3uvWTD0T_n-fLK39ij5NwQdpSnwAG9I';
