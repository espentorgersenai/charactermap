import { useEffect, useState, useCallback } from 'react'
import { getLimits, type Limits } from '../api/client'

export function useLimits() {
  const [limits, setLimits] = useState<Limits | null>(null)

  const refresh = useCallback(async () => {
    setLimits(await getLimits())
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  return { limits, refresh }
}
