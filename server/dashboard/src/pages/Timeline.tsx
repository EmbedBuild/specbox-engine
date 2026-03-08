import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, Filter } from 'lucide-react'
import { api } from '../api'
import type { TimelineData } from '../types'
import { useAutoRefresh } from '../hooks/useAutoRefresh'
import TimelineEventCard from '../components/TimelineEvent'

const eventTypes = [
  { key: 'session', label: 'Sesiones' },
  { key: 'checkpoint', label: 'Checkpoints' },
  { key: 'healing', label: 'Healing' },
  { key: 'acceptance_test', label: 'Tests' },
  { key: 'acceptance_validation', label: 'Validaciones' },
  { key: 'merge', label: 'Merges' },
  { key: 'feedback', label: 'Feedback' },
  { key: 'feedback_resolution', label: 'FB Resueltos' },
]

export default function Timeline() {
  const { name } = useParams<{ name: string }>()
  const { data, loading, error } = useAutoRefresh<TimelineData>(
    () => api.projectTimeline(name!, 100),
    [name],
  )
  const [filters, setFilters] = useState<Set<string>>(new Set())

  const toggleFilter = (type: string) => {
    setFilters(prev => {
      const next = new Set(prev)
      if (next.has(type)) next.delete(type)
      else next.add(type)
      return next
    })
  }

  if (loading) return <div className="animate-pulse"><div className="h-8 bg-slate-800 rounded w-64 mb-4" /><div className="h-96 bg-slate-800 rounded-xl" /></div>
  if (error) return <p className="text-red-400">{error}</p>
  if (!data) return null

  const timeline = data.timeline ?? []
  const filtered = filters.size === 0
    ? timeline
    : timeline.filter(e => filters.has(e.event_type))

  return (
    <div className="space-y-4 md:space-y-6">
      <div className="flex items-center gap-3 md:gap-4">
        <Link to={`/project/${name}`} className="p-2 rounded-lg hover:bg-slate-800 transition-colors">
          <ArrowLeft className="w-5 h-5 text-slate-400" />
        </Link>
        <div>
          <h1 className="text-xl md:text-2xl font-bold text-white">Timeline</h1>
          <p className="text-xs md:text-sm text-slate-400">{name} &middot; {data.total_events ?? 0} eventos totales</p>
        </div>
      </div>

      {/* Filters */}
      <div className="card">
        <div className="flex items-center gap-2 mb-3">
          <Filter className="w-4 h-4 text-slate-400" />
          <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">Filtrar por tipo</span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {eventTypes.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => toggleFilter(key)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                filters.has(key)
                  ? 'bg-blue-600/20 text-blue-400 border border-blue-500/30'
                  : filters.size === 0
                    ? 'bg-slate-800 text-slate-300 border border-slate-700'
                    : 'bg-slate-800/50 text-slate-500 border border-slate-800'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
        {filters.size > 0 && (
          <button
            onClick={() => setFilters(new Set())}
            className="mt-2 px-3 py-1.5 rounded-lg text-xs font-medium text-slate-500 hover:text-slate-300 transition-colors"
          >
            Limpiar filtros
          </button>
        )}
      </div>

      {/* Events */}
      <div className="card divide-y divide-slate-800/50">
        {filtered.length === 0 ? (
          <p className="text-center text-slate-500 py-12">No hay eventos con los filtros seleccionados</p>
        ) : (
          filtered.map((event, i) => (
            <TimelineEventCard key={`${event.timestamp}-${i}`} event={event} />
          ))
        )}
      </div>

      {filtered.length < (data.total_events ?? 0) && (
        <p className="text-center text-xs text-slate-500">
          Mostrando {filtered.length} de {data.total_events} eventos
        </p>
      )}
    </div>
  )
}
