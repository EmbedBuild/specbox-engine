import { ArrowUpCircle, Check, AlertTriangle, Package } from 'lucide-react'
import { api } from '../api'
import type { UpgradesData } from '../types'
import { useAutoRefresh } from '../hooks/useAutoRefresh'
import StackBadge from '../components/StackBadge'
import { timeAgo } from '../utils'

export default function Upgrades() {
  const { data, loading } = useAutoRefresh<UpgradesData>(() => api.upgrades())

  if (loading) return <div className="animate-pulse"><div className="h-8 bg-slate-800 rounded w-48 mb-4" /><div className="h-96 bg-slate-800 rounded-xl" /></div>
  if (!data) return <p className="text-red-400">Error cargando datos</p>

  const projects = data.projects ?? []

  return (
    <div className="space-y-4 md:space-y-6">
      <div>
        <h1 className="text-xl md:text-2xl font-bold text-white">Version Matrix</h1>
        <p className="text-xs md:text-sm text-slate-400 mt-1">Estado de actualizacion de proyectos</p>
      </div>

      {/* Version info */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4">
        <div className="card">
          <p className="text-[10px] md:text-xs text-slate-500 mb-1">Engine Version</p>
          <p className="text-base md:text-lg font-bold font-mono text-blue-400">{data.current_engine_version ?? '?'}</p>
        </div>
        <div className="card">
          <p className="text-[10px] md:text-xs text-slate-500 mb-1">MCP Version</p>
          <p className="text-base md:text-lg font-bold font-mono text-blue-400">{data.current_mcp_version ?? '?'}</p>
        </div>
        <div className="card">
          <div className="flex items-center gap-2">
            <Check className="w-4 h-4 text-emerald-400" />
            <p className="text-[10px] md:text-xs text-slate-500">Actualizados</p>
          </div>
          <p className="text-xl md:text-2xl font-bold text-emerald-400 mt-1">{data.up_to_date ?? 0}</p>
        </div>
        <div className="card">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            <p className="text-[10px] md:text-xs text-slate-500">Pendientes</p>
          </div>
          <p className="text-xl md:text-2xl font-bold text-amber-400 mt-1">{data.needs_upgrade ?? 0}</p>
        </div>
      </div>

      {/* Desktop Table */}
      <div className="card overflow-hidden hidden md:block">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-slate-500 uppercase tracking-wider border-b border-slate-800">
              <th className="text-left py-3 px-3 font-medium">Proyecto</th>
              <th className="text-left py-3 px-3 font-medium">Stack</th>
              <th className="text-center py-3 px-3 font-medium">Engine</th>
              <th className="text-center py-3 px-3 font-medium">MCP</th>
              <th className="text-center py-3 px-3 font-medium hidden lg:table-cell">Ultimo upgrade</th>
              <th className="text-center py-3 px-3 font-medium">Estado</th>
            </tr>
          </thead>
          <tbody>
            {projects.map(p => (
              <tr key={p.project} className="table-row">
                <td className="py-3 px-3 text-white font-medium">{p.project}</td>
                <td className="py-3 px-3"><StackBadge stack={p.stack} /></td>
                <td className="py-3 px-3 text-center">
                  <span className={`font-mono text-xs ${p.engine_version === data.current_engine_version ? 'text-slate-400' : 'text-amber-400'}`}>
                    {p.engine_version ?? '?'}
                  </span>
                </td>
                <td className="py-3 px-3 text-center">
                  <span className={`font-mono text-xs ${p.mcp_version === data.current_mcp_version ? 'text-slate-400' : 'text-amber-400'}`}>
                    {p.mcp_version ?? '?'}
                  </span>
                </td>
                <td className="py-3 px-3 text-center text-xs text-slate-400 hidden lg:table-cell">
                  {p.last_upgraded_at === 'never' ? 'Nunca' : timeAgo(p.last_upgraded_at)}
                </td>
                <td className="py-3 px-3 text-center">
                  {p.needs_upgrade ? (
                    <span className="badge bg-amber-500/10 text-amber-400 border border-amber-500/20">
                      <ArrowUpCircle className="w-3 h-3 mr-1" /> Upgrade
                    </span>
                  ) : (
                    <span className="badge bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      <Check className="w-3 h-3 mr-1" /> OK
                    </span>
                  )}
                </td>
              </tr>
            ))}
            {projects.length === 0 && (
              <tr>
                <td colSpan={6} className="py-12 text-center text-slate-500">
                  <Package className="w-8 h-8 mx-auto mb-2 opacity-50" />
                  <p>No hay proyectos registrados</p>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Mobile card list */}
      <div className="md:hidden space-y-2">
        {projects.map(p => (
          <div key={p.project} className="card">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-white">{p.project}</span>
              {p.needs_upgrade ? (
                <span className="badge bg-amber-500/10 text-amber-400 border border-amber-500/20 text-xs">
                  <ArrowUpCircle className="w-3 h-3 mr-1" /> Upgrade
                </span>
              ) : (
                <span className="badge bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-xs">
                  <Check className="w-3 h-3 mr-1" /> OK
                </span>
              )}
            </div>
            <div className="flex items-center gap-3 text-xs text-slate-400">
              <StackBadge stack={p.stack} />
              <span className="font-mono">{p.engine_version ?? '?'}</span>
              <span className="ml-auto">{p.last_upgraded_at === 'never' ? 'Nunca' : timeAgo(p.last_upgraded_at)}</span>
            </div>
          </div>
        ))}
        {projects.length === 0 && (
          <div className="card py-12 text-center text-slate-500">
            <Package className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p>No hay proyectos registrados</p>
          </div>
        )}
      </div>
    </div>
  )
}
