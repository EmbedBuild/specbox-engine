import { useParams, Link } from 'react-router-dom'
import {
  ArrowLeft, Terminal, FileCode, Zap, Heart, CheckCircle,
  GitMerge, MessageSquare, Clock, Activity, TestTube2
} from 'lucide-react'
import { api } from '../api'
import type { ProjectActivity } from '../types'
import { useAutoRefresh } from '../hooks/useAutoRefresh'
import StackBadge from '../components/StackBadge'
import { timeAgo, formatNumber } from '../utils'

function MetricCard({ label, value, sub, icon, color }: {
  label: string; value: string | number; sub?: string; icon: React.ReactNode; color: string
}) {
  return (
    <div className={`card border ${color}`}>
      <div className="flex items-center gap-2 mb-2">
        {icon}
        <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">{label}</span>
      </div>
      <p className="text-lg md:text-xl font-bold text-white">{value}</p>
      {sub && <p className="text-[10px] md:text-xs text-slate-500 mt-1 truncate">{sub}</p>}
    </div>
  )
}

function RateBar({ label, rate, color }: { label: string; rate: number; color: string }) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs text-slate-400">{label}</span>
        <span className="text-xs font-mono text-slate-300">{rate ?? 0}%</span>
      </div>
      <div className="w-full h-2 bg-slate-800 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color} transition-all duration-500`} style={{ width: `${Math.min(rate ?? 0, 100)}%` }} />
      </div>
    </div>
  )
}

export default function ProjectDetail() {
  const { name } = useParams<{ name: string }>()
  const { data, loading, error } = useAutoRefresh<ProjectActivity>(
    () => api.projectDetail(name!),
    [name],
  )

  if (loading) return <div className="animate-pulse space-y-4"><div className="h-8 bg-slate-800 rounded w-64" /><div className="h-96 bg-slate-800 rounded-xl" /></div>
  if (error) return <p className="text-red-400">{error}</p>
  if (!data) return null

  const sessions = data.sessions ?? { count: 0, total_tokens: 0, total_files_modified: 0, avg_tokens_per_session: 0 }
  const healing = data.healing ?? { count: 0, resolved: 0, resolution_rate: 0 }
  const acceptance = data.acceptance ?? { validations: 0, accepted: 0, conditional: 0, rejected: 0, acceptance_rate: 0 }
  const merge = data.merge_pipeline ?? { total: 0, merged: 0, blocked: 0, blocked_by_feedback: 0, merge_rate: 0 }
  const feedback = data.feedback ?? { tickets: 0, resolutions: 0, open: 0, critical: 0, major: 0, invalidating: 0, resolution_rate: 0 }
  const e2e = data.e2e ?? {
    runs: 0, latest_total: 0, latest_passing: 0, latest_failing: 0,
    latest_skipped: 0, latest_pass_rate: null, latest_duration_ms: 0,
    viewports: [], trend: 'insufficient_data' as const,
  }
  const featuresActive = data.features_active ?? []

  return (
    <div className="space-y-4 md:space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3 md:gap-4">
        <Link to="/" className="p-2 rounded-lg hover:bg-slate-800 transition-colors">
          <ArrowLeft className="w-5 h-5 text-slate-400" />
        </Link>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 md:gap-3 flex-wrap">
            <h1 className="text-xl md:text-2xl font-bold text-white">{data.project}</h1>
            <StackBadge stack={data.stack} />
          </div>
          <p className="text-xs md:text-sm text-slate-400 mt-0.5 truncate">
            Ultimos {data.period_days} dias &middot; Ultima actividad: {timeAgo(data.last_activity)}
          </p>
        </div>
        <Link to={`/project/${name}/timeline`} className="px-3 md:px-4 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg text-xs md:text-sm text-slate-300 transition-colors flex items-center gap-2 flex-shrink-0">
          <Clock className="w-4 h-4" /> <span className="hidden sm:inline">Timeline</span>
        </Link>
      </div>

      {/* Sessions */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4">
        <MetricCard label="Sesiones" value={sessions.count} icon={<Terminal className="w-4 h-4 text-blue-400" />} color="border-blue-500/20" />
        <MetricCard label="Tokens" value={formatNumber(sessions.total_tokens)} sub={`~${formatNumber(sessions.avg_tokens_per_session)}/sesion`} icon={<Zap className="w-4 h-4 text-amber-400" />} color="border-amber-500/20" />
        <MetricCard label="Archivos" value={sessions.total_files_modified} icon={<FileCode className="w-4 h-4 text-purple-400" />} color="border-purple-500/20" />
        <MetricCard label="Features" value={featuresActive.length} sub={featuresActive.join(', ') || 'ninguna'} icon={<Activity className="w-4 h-4 text-cyan-400" />} color="border-cyan-500/20" />
      </div>

      {/* Rates */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4">
        <div className="card space-y-4">
          <div className="flex items-center gap-2 mb-1">
            <Heart className="w-4 h-4 text-rose-400" />
            <h3 className="text-sm font-semibold text-slate-300">Self-Healing</h3>
          </div>
          <div className="grid grid-cols-2 gap-3 text-center">
            <div><p className="text-xl md:text-2xl font-bold text-white">{healing.count}</p><p className="text-[10px] md:text-xs text-slate-500">eventos</p></div>
            <div><p className="text-xl md:text-2xl font-bold text-emerald-400">{healing.resolved}</p><p className="text-[10px] md:text-xs text-slate-500">resueltos</p></div>
          </div>
          <RateBar label="Resolution rate" rate={healing.resolution_rate} color="bg-emerald-500" />
        </div>

        <div className="card space-y-4">
          <div className="flex items-center gap-2 mb-1">
            <CheckCircle className="w-4 h-4 text-cyan-400" />
            <h3 className="text-sm font-semibold text-slate-300">Acceptance</h3>
          </div>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div><p className="text-base md:text-lg font-bold text-emerald-400">{acceptance.accepted}</p><p className="text-[10px] md:text-xs text-slate-500">accepted</p></div>
            <div><p className="text-base md:text-lg font-bold text-amber-400">{acceptance.conditional}</p><p className="text-[10px] md:text-xs text-slate-500">conditional</p></div>
            <div><p className="text-base md:text-lg font-bold text-red-400">{acceptance.rejected}</p><p className="text-[10px] md:text-xs text-slate-500">rejected</p></div>
          </div>
          <RateBar label="Acceptance rate" rate={acceptance.acceptance_rate} color="bg-cyan-500" />
        </div>

        <div className="card space-y-4">
          <div className="flex items-center gap-2 mb-1">
            <GitMerge className="w-4 h-4 text-indigo-400" />
            <h3 className="text-sm font-semibold text-slate-300">Merge Pipeline</h3>
          </div>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div><p className="text-base md:text-lg font-bold text-emerald-400">{merge.merged}</p><p className="text-[10px] md:text-xs text-slate-500">merged</p></div>
            <div><p className="text-base md:text-lg font-bold text-red-400">{merge.blocked}</p><p className="text-[10px] md:text-xs text-slate-500">blocked</p></div>
            <div><p className="text-base md:text-lg font-bold text-orange-400">{merge.blocked_by_feedback}</p><p className="text-[10px] md:text-xs text-slate-500">by FB</p></div>
          </div>
          <RateBar label="Merge rate" rate={merge.merge_rate} color="bg-indigo-500" />
        </div>

        <div className="card space-y-4">
          <div className="flex items-center gap-2 mb-1">
            <TestTube2 className="w-4 h-4 text-teal-400" />
            <h3 className="text-sm font-semibold text-slate-300">E2E Testing</h3>
          </div>
          {e2e.runs > 0 ? (
            <>
              <div className="grid grid-cols-3 gap-2 text-center">
                <div>
                  <p className="text-base md:text-lg font-bold text-emerald-400">{e2e.latest_passing}</p>
                  <p className="text-[10px] md:text-xs text-slate-500">passing</p>
                </div>
                <div>
                  <p className="text-base md:text-lg font-bold text-red-400">{e2e.latest_failing}</p>
                  <p className="text-[10px] md:text-xs text-slate-500">failing</p>
                </div>
                <div>
                  <p className="text-base md:text-lg font-bold text-slate-400">{e2e.latest_skipped}</p>
                  <p className="text-[10px] md:text-xs text-slate-500">skipped</p>
                </div>
              </div>
              <RateBar
                label="E2E Pass Rate"
                rate={e2e.latest_pass_rate ?? 0}
                color={e2e.latest_failing === 0 ? 'bg-teal-500' : 'bg-red-500'}
              />
              <div className="flex items-center justify-between text-xs text-slate-500">
                <span>{e2e.viewports.join(', ')}</span>
                <TrendIndicator trend={e2e.trend} />
              </div>
            </>
          ) : (
            <p className="text-xs text-slate-500 text-center py-4">Sin E2E tests</p>
          )}
        </div>
      </div>

      {/* Feedback */}
      {(feedback.tickets ?? 0) > 0 && (
        <div className="card">
          <div className="flex items-center gap-2 mb-4">
            <MessageSquare className="w-4 h-4 text-orange-400" />
            <h3 className="text-sm font-semibold text-slate-300">Feedback Loop</h3>
          </div>
          <div className="grid grid-cols-3 md:grid-cols-6 gap-3 md:gap-4 text-center">
            <div><p className="text-lg md:text-xl font-bold text-white">{feedback.tickets}</p><p className="text-[10px] md:text-xs text-slate-500">tickets</p></div>
            <div><p className="text-lg md:text-xl font-bold text-amber-400">{feedback.open}</p><p className="text-[10px] md:text-xs text-slate-500">abiertos</p></div>
            <div><p className="text-lg md:text-xl font-bold text-red-400">{feedback.critical}</p><p className="text-[10px] md:text-xs text-slate-500">critical</p></div>
            <div><p className="text-lg md:text-xl font-bold text-orange-400">{feedback.major}</p><p className="text-[10px] md:text-xs text-slate-500">major</p></div>
            <div><p className="text-lg md:text-xl font-bold text-purple-400">{feedback.invalidating}</p><p className="text-[10px] md:text-xs text-slate-500">invalidating</p></div>
            <div><p className="text-lg md:text-xl font-bold text-emerald-400">{feedback.resolutions}</p><p className="text-[10px] md:text-xs text-slate-500">resueltos</p></div>
          </div>
          <div className="mt-4">
            <RateBar label="Resolution rate" rate={feedback.resolution_rate} color="bg-orange-500" />
          </div>
        </div>
      )}
    </div>
  )
}

function TrendIndicator({ trend }: { trend: string }) {
  if (trend === 'improving') return <span className="text-emerald-400">↑ mejorando</span>
  if (trend === 'degrading') return <span className="text-red-400">↓ degradando</span>
  if (trend === 'stable') return <span>— estable</span>
  return <span>—</span>
}
