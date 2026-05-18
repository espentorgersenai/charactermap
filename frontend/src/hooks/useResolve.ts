import { useState } from 'react'
import { api, ResolveCandidate } from '../api/client'

export function useResolve() {
  const [candidates, setCandidates] = useState<ResolveCandidate[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function resolve(query: string, workType: 'book' | 'film_tv') {
    setIsLoading(true)
    setError(null)
    try {
      const res = await api.resolve(query, workType)
      setCandidates(res.candidates)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Resolve failed')
      setCandidates([])
    } finally {
      setIsLoading(false)
    }
  }

  function reset() {
    setCandidates([])
    setError(null)
  }

  return { resolve, candidates, isLoading, error, reset }
}
