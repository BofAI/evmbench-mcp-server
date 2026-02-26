import { useCallback, useEffect, useState } from "react"
import { fetchDailyLimit, type DailyLimit } from "@/lib/limits"

const DAILY_LIMIT_TTL_MS = 15000
const DAILY_LIMIT_POLL_MS = 60_000

let dailyLimitCache: { value: DailyLimit; timestamp: number } | null = null
let dailyLimitInFlight: Promise<DailyLimit> | null = null

export function invalidateDailyLimitCache(): void {
  dailyLimitCache = null
}

async function getDailyLimit(): Promise<DailyLimit> {
  const now = Date.now()

  if (dailyLimitCache && now - dailyLimitCache.timestamp < DAILY_LIMIT_TTL_MS) {
    return dailyLimitCache.value
  }

  if (dailyLimitInFlight) {
    return dailyLimitInFlight
  }

  dailyLimitInFlight = fetchDailyLimit()
    .then((limit) => {
      dailyLimitCache = { value: limit, timestamp: Date.now() }
      return limit
    })
    .catch((error) => {
      dailyLimitInFlight = null
      throw error
    })
    .finally(() => {
      dailyLimitInFlight = null
    })

  return dailyLimitInFlight
}

export function useDailyLimit() {
  const [data, setData] = useState<DailyLimit | null>(
    dailyLimitCache ? dailyLimitCache.value : null,
  )
  const [isLoading, setIsLoading] = useState(!dailyLimitCache)
  const [error, setError] = useState<Error | null>(null)

  const refetch = useCallback(async () => {
    invalidateDailyLimitCache()
    setIsLoading(true)
    setError(null)
    try {
      const limit = await fetchDailyLimit()
      setData(limit)
    } catch (err) {
      setError(err instanceof Error ? err : new Error("Failed to load limit"))
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    let isMounted = true

    const load = async () => {
      try {
        const limit = await getDailyLimit()
        if (!isMounted) return
        setData(limit)
        setError(null)
      } catch (err) {
        if (!isMounted) return
        setError(err instanceof Error ? err : new Error("Failed to load limit"))
      } finally {
        if (isMounted) {
          setIsLoading(false)
        }
      }
    }

    if (!dailyLimitCache) {
      void load()
    } else {
      setIsLoading(false)
    }

    return () => {
      isMounted = false
    }
  }, [])

  useEffect(() => {
    const interval = setInterval(() => {
      void refetch()
    }, DAILY_LIMIT_POLL_MS)
    return () => clearInterval(interval)
  }, [refetch])

  return { data, isLoading, error, refetch }
}

