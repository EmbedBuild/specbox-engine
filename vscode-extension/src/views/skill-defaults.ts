export interface SkillDefaults {
	whatItDoes: string;
	whenToUse: string[];
	command: string;
	example: string;
}

// Static fallback content used when a SKILL.md frontmatter doesn't expose
// a structured description matching our 4-block layout. Hand-curated for
// the 25 canonical SpecBox engine skills.
//
// IMPORTANT: when adding a new skill to the engine, add an entry here too.
// Missing entries surface as "(no description available)" placeholders.
export const SKILL_DEFAULTS: Record<string, SkillDefaults> = {
	prd: {
		whatItDoes: 'Generates a Product Requirements Document (PRD) from a feature description and persists US/UC/AC into the tracking backend.',
		whenToUse: [
			'Starting a new feature with no spec yet.',
			'Right after /discovery returns READY_FOR_PRD.',
			'When you need to enrich an existing US-XX with technical context, NFRs, and risks.',
		],
		command: '/prd <feature_name>',
		example: '/prd vscode_discoverability_sidebar',
	},
	plan: {
		whatItDoes: 'Produces a technical implementation plan from a PRD, including UI component analysis, phases mapped to UCs, and Stitch design generation when applicable.',
		whenToUse: [
			'Right after /prd creates the US/UC/AC structure.',
			'Before /implement — the plan is the source of truth for phase execution.',
		],
		command: '/plan <US-XX | feature_name>',
		example: '/plan US-VSCODE-DISCOVERABILITY',
	},
	implement: {
		whatItDoes: 'Autopilot end-to-end implementation: creates a feature branch, executes all phases of a plan, runs QA + acceptance gates, and opens a PR.',
		whenToUse: [
			'When a plan exists in doc/plans/ and the US/UCs are in the tracking backend.',
			'For aggressive autopilot runs after /prd + /plan have produced trustworthy artifacts.',
		],
		command: '/implement <US-XX | UC-XXX | plan_name>',
		example: '/implement US-VSCODE-DISCOVERABILITY',
	},
	feedback: {
		whatItDoes: 'Captures developer testing feedback as structured evidence + a GitHub issue, and can invalidate an AG-09b acceptance verdict.',
		whenToUse: [
			'Found a bug during manual testing of a freshly merged UC.',
			'An acceptance criterion looks wrong after seeing the implementation in action.',
		],
		command: '/feedback <UC-XXX> "<short description>"',
		example: '/feedback UC-701 "Sidebar still shows /remote skill"',
	},
	audit: {
		whatItDoes: 'On-demand ISO/IEC 25010 (SQuaRE) quality audit. Generates a PDF + JSON report with scores across 8 quality characteristics.',
		whenToUse: [
			'Quarterly or per-release quality snapshot.',
			'Before pitching the project to a stakeholder who cares about quality posture.',
		],
		command: '/audit',
		example: '/audit',
	},
	compliance: {
		whatItDoes: 'SpecBox compliance audit — checks engine version alignment, hooks, settings, quality infrastructure, and spec-driven posture. Auto-fixes safe gaps.',
		whenToUse: [
			'Verifying a project is on the current engine version after an upgrade.',
			'Diagnosing why hooks or skills aren\'t firing as expected.',
		],
		command: '/compliance [--fix]',
		example: '/compliance --fix',
	},
	'quality-gate': {
		whatItDoes: 'Runs adaptive quality gates with auto-discovered baseline and ratchet-safe coverage check.',
		whenToUse: [
			'Before opening a PR, to validate that lint + tests + coverage meet baseline.',
			'After resolving a chunk of self-healing, to confirm no regression.',
		],
		command: '/quality-gate',
		example: '/quality-gate',
	},
	'acceptance-check': {
		whatItDoes: 'Standalone acceptance check — validates AC from a PRD against code without the full /implement pipeline.',
		whenToUse: [
			'Verifying acceptance for an external PR you didn\'t implement yourself.',
			'Spot-checking that a UC meets its acceptance criteria mid-flight.',
		],
		command: '/acceptance-check <UC-XXX>',
		example: '/acceptance-check UC-701',
	},
	'visual-setup': {
		whatItDoes: 'Configures the complete visual identity of a project: Brand Kit, Stitch Design System, VEG base, and multi-form-factor settings.',
		whenToUse: [
			'First time setting up the visual identity for a new project.',
			'Refreshing brand tokens after a rebrand or partner change.',
		],
		command: '/visual-setup',
		example: '/visual-setup',
	},
	'adapt-ui': {
		whatItDoes: 'Scans the project\'s widget/component structure and generates a UI inventory mapping file.',
		whenToUse: [
			'Onboarding a legacy codebase before planning a feature.',
			'When /plan needs an up-to-date inventory of reusable components.',
		],
		command: '/adapt-ui',
		example: '/adapt-ui',
	},
	'check-designs': {
		whatItDoes: 'Retroactive compliance check for Stitch designs. Scans all UCs with screens and reports which have HTML designs and which don\'t.',
		whenToUse: [
			'Auditing design-to-code traceability across a backlog.',
			'Before promoting a project from L0 to L1 in the design compliance ratchet.',
		],
		command: '/check-designs',
		example: '/check-designs',
	},
	'switch-backend': {
		whatItDoes: 'Migrates a project between tracking backends (FreeForm, Trello, Plane, Native) preserving US/UC/AC/comments/state.',
		whenToUse: [
			'Outgrowing FreeForm and adopting Plane/Trello for client reporting.',
			'Consolidating multi-developer work into the Native Postgres backend.',
		],
		command: '/switch-backend',
		example: '/switch-backend',
	},
	'app-init': {
		whatItDoes: 'Initializes or refreshes the canonical project documents doc/app/app_prd.md, app_spec.md, app_market.md.',
		whenToUse: [
			'Fresh clone of a SpecBox-enabled project.',
			'After major engine upgrade that introduced new canonical zones.',
		],
		command: '/app-init',
		example: '/app-init',
	},
	'app-sync': {
		whatItDoes: 'Verifies and reconciles drift between canonical docs (doc/app/*.md) and reality (code, tracking, lockfiles).',
		whenToUse: [
			'After a stack change (new lockfile) to refresh the auto zone.',
			'When app-docs-sync-guard warns about drift.',
		],
		command: '/app-sync [--check|--repair|--review|--rebuild-from-tracking]',
		example: '/app-sync --check',
	},
	'queue-review': {
		whatItDoes: 'Reviews and resolves entries in doc/app/decisions_queue.md — the deferred decisions queue populated by aggressive autopilot.',
		whenToUse: [
			'Periodic batch review of deferred decisions accumulated by autopilot.',
			'Before a release, to clean the queue.',
		],
		command: '/queue-review',
		example: '/queue-review',
	},
	'stripe-connect': {
		whatItDoes: 'Scaffolds a Stripe Connect marketplace integration (Express + Direct charges + embedded subscriptions) in a Supabase + React/Flutter project.',
		whenToUse: [
			'Building a marketplace product with multiple sellers and platform fees.',
			'Migrating an existing marketplace from a custom Stripe wiring to the SpecBox canonical setup.',
		],
		command: '/stripe-connect',
		example: '/stripe-connect',
	},
	'stripe-standard': {
		whatItDoes: 'Scaffolds a Stripe Standard account integration (no Connect) with up to 4 billing modalities: single subscription, tiered subscriptions, metered billing, one-shot checkout.',
		whenToUse: [
			'Adding payments to a SaaS or e-commerce product without marketplace topology.',
			'Choosing between subscription tiers, metered usage, or one-time payments.',
		],
		command: '/stripe-standard',
		example: '/stripe-standard',
	},
	'stripe-switch-account': {
		whatItDoes: 'Rotates the active Stripe account of a SpecBox project safely (dry-run plan + literal confirmation + rollback runbook).',
		whenToUse: [
			'Switching from test mode to live mode after launch.',
			'Migrating between Stripe accounts during an acquisition or restructure.',
		],
		command: '/stripe-switch-account',
		example: '/stripe-switch-account',
	},
	release: {
		whatItDoes: 'Audits the codebase for residuals, bumps ENGINE_VERSION.yaml + CHANGELOG + CLAUDE.md, and pushes the release to the remote.',
		whenToUse: [
			'Cutting a new engine version (major, minor, or patch).',
			'After a hotfix that touches multiple modules and needs a coordinated release.',
		],
		command: '/release',
		example: '/release',
	},
	handoff: {
		whatItDoes: 'Persists the fine-grained session state to .quality/handoff.md and Engram so the next session resumes with full context.',
		whenToUse: [
			'Before /clear or proposing context compaction to the user.',
			'When an active UC is still open and you need to switch machines.',
		],
		command: '/handoff',
		example: '/handoff',
	},
	discovery: {
		whatItDoes: 'Lightweight Product Discovery (15-30 min) that produces doc/discovery/<feature>/icp_jtbd.md with ICPs and rational/emotional JTBDs.',
		whenToUse: [
			'Before /prd, to ground the feature in real user jobs.',
			'When the value or audience of a feature is unclear.',
		],
		command: '/discovery <feature_name>',
		example: '/discovery vscode_discoverability_sidebar',
	},
	quickstart: {
		whatItDoes: 'Interactive tutorial that walks a new developer through the full SpecBox pipeline using a demo project.',
		whenToUse: [
			'First time using the SpecBox Engine.',
			'Onboarding a teammate to the spec-driven workflow.',
		],
		command: '/quickstart',
		example: '/quickstart',
	},
	'manual-test': {
		whatItDoes: 'Systematic manual testing skill with live bug resolution and stakeholder-grade evidence capture.',
		whenToUse: [
			'Validating a feature before a demo or release where no E2E exists.',
			'Capturing reproducible bug reports during stakeholder review.',
		],
		command: '/manual-test',
		example: '/manual-test',
	},
	'optimize-agents': {
		whatItDoes: 'Audits, scores, and optimizes the multi-agent setup of the project (model assignment, validation strategy, team coordination).',
		whenToUse: [
			'Quarterly tune-up of the agent system.',
			'After adding new agents or restructuring teams.',
		],
		command: '/optimize-agents',
		example: '/optimize-agents',
	},
	explore: {
		whatItDoes: 'Read-only codebase exploration and analysis — finds files, understands architecture, surfaces patterns. Cannot modify files.',
		whenToUse: [
			'Researching an unfamiliar codebase before /plan.',
			'Answering "where is X defined?" or "what touches Y?" without risk of accidental edits.',
		],
		command: '/explore "<question>"',
		example: '/explore "where is the OAuth loopback handler implemented?"',
	},
};
