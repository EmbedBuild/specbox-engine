import type { SalaData, ProjectActivity, TimelineData, HealingData, UpgradesData, E2EData, SpecDrivenData } from './types'

const BASE = '/api'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }))
    throw new Error(err.error || res.statusText)
  }
  return res.json()
}

export const api = {
  sala: (days = 7) => get<SalaData>(`/sala?days=${days}`),
  projectDetail: (name: string, days = 7) => get<ProjectActivity>(`/project/${name}?days=${days}`),
  projectTimeline: (name: string, limit = 50) => get<TimelineData>(`/project/${name}/timeline?limit=${limit}`),
  healing: () => get<HealingData>('/healing'),
  upgrades: () => get<UpgradesData>('/upgrades'),
  e2e: () => get<E2EData>('/e2e'),
  specDriven: () => get<SpecDrivenData>('/spec-driven'),
}
