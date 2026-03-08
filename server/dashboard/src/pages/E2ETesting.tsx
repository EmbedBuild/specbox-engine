import { TestTube2, CheckCircle, XCircle, FolderOpen } from 'lucide-react'
import { api } from '../api'
import type { E2EData } from '../types'
import { useAutoRefresh } from '../hooks/useAutoRefresh'
import KPICard from '../components/KPICard'
import { timeAgo } from '../utils'

export default function E2ETesting() {
  const { data, loading, error } = useAutoRefresh<E2EData>(() => api.e2e())

  if (loading) return <LoadingSkeleton />
  if (error) return <ErrorState message={error} />
  if (!data) return null

  return (
    <div className="space-y-4 md:space-y-6">
      <div>
        <h1 className="text-xl md:text-2xl font-bold text-white">E2E Testing</h1>
        <p className="text-xs md:text-sm text-slate-400 mt-1">
          Estado de tests Playwright en todos los proyectos
        </p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4">
        <KPICard
          label="Proyectos con E2E"
          value={data.total_projects_with_e2e}
          icon={<FolderOpen className="w-4 h-4 md:w-5 md:h-5" />}
          color="blue"
        />
        <KPICard
          label="Tests Totales"
          value={data.total_tests}
          icon={<TestTube2 className="w-4 h-4 md:w-5 md:h-5" />}
          color="slate"
        />
        <KPICard
          label="Pass Rate Global"
          value={data.global_pass_rate != null ? `${data.global_pass_rate}%` : '—'}
          icon={<CheckCircle className="w-4 h-4 md:w-5 md:h-5" />}
          color={
            data.global_pass_rate == null ? 'slate'
            : data.global_pass_rate >= 95 ? 'green'
            : data.global_pass_rate >= 80 ? 'amber'
            : 'red'
          }
        />
        <KPICard
          label="Failing"
          value={data.total_failing}
          icon={<XCircle className="w-4 h-4 md:w-5 md:h-5" />}
          color={data.total_failing > 0 ? 'red' : 'green'}
        />
      </div>

      {/* Projects Table */}
      <div className="card overflow-hidden">
        <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-4">
          Por Proyecto
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-slate-500 uppercase tracking-wider border-b border-slate-800">
                <th className="text-left py-3 px-3 font-medium">Proyecto</th>
                <th className="text-center py-3 px-3 font-medium">Tests</th>
                <th className="text-center py-3 px-3 font-medium">Passing</th>
                <th className="text-center py-3 px-3 font-medium">Failing</th>
                <th className="text-center py-3 px-3 font-medium">Pass Rate</th>
                <th className="text-center py-3 px-3 font-medium hidden md:table-cell">Viewports</th>
                <th className="text-center py-3 px-3 font-medium hidden md:table-cell">Runs</th>
                <th className="text-center py-3 px-3 font-medium">Trend</th>
                <th className="text-left py-3 px-3 font-medium hidden lg:table-cell">Ultimo run</th>
              </tr>
            </thead>
            <tbody>
              {data.projects.map(p => (
                <tr key={p.project} className="table-row">
                  <td className="py-3 px-3 text-white font-medium">{p.project}</td>
                  <td className="py-3 px-3 text-center text-slate-300">{p.total}</td>
                  <td className="py-3 px-3 text-center text-emerald-400">{p.passing}</td>
                  <td className="py-3 px-3 text-center">
                    <span className={p.failing > 0 ? 'text-red-400 font-medium' : 'text-slate-600'}>
                      {p.failing}
                    </span>
                  </td>
                  <td className="py-3 px-3 text-center">
                    <span className={
                      p.pass_rate >= 95 ? 'text-emerald-400'
                      : p.pass_rate >= 80 ? 'text-amber-400'
                      : 'text-red-400'
                    }>
                      {p.pass_rate}%
                    </span>
                  </td>
                  <td className="py-3 px-3 text-center text-slate-400 text-xs hidden md:table-cell">
                    {p.viewports.join(', ')}
                  </td>
                  <td className="py-3 px-3 text-center text-slate-300 hidden md:table-cell">{p.runs}</td>
                  <td className="py-3 px-3 text-center">
                    {p.trend === 'improving' && <span className="text-emerald-400">↑</span>}
                    {p.trend === 'degrading' && <span className="text-red-400">↓</span>}
                    {p.trend === 'stable' && <span className="text-slate-500">—</span>}
                    {p.trend === 'insufficient_data' && <span className="text-slate-600">·</span>}
                  </td>
                  <td className="py-3 px-3 text-slate-400 text-xs hidden lg:table-cell">
                    {timeAgo(p.last_run)}
                  </td>
                </tr>
              ))}
              {data.projects.length === 0 && (
                <tr>
                  <td colSpan={9} className="py-12 text-center text-slate-500">
                    <TestTube2 className="w-8 h-8 mx-auto mb-2 opacity-50" />
                    <p>Ningun proyecto ha reportado E2E tests</p>
                    <p className="text-xs mt-1">
                      Configura <code className="text-teal-400">hooks/e2e-report.sh</code> para empezar
                    </p>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function LoadingSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="h-8 bg-slate-800 rounded w-48" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4">
        {[...Array(4)].map((_, i) => <div key={i} className="h-20 md:h-24 bg-slate-800 rounded-xl" />)}
      </div>
      <div className="h-96 bg-slate-800 rounded-xl" />
    </div>
  )
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex items-center justify-center h-96">
      <div className="text-center">
        <TestTube2 className="w-12 h-12 text-red-400 mx-auto mb-4" />
        <h2 className="text-lg font-semibold text-white mb-2">Error cargando datos</h2>
        <p className="text-sm text-slate-400">{message}</p>
      </div>
    </div>
  )
}
