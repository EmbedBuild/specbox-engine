import { useEffect, useState, useCallback, useRef } from 'react'

const REFRESH_INTERVAL = 30_000 // 30 seconds

interface UseAutoRefreshResult<T> {
  data: T | null
  loading: boolean
  error: string
  lastUpdated: Date | null
}

export function useAutoRefresh<T>(
  fetcher: () => Promise<T>,
  deps: unknown[] = [],
  interval = REFRESH_INTERVAL,
): UseAutoRefreshResult<T> {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)
  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher

  const refresh = useCallback(() => {
    fetcherRef.current()
      .then(d => {
        setData(d)
        setLastUpdated(new Date())
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    setLoading(true)
    setError('')
    fetcherRef.current()
      .then(d => {
        setData(d)
        setLastUpdated(new Date())
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))

    const id = setInterval(refresh, interval)
    return () => clearInterval(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  return { data, loading, error, lastUpdated }
}
