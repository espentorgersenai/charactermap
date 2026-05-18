export interface AdaptationInfo {
  tmdb_id: number
  title: string
  year: number | null
  rating: number | null
  poster_url: string | null
}

export interface ResolveCandidate {
  source: string
  id: string
  title: string
  year: number | null
  author: string | null
  director: string | null
  cover_url: string | null
  confidence_score: number
  adaptation: AdaptationInfo | null
}

export interface ResolveResponse {
  candidates: ResolveCandidate[]
}

const API_BASE = '/api'

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message)
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: 'Unknown error', code: 'UNKNOWN' }))
    throw new ApiError(res.status, err.code ?? 'UNKNOWN', err.error ?? 'Request failed')
  }
  return res.json()
}

export const api = {
  resolve: (query: string, workType: 'book' | 'film_tv') =>
    request<ResolveResponse>('/resolve', {
      method: 'POST',
      body: JSON.stringify({ query, work_type: workType }),
    }),
}
