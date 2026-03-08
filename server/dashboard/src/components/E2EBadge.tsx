import { TestTube2 } from 'lucide-react'

interface E2EBadgeProps {
  passing: number
  total: number
  failing: number
}

export default function E2EBadge({ passing, total, failing }: E2EBadgeProps) {
  if (total === 0) return <span className="text-slate-600 text-xs">—</span>

  const color = failing > 0
    ? 'bg-red-500/10 text-red-400 border-red-500/20'
    : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border ${color}`}>
      <TestTube2 className="w-3 h-3" />
      {passing}/{total}
    </span>
  )
}
