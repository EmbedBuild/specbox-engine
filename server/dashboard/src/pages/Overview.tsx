import { Link } from 'react-router-dom'
import {
  FolderOpen, Terminal, Heart, CheckCircle, GitMerge,
  MessageSquare, Activity, ExternalLink, TestTube2
} from 'lucide-react'
import { api } from '../api'
import type { SalaData } from '../types'
import { useAutoRefresh } from '../hooks/useAutoRefresh'
import KPICard from '../components/KPICard'
import HealthBadge from '../components/HealthBadge'
import StackBadge from '../components/StackBadge'
import VerdictBadge from '../components/VerdictBadge'
import { timeAgo, formatNumber } from '../utils'

export default function Overview() {
  const { data, loading, error } = useAutoRefresh<SalaData>(() => api.sala())

  if (loading) return <LoadingSkeleton />
  if (error) return <ErrorState message={error} />
  if (!data) return null

  const agg = data.aggregates ?? {} as Record<string, unknown>
  const projects = data.projects ?? []

  const acceptanceRate = agg.acceptance_rate ?? 0
  const totalMerged = agg.total_merged ?? 0
  const totalBlocked = agg.total_blocked ?? 0

  return (
    <div className="space-y-4 md:space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl md:text-2xl font-bold text-white">Dashboard</h1>
          <p className="text-xs md:text-sm text-slate-400 mt-1">
            Ultimos {data.period_days} dias &middot; {new Date().toLocaleDateString('es-ES', { weekday: 'long', day: 'numeric', month: 'long' })}
          </p>
        </div>
        {agg.global_health && <HealthBadge health={agg.global_health} size="md" />}
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 md:gap-4">
        <KPICard label="Proyectos" value={agg.total_projects ?? 0} icon={<FolderOpen className="w-4 h-4 md:w-5 md:h-5" />} color="blue" />
        <KPICard label="Sesiones (7d)" value={agg.total_sessions ?? 0} icon={<Terminal className="w-4 h-4 md:w-5 md:h-5" />} color="slate" />
        <KPICard label="Tokens" value={formatNumber(agg.total_tokens ?? 0)} icon={<Activity className="w-4 h-4 md:w-5 md:h-5" />} color="slate" />
        <KPICard label="Acceptance" value={`${acceptanceRate}%`} icon={<CheckCircle className="w-4 h-4 md:w-5 md:h-5" />} color={acceptanceRate >= 80 ? 'green' : acceptanceRate >= 50 ? 'amber' : 'red'} />
        <KPICard label="Merge Rate" value={totalMerged > 0 ? `${Math.round(totalMerged / (totalMerged + totalBlocked) * 100)}%` : '-'} icon={<GitMerge className="w-4 h-4 md:w-5 md:h-5" />} color="green" />
        <KPICard
          label="E2E Tests"
          value={agg.e2e_global_pass_rate != null ? `${agg.e2e_global_pass_rate}%` : '—'}
          icon={<TestTube2 className="w-4 h-4 md:w-5 md:h-5" />}
          color={
            agg.e2e_global_pass_rate == null ? 'slate'
            : agg.e2e_global_pass_rate >= 95 ? 'green'
            : agg.e2e_global_pass_rate >= 80 ? 'amber'
            : 'red'
          }
        />
      </div>

      {/* Projects Table */}
      <div className="card overflow-hidden">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">Proyectos</h2>
          <span className="text-xs text-slate-500">{projects.length} registrados</span>
        </div>

        {/* Desktop table */}
        <div className="overflow-x-auto hidden md:block">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-slate-500 uppercase tracking-wider border-b border-slate-800">
                <th className="text-left py-3 px-3 font-medium">Proyecto</th>
                <th className="text-left py-3 px-3 font-medium">Stack</th>
                <th className="text-left py-3 px-3 font-medium">Actividad</th>
                <th className="text-center py-3 px-3 font-medium">Sesiones</th>
                <th className="text-center py-3 px-3 font-medium">Health</th>
                <th className="text-center py-3 px-3 font-medium hidden lg:table-cell">Verdict</th>
                <th className="text-center py-3 px-3 font-medium hidden lg:table-cell">Merges</th>
                <th className="text-center py-3 px-3 font-medium hidden lg:table-cell">Blocked</th>
                <th className="text-center py-3 px-3 font-medium hidden xl:table-cell">E2E</th>
                <th className="text-center py-3 px-3 font-medium">Feedback</th>
                <th className="w-8"></th>
              </tr>
            </thead>
            <tbody>
              {projects.map(p => (
                <tr key={p.project} className="table-row">
                  <td className="py-3 px-3">
                    <Link to={`/project/${p.project}`} className="text-white font-medium hover:text-blue-400 transition-colors">
                      {p.project}
                    </Link>
                    {p.active_feature && (
                      <p className="text-xs text-slate-500 mt-0.5 truncate max-w-48">{p.active_feature}</p>
                    )}
                  </td>
                  <td className="py-3 px-3"><StackBadge stack={p.stack} /></td>
                  <td className="py-3 px-3 text-slate-400 text-xs">{timeAgo(p.last_activity)}</td>
                  <td className="py-3 px-3 text-center text-slate-300">{p.sessions ?? 0}</td>
                  <td className="py-3 px-3 text-center"><HealthBadge health={p.healing_health} /></td>
                  <td className="py-3 px-3 text-center hidden lg:table-cell"><VerdictBadge verdict={p.last_verdict} /></td>
                  <td className="py-3 px-3 text-center text-slate-300 hidden lg:table-cell">{p.merges ?? 0}</td>
                  <td className="py-3 px-3 text-center hidden lg:table-cell">
                    {(p.blocked ?? 0) > 0
                      ? <span className="text-red-400 font-medium">{p.blocked}</span>
                      : <span className="text-slate-600">0</span>
                    }
                  </td>
                  <td className="py-3 px-3 text-center hidden xl:table-cell">
                    {(p.e2e_total ?? 0) > 0
                      ? <span className={(p.e2e_failing ?? 0) > 0 ? 'text-red-400 font-medium' : 'text-emerald-400'}>
                          {p.e2e_passing ?? 0}/{p.e2e_total}
                        </span>
                      : <span className="text-slate-600">—</span>
                    }
                  </td>
                  <td className="py-3 px-3 text-center">
                    {(p.feedback_open ?? 0) > 0
                      ? <span className={`badge ${(p.feedback_blocking?.length ?? 0) > 0 ? 'bg-red-500/10 text-red-400' : 'bg-amber-500/10 text-amber-400'}`}>{p.feedback_open}</span>
                      : <span className="text-slate-600">0</span>
                    }
                  </td>
                  <td className="py-3 px-3">
                    <Link to={`/project/${p.project}`} className="text-slate-600 hover:text-slate-400">
                      <ExternalLink className="w-3.5 h-3.5" />
                    </Link>
                  </td>
                </tr>
              ))}
              {projects.length === 0 && (
                <tr>
                  <td colSpan={11} className="py-12 text-center text-slate-500">
                    <FolderOpen className="w-8 h-8 mx-auto mb-2 opacity-50" />
                    <p>No hay proyectos registrados</p>
                    <p className="text-xs mt-1">Usa <code className="text-blue-400">onboard_project</code> para registrar tu primer proyecto</p>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Mobile card list */}
        <div className="md:hidden space-y-2">
          {projects.map(p => (
            <Link
              key={p.project}
              to={`/project/${p.project}`}
              className="block p-3 rounded-lg bg-slate-800/50 hover:bg-slate-800 transition-colors"
            >
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-sm font-medium text-white">{p.project}</span>
                <HealthBadge health={p.healing_health} />
              </div>
              <div className="flex items-center gap-3 text-xs text-slate-400">
                <StackBadge stack={p.stack} />
                <span>{p.sessions ?? 0} ses.</span>
                {(p.feedback_open ?? 0) > 0 && (
                  <span className="text-amber-400">{p.feedback_open} FB</span>
                )}
                <span className="ml-auto">{timeAgo(p.last_activity)}</span>
              </div>
              {p.active_feature && (
                <p className="text-xs text-slate-500 mt-1 truncate">{p.active_feature}</p>
              )}
            </Link>
          ))}
          {projects.length === 0 && (
            <div className="py-12 text-center text-slate-500">
              <FolderOpen className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p>No hay proyectos registrados</p>
            </div>
          )}
        </div>
      </div>

      {/* Bottom cards */}
      {(agg.total_feedback_open ?? 0) > 0 && (
        <div className="card border-amber-500/30">
          <div className="flex items-center gap-2">
            <MessageSquare className="w-4 h-4 text-amber-400" />
            <span className="text-sm text-amber-400 font-medium">{agg.total_feedback_open} feedback tickets abiertos</span>
          </div>
        </div>
      )}
    </div>
  )
}

function LoadingSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="h-8 bg-slate-800 rounded w-48" />
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 md:gap-4">
        {[...Array(6)].map((_, i) => <div key={i} className="h-20 md:h-24 bg-slate-800 rounded-xl" />)}
      </div>
      <div className="h-96 bg-slate-800 rounded-xl" />
    </div>
  )
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex items-center justify-center h-96">
      <div className="text-center">
        <Activity className="w-12 h-12 text-red-400 mx-auto mb-4" />
        <h2 className="text-lg font-semibold text-white mb-2">Error cargando datos</h2>
        <p className="text-sm text-slate-400">{message}</p>
      </div>
    </div>
  )
}
