export type SkillCategory =
	| 'pipeline'
	| 'quality'
	| 'visual'
	| 'tracking'
	| 'stripe'
	| 'lifecycle'
	| 'other';

export const CATEGORY_ORDER: readonly SkillCategory[] = [
	'pipeline', 'quality', 'visual', 'tracking', 'stripe', 'lifecycle', 'other',
] as const;

export const CATEGORY_LABELS: Record<SkillCategory, string> = {
	pipeline: 'Pipeline',
	quality: 'Quality',
	visual: 'Visual',
	tracking: 'Tracking',
	stripe: 'Stripe',
	lifecycle: 'Lifecycle',
	other: 'Other',
};

export const CATEGORY_ICONS: Record<SkillCategory, string> = {
	pipeline: 'rocket',
	quality: 'shield',
	visual: 'paintcan',
	tracking: 'list-tree',
	stripe: 'credit-card',
	lifecycle: 'tools',
	other: 'question',
};

const SKILL_TO_CATEGORY: Record<string, SkillCategory> = {
	// Pipeline
	prd: 'pipeline',
	plan: 'pipeline',
	implement: 'pipeline',
	feedback: 'pipeline',
	// Quality
	audit: 'quality',
	compliance: 'quality',
	'quality-gate': 'quality',
	'acceptance-check': 'quality',
	// Visual
	'visual-setup': 'visual',
	'adapt-ui': 'visual',
	'check-designs': 'visual',
	// Tracking
	'switch-backend': 'tracking',
	'app-init': 'tracking',
	'app-sync': 'tracking',
	'queue-review': 'tracking',
	// Stripe
	'stripe-connect': 'stripe',
	'stripe-standard': 'stripe',
	'stripe-switch-account': 'stripe',
	// Lifecycle
	release: 'lifecycle',
	handoff: 'lifecycle',
	discovery: 'lifecycle',
	quickstart: 'lifecycle',
	'manual-test': 'lifecycle',
	'optimize-agents': 'lifecycle',
	explore: 'lifecycle',
};

export function getCategoryFor(skillName: string): SkillCategory {
	return SKILL_TO_CATEGORY[skillName] ?? 'other';
}
