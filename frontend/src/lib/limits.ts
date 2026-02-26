import { API_BASE } from "@/lib/api"

export interface DailyLimit {
  date_utc: string
  capacity: number
  used: number
  remaining: number
  reset_at: string
}

export async function fetchDailyLimit(
  signal?: AbortSignal,
): Promise<DailyLimit> {
  const response = await fetch(`${API_BASE}/v1/jobs/daily-limit`, {
    signal,
    cache: "no-store",
    credentials: "include",
  })

  if (!response.ok) {
    throw new Error(`Failed to load daily limit (${response.status})`)
  }

  return response.json()
}

