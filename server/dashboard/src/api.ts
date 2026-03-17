import type { SalaData, ProjectActivity, TimelineData, HealingData, UpgradesData, E2EData, SpecDrivenData } from './types'

const BASE = '/api'

// Read token from URL ?token=xxx and persist in sessionStorage
function getToken(): string | null {
  const urlToken = new URLSearchParams(window.location.search).get('token')
  if (urlToken) {
    sessionStorage.setItem('specbox_token', urlToken)
    // Clean token from URL to avoid leaking in history/bookmarks
    const url = new URL(window.location.href)
    url.searchParams.delete('token')
    window.history.replaceState({}, '', url.toString())
    return urlToken
  }
  return sessionStorage.getItem('specbox_token')
}

const TOKEN = getToken()

async function get<T>(path: string): Promise<T> {
  const headers: HeadersInit = {}
  if (TOKEN) {
    headers['Authorization'] = `Bearer ${TOKEN}`
  }
  const res = await fetch(`${BASE}${path}`, { headers })
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
