import {
  Terminal, GitBranch, Heart, CheckCircle, XCircle,
  GitMerge, MessageSquare, AlertTriangle, Clock, TestTube2
} from 'lucide-react'
import type { TimelineEvent as TEvent } from '../types'
import { timeAgo } from '../utils'

const eventConfig: Record<string, { icon: typeof Terminal; color: string; label: string }> = {
  session: { icon: Terminal, color: 'text-blue-400 bg-blue-500/10', label: 'Sesion' },
  checkpoint: { icon: GitBranch, color: 'text-purple-400 bg-purple-500/10', label: 'Checkpoint' },
  healing: { icon: Heart, color: 'text-amber-400 bg-amber-500/10', label: 'Healing' },
  acceptance_test: { icon: CheckCircle, color: 'text-emerald-400 bg-emerald-500/10', label: 'Test AG-09a' },
  acceptance_validation: { icon: CheckCircle, color: 'text-cyan-400 bg-cyan-500/10', label: 'Validacion AG-09b' },
  merge: { icon: GitMerge, color: 'text-indigo-400 bg-indigo-500/10', label: 'Merge' },
  feedback: { icon: MessageSquare, color: 'text-orange-400 bg-orange-500/10', label: 'Feedback' },
  feedback_resolution: { icon: CheckCircle, color: 'text-green-400 bg-green-500/10', label: 'FB Resuelto' },
  e2e_run: { icon: TestTube2, color: 'text-teal-400 bg-teal-500/10', label: 'E2E Test' },
}

function getEventSummary(event: TEvent): string {
  switch (event.event_type) {
    case 'session':
      return `${event.files_modified || 0} archivos modificados, ${((event.context_tokens_est as number) || 0).toLocaleString()} tokens`
    case 'checkpoint':
      return `${event.feature} — Fase ${event.phase}: ${event.phase_name || ''}`
    case 'healing':
      return `${event.feature} — Nivel ${event.level}: ${event.error_type} → ${event.result}`
    case 'acceptance_test':
      return `${event.feature} — ${event.tests_passed ?? 0}/${event.tests_total ?? 0} tests passed`
    case 'acceptance_validation':
      return `${event.feature} — ${event.verdict} (${event.criteria_passed ?? 0}/${event.criteria_total ?? 0})`
    case 'merge':
      return `${event.feature} — PR #${event.pr_number}: ${event.merge_status}`
    case 'feedback':
      return `${event.feedback_id}: ${event.description || ''}`
    case 'feedback_resolution':
      return `${event.feedback_id} resuelto: ${event.resolution || ''}`
    case 'e2e_run':
      return `E2E: ${event.passing}/${event.total} passing (${event.pass_rate}%)${event.viewports ? ` [${(event.viewports as string[]).join(', ')}]` : ''}`
    default:
      return JSON.stringify(event).slice(0, 100)
  }
}

function getResultBadge(event: TEvent) {
  const type = event.event_type
  if (type === 'healing') {
    const result = event.result as string
    if (result === 'resolved') return <span className="badge bg-emerald-500/10 text-emerald-400">Resolved</span>
    if (result === 'failed') return <span className="badge bg-red-500/10 text-red-400">Failed</span>
    return <span className="badge bg-amber-500/10 text-amber-400">{result}</span>
  }
  if (type === 'acceptance_validation') {
    const verdict = event.verdict as string
    const colors: Record<string, string> = {
      ACCEPTED: 'bg-emerald-500/10 text-emerald-400',
      CONDITIONAL: 'bg-amber-500/10 text-amber-400',
      REJECTED: 'bg-red-500/10 text-red-400',
    }
    return <span className={`badge ${colors[verdict] || 'bg-slate-500/10 text-slate-400'}`}>{verdict}</span>
  }
  if (type === 'merge') {
    const status = event.merge_status as string
    if (status === 'merged') return <span className="badge bg-emerald-500/10 text-emerald-400">Merged</span>
    if (status === 'blocked') return <span className="badge bg-red-500/10 text-red-400">Blocked</span>
    return null
  }
  if (type === 'feedback') {
    const severity = event.severity as string
    const colors: Record<string, string> = {
      critical: 'bg-red-500/10 text-red-400',
      major: 'bg-amber-500/10 text-amber-400',
      minor: 'bg-slate-500/10 text-slate-400',
    }
    return <span className={`badge ${colors[severity] || 'bg-slate-500/10 text-slate-400'}`}>{severity}</span>
  }
  if (type === 'e2e_run') {
    const status = event.status as string
    if (status === 'green') return <span className="badge bg-emerald-500/10 text-emerald-400">Pass</span>
    return <span className="badge bg-red-500/10 text-red-400">Fail</span>
  }
  return null
}

export default function TimelineEventCard({ event }: { event: TEvent }) {
  const cfg = eventConfig[event.event_type] || eventConfig.session
  const Icon = cfg.icon

  return (
    <div className="flex gap-3 md:gap-4 py-3 px-3 md:px-4 table-row rounded-lg">
      <div className={`w-7 h-7 md:w-8 md:h-8 rounded-lg ${cfg.color} flex items-center justify-center flex-shrink-0 mt-0.5`}>
        <Icon className="w-3.5 h-3.5 md:w-4 md:h-4" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5 flex-wrap">
          <span className="text-[10px] md:text-xs font-medium text-slate-400">{cfg.label}</span>
          {getResultBadge(event)}
        </div>
        <p className="text-xs md:text-sm text-slate-200 truncate">{getEventSummary(event)}</p>
      </div>
      <div className="flex items-center gap-1 md:gap-1.5 text-[10px] md:text-xs text-slate-500 flex-shrink-0">
        <Clock className="w-3 h-3 hidden sm:block" />
        <span title={event.timestamp}>{timeAgo(event.timestamp)}</span>
      </div>
    </div>
  )
}
