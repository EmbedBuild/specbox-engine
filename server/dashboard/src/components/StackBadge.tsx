interface Props {
  stack: string
}

const stackColors: Record<string, string> = {
  flutter: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
  react: 'bg-cyan-500/15 text-cyan-400 border-cyan-500/30',
  python: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30',
  'google-apps-script': 'bg-green-500/15 text-green-400 border-green-500/30',
  gas: 'bg-green-500/15 text-green-400 border-green-500/30',
  unknown: 'bg-slate-500/15 text-slate-400 border-slate-500/30',
}

const stackLabels: Record<string, string> = {
  flutter: 'Flutter',
  react: 'React',
  python: 'Python',
  'google-apps-script': 'GAS',
  gas: 'GAS',
}

export default function StackBadge({ stack }: Props) {
  const color = stackColors[stack] || stackColors.unknown
  const label = stackLabels[stack] || stack

  return (
    <span className={`badge border ${color}`}>
      {label}
    </span>
  )
}
