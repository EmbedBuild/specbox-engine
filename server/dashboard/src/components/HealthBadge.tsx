interface Props {
  health: 'healthy' | 'degraded' | 'critical' | string
  size?: 'sm' | 'md'
}

const config: Record<string, { bg: string; dot: string; label: string }> = {
  healthy: { bg: 'bg-emerald-500/10 text-emerald-400', dot: 'bg-emerald-400', label: 'Healthy' },
  degraded: { bg: 'bg-amber-500/10 text-amber-400', dot: 'bg-amber-400', label: 'Degraded' },
  critical: { bg: 'bg-red-500/10 text-red-400', dot: 'bg-red-400', label: 'Critical' },
  unhealthy: { bg: 'bg-red-500/10 text-red-400', dot: 'bg-red-400', label: 'Unhealthy' },
}

export default function HealthBadge({ health, size = 'sm' }: Props) {
  const c = config[health] || config.healthy
  const sizeClasses = size === 'md' ? 'px-3 py-1 text-sm' : 'px-2 py-0.5 text-xs'

  return (
    <span className={`badge ${c.bg} ${sizeClasses}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${c.dot} mr-1.5`} />
      {c.label}
    </span>
  )
}
