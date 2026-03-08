import { type ReactNode } from 'react'

interface Props {
  label: string
  value: string | number
  icon: ReactNode
  trend?: 'up' | 'down' | 'neutral'
  color?: 'blue' | 'green' | 'amber' | 'red' | 'slate'
}

const colorMap = {
  blue: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  green: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  amber: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  red: 'bg-red-500/10 text-red-400 border-red-500/20',
  slate: 'bg-slate-500/10 text-slate-400 border-slate-500/20',
}

export default function KPICard({ label, value, icon, color = 'blue' }: Props) {
  return (
    <div className={`kpi-card border ${colorMap[color]}`}>
      <div className="flex items-center justify-between">
        <span className="text-[10px] md:text-xs font-medium uppercase tracking-wider opacity-70">{label}</span>
        <span className="opacity-50">{icon}</span>
      </div>
      <p className="text-xl md:text-2xl font-bold text-white mt-1">{value}</p>
    </div>
  )
}
