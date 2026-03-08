export interface SalaProject {
  project: string
  stack: string
  last_activity: string
  sessions: number
  active_feature: string
  healing_health: 'healthy' | 'degraded' | 'critical'
  healing_events: number
  acceptance_validations: number
  last_verdict: string
  merges: number
  blocked: number
  feedback_open: number
  feedback_blocking: string[]
  e2e_total: number
  e2e_passing: number
  e2e_failing: number
  e2e_pass_rate: number | null
  e2e_runs: number
}

export interface SalaAggregates {
  total_projects: number
  total_sessions: number
  total_tokens: number
  most_active_project: string
  global_health: 'healthy' | 'degraded' | 'critical'
  total_validations: number
  total_accepted: number
  acceptance_rate: number
  total_merged: number
  total_blocked: number
  total_feedback_tickets: number
  total_feedback_open: number
  total_e2e_runs: number
  total_e2e_tests: number
  total_e2e_passing: number
  total_e2e_failing: number
  e2e_global_pass_rate: number | null
}

export interface SalaData {
  period_days: number
  projects: SalaProject[]
  aggregates: SalaAggregates
}

export interface ProjectActivity {
  project: string
  period_days: number
  sessions: {
    count: number
    total_tokens: number
    total_files_modified: number
    avg_tokens_per_session: number
  }
  features_active: string[]
  healing: {
    count: number
    resolved: number
    resolution_rate: number
  }
  acceptance: {
    validations: number
    accepted: number
    conditional: number
    rejected: number
    acceptance_rate: number
  }
  merge_pipeline: {
    total: number
    merged: number
    blocked: number
    blocked_by_feedback: number
    merge_rate: number
  }
  feedback: {
    tickets: number
    resolutions: number
    open: number
    critical: number
    major: number
    invalidating: number
    resolution_rate: number
  }
  e2e: {
    runs: number
    latest_total: number
    latest_passing: number
    latest_failing: number
    latest_skipped: number
    latest_pass_rate: number | null
    latest_duration_ms: number
    viewports: string[]
    trend: 'improving' | 'stable' | 'degrading' | 'insufficient_data'
  }
  last_activity: string
  stack: string
}

export interface TimelineEvent {
  timestamp: string
  event_type: string
  [key: string]: unknown
}

export interface TimelineData {
  project: string
  total_events: number
  showing: number
  timeline: TimelineEvent[]
}

export interface HealingFeature {
  feature: string
  events: number
  resolved: number
  failed: number
  max_level: number
}

export interface HealingData {
  total_events: number
  total_resolved: number
  total_failed: number
  resolution_rate: string
  by_level: Record<string, number>
  features: HealingFeature[]
  overall_health: string
  healing_events?: number
  message?: string
}

export interface UpgradeProject {
  project: string
  engine_version: string
  mcp_version: string
  last_upgraded_at: string
  stack: string
  needs_upgrade: boolean
}

export interface UpgradesData {
  current_engine_version: string
  current_mcp_version: string
  total_projects: number
  needs_upgrade: number
  up_to_date: number
  projects: UpgradeProject[]
}

export interface E2EProject {
  project: string
  total: number
  passing: number
  failing: number
  pass_rate: number
  viewports: string[]
  runs: number
  last_run: string
  trend: 'improving' | 'stable' | 'degrading' | 'insufficient_data'
}

export interface E2EData {
  total_projects_with_e2e: number
  total_tests: number
  total_passing: number
  total_failing: number
  global_pass_rate: number | null
  projects: E2EProject[]
}

export interface SpecDrivenProject {
  project: string
  board_id: string
  stack: string
  us_count: number
  uc_count: number
  ac_count: number
  progress: number
  last_sync: string
}

export interface SpecDrivenData {
  total_projects: number
  total_us: number
  total_uc: number
  total_ac: number
  avg_progress: number
  projects: SpecDrivenProject[]
}
