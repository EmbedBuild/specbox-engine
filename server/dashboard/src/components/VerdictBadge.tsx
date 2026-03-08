interface Props {
  verdict: string
}

const verdictConfig: Record<string, string> = {
  ACCEPTED: 'bg-emerald-500/10 text-emerald-400',
  CONDITIONAL: 'bg-amber-500/10 text-amber-400',
  REJECTED: 'bg-red-500/10 text-red-400',
  INVALIDATED: 'bg-purple-500/10 text-purple-400',
}

export default function VerdictBadge({ verdict }: Props) {
  if (!verdict) return <span className="text-slate-600 text-xs">-</span>

  const color = verdictConfig[verdict] || 'bg-slate-500/10 text-slate-400'
  return <span className={`badge ${color}`}>{verdict}</span>
}
