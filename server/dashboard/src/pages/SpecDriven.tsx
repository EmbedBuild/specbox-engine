import { ClipboardList, FolderOpen, Activity, FileText, GitBranch, CheckSquare } from 'lucide-react'
import { api } from '../api'
import type { SpecDrivenData } from '../types'
import { useAutoRefresh } from '../hooks/useAutoRefresh'
import KPICard from '../components/KPICard'
import StackBadge from '../components/StackBadge'
import { timeAgo } from '../utils'

export default function SpecDriven() {
  const { data, loading, error } = useAutoRefresh<SpecDrivenData>(() => api.specDriven())

  if (loading) return <LoadingSkeleton />
  if (error) return <ErrorState message={error} />
  if (!data) return null

  const projects = data.projects ?? []

  return (
    <div className="space-y-4 md:space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl md:text-2xl font-bold text-white">Spec-Driven</h1>
        <p className="text-xs md:text-sm text-slate-400 mt-1">
          Proyectos con board Trello configurado &middot; US / UC / AC
        </p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 md:gap-4">
        <KPICard label="Proyectos" value={data.total_projects} icon={<FolderOpen className="w-4 h-4 md:w-5 md:h-5" />} color="blue" />
        <KPICard label="User Stories" value={data.total_us} icon={<FileText className="w-4 h-4 md:w-5 md:h-5" />} color="slate" />
        <KPICard label="Use Cases" value={data.total_uc} icon={<GitBranch className="w-4 h-4 md:w-5 md:h-5" />} color="slate" />
        <KPICard label="Acceptance Criteria" value={data.total_ac} icon={<CheckSquare className="w-4 h-4 md:w-5 md:h-5" />} color="slate" />
        <KPICard
          label="Progreso Medio"
          value={`${data.avg_progress}%`}
          icon={<Activity className="w-4 h-4 md:w-5 md:h-5" />}
          color={data.avg_progress >= 80 ? 'green' : data.avg_progress >= 40 ? 'amber' : 'red'}
        />
      </div>

      {/* Projects Table */}
      <div className="card overflow-hidden">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">Proyectos con Board</h2>
          <span className="text-xs text-slate-500">{projects.length} configurados</span>
        </div>

        {/* Desktop table */}
        <div className="overflow-x-auto hidden md:block">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-slate-500 uppercase tracking-wider border-b border-slate-800">
                <th className="text-left py-3 px-3 font-medium">Proyecto</th>
                <th className="text-left py-3 px-3 font-medium">Stack</th>
                <th className="text-center py-3 px-3 font-medium">US</th>
                <th className="text-center py-3 px-3 font-medium">UC</th>
                <th className="text-center py-3 px-3 font-medium">AC</th>
                <th className="text-center py-3 px-3 font-medium">Progreso</th>
                <th className="text-left py-3 px-3 font-medium">Ultimo Sync</th>
              </tr>
            </thead>
            <tbody>
              {projects.map(p => (
                <tr key={p.project} className="table-row">
                  <td className="py-3 px-3">
                    <span className="text-white font-medium">{p.project}</span>
                    <p className="text-xs text-slate-500 mt-0.5 truncate max-w-48">{p.board_id}</p>
                  </td>
                  <td className="py-3 px-3"><StackBadge stack={p.stack} /></td>
                  <td className="py-3 px-3 text-center text-slate-300">{p.us_count}</td>
                  <td className="py-3 px-3 text-center text-slate-300">{p.uc_count}</td>
                  <td className="py-3 px-3 text-center text-slate-300">{p.ac_count}</td>
                  <td className="py-3 px-3 text-center">
                    <ProgressBar value={p.progress} />
                  </td>
                  <td className="py-3 px-3 text-slate-400 text-xs">{timeAgo(p.last_sync)}</td>
                </tr>
              ))}
              {projects.length === 0 && (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-500">
                    <ClipboardList className="w-8 h-8 mx-auto mb-2 opacity-50" />
                    <p>No hay proyectos con board Trello configurado</p>
                    <p className="text-xs mt-1">Configura <code className="text-blue-400">boardId</code> en la metadata del proyecto</p>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Mobile card list */}
        <div className="md:hidden space-y-2">
          {projects.map(p => (
            <div
              key={p.project}
              className="block p-3 rounded-lg bg-slate-800/50"
            >
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-sm font-medium text-white">{p.project}</span>
                <StackBadge stack={p.stack} />
              </div>
              <div className="flex items-center gap-3 text-xs text-slate-400 mb-2">
                <span>{p.us_count} US</span>
                <span>{p.uc_count} UC</span>
                <span>{p.ac_count} AC</span>
                <span className="ml-auto">{timeAgo(p.last_sync)}</span>
              </div>
              <ProgressBar value={p.progress} />
            </div>
          ))}
          {projects.length === 0 && (
            <div className="py-12 text-center text-slate-500">
              <ClipboardList className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p>No hay proyectos con board configurado</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function ProgressBar({ value }: { value: number }) {
  const color = value >= 80 ? 'bg-emerald-500' : value >= 40 ? 'bg-amber-500' : 'bg-red-500'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-slate-700 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${Math.min(value, 100)}%` }} />
      </div>
      <span className="text-xs text-slate-400 w-8 text-right">{value}%</span>
    </div>
  )
}

function LoadingSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="h-8 bg-slate-800 rounded w-48" />
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 md:gap-4">
        {[...Array(5)].map((_, i) => <div key={i} className="h-20 md:h-24 bg-slate-800 rounded-xl" />)}
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
