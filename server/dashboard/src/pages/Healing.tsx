import { Shield } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { api } from '../api'
import type { HealingData } from '../types'
import { useAutoRefresh } from '../hooks/useAutoRefresh'
import HealthBadge from '../components/HealthBadge'

const levelLabels: Record<string, string> = {
  '1': 'L1: Auto-fix',
  '2': 'L2: Diagnose',
  '3': 'L3: Rollback',
  '4': 'L4: Escalate',
}

const levelColors: Record<string, string> = {
  '1': '#22c55e',
  '2': '#3b82f6',
  '3': '#f59e0b',
  '4': '#ef4444',
}

export default function Healing() {
  const { data, loading } = useAutoRefresh<HealingData>(() => api.healing())

  if (loading) return <div className="animate-pulse"><div className="h-8 bg-slate-800 rounded w-48 mb-4" /><div className="h-96 bg-slate-800 rounded-xl" /></div>

  const totalEvents = data?.total_events ?? data?.healing_events ?? 0
  const features = data?.features ?? []
  const noData = totalEvents === 0 && features.length === 0

  const levelData = data?.by_level
    ? Object.entries(data.by_level).map(([level, count]) => ({
        name: levelLabels[level] || `Level ${level}`,
        count: count ?? 0,
        color: levelColors[level] || '#64748b',
      }))
    : []

  return (
    <div className="space-y-4 md:space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl md:text-2xl font-bold text-white">Self-Healing</h1>
          <p className="text-xs md:text-sm text-slate-400 mt-1">Protocolo de auto-recuperacion del engine</p>
        </div>
        {data?.overall_health && <HealthBadge health={data.overall_health} size="md" />}
      </div>

      {noData ? (
        <div className="card flex flex-col items-center justify-center py-12 md:py-16">
          <Shield className="w-12 h-12 md:w-16 md:h-16 text-emerald-400/30 mb-4" />
          <h2 className="text-base md:text-lg font-semibold text-slate-300 mb-1">Sin eventos de healing</h2>
          <p className="text-xs md:text-sm text-slate-500 text-center px-4">{data?.message || 'Todas las implementaciones han sido limpias'}</p>
        </div>
      ) : (
        <>
          {/* KPIs */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4">
            <div className="card text-center">
              <p className="text-2xl md:text-3xl font-bold text-white">{totalEvents}</p>
              <p className="text-[10px] md:text-xs text-slate-500 mt-1">Total eventos</p>
            </div>
            <div className="card text-center">
              <p className="text-2xl md:text-3xl font-bold text-emerald-400">{data?.total_resolved ?? 0}</p>
              <p className="text-[10px] md:text-xs text-slate-500 mt-1">Resueltos</p>
            </div>
            <div className="card text-center">
              <p className="text-2xl md:text-3xl font-bold text-red-400">{data?.total_failed ?? 0}</p>
              <p className="text-[10px] md:text-xs text-slate-500 mt-1">Fallidos</p>
            </div>
            <div className="card text-center">
              <p className="text-2xl md:text-3xl font-bold text-blue-400">{data?.resolution_rate ?? 'N/A'}</p>
              <p className="text-[10px] md:text-xs text-slate-500 mt-1">Resolution rate</p>
            </div>
          </div>

          {/* Chart */}
          {levelData.length > 0 && (
            <div className="card">
              <h3 className="text-sm font-semibold text-slate-300 mb-4">Distribucion por nivel</h3>
              <div className="h-[200px] md:h-[250px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={levelData}>
                    <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 11 }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fill: '#94a3b8', fontSize: 12 }} axisLine={false} tickLine={false} />
                    <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px', color: '#e2e8f0' }} />
                    <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                      {levelData.map((entry, i) => (
                        <Cell key={i} fill={entry.color} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Features */}
          {features.length > 0 && (
            <div className="card">
              <h3 className="text-sm font-semibold text-slate-300 mb-4">Features con healing</h3>

              {/* Desktop table */}
              <div className="hidden md:block">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-xs text-slate-500 uppercase tracking-wider border-b border-slate-800">
                      <th className="text-left py-2 px-3 font-medium">Feature</th>
                      <th className="text-center py-2 px-3 font-medium">Eventos</th>
                      <th className="text-center py-2 px-3 font-medium">Resueltos</th>
                      <th className="text-center py-2 px-3 font-medium">Fallidos</th>
                      <th className="text-center py-2 px-3 font-medium">Max Level</th>
                    </tr>
                  </thead>
                  <tbody>
                    {features.map(f => (
                      <tr key={f.feature} className="table-row">
                        <td className="py-2.5 px-3 text-white font-medium">{f.feature}</td>
                        <td className="py-2.5 px-3 text-center text-slate-300">{f.events ?? 0}</td>
                        <td className="py-2.5 px-3 text-center text-emerald-400">{f.resolved ?? 0}</td>
                        <td className="py-2.5 px-3 text-center">
                          {(f.failed ?? 0) > 0 ? <span className="text-red-400 font-medium">{f.failed}</span> : <span className="text-slate-600">0</span>}
                        </td>
                        <td className="py-2.5 px-3 text-center">
                          <span className="badge bg-slate-700 text-slate-300">L{f.max_level ?? '?'}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Mobile card list */}
              <div className="md:hidden space-y-2">
                {features.map(f => (
                  <div key={f.feature} className="p-3 rounded-lg bg-slate-800/50">
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-sm font-medium text-white truncate">{f.feature}</span>
                      <span className="badge bg-slate-700 text-slate-300 flex-shrink-0 ml-2">L{f.max_level ?? '?'}</span>
                    </div>
                    <div className="flex items-center gap-4 text-xs">
                      <span className="text-slate-400">{f.events ?? 0} eventos</span>
                      <span className="text-emerald-400">{f.resolved ?? 0} OK</span>
                      {(f.failed ?? 0) > 0 && <span className="text-red-400">{f.failed} fail</span>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
