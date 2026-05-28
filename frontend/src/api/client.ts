export interface AdaptationInfo {
  tmdb_id: number
  title: string
  year: number | null
  rating: number | null
  poster_url: string | null
  media_type?: 'movie' | 'tv' | null
}

export interface SeasonInfo {
  number: number
  name: string
  year: number | null
  episode_count: number | null
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
  media_type?: 'movie' | 'tv' | null
  seasons?: SeasonInfo[] | null
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

export type JobProgressStage =
  | 'searching'
  | 'structuring'
  | 'generating'
  | 'enriching'
  | 'rendering'
  | null

export interface JobStatus {
  job_id: string
  status: 'queued' | 'generating' | 'done' | 'refused' | 'failed'
  progress_stage?: JobProgressStage
  character_map?: Record<string, unknown> | null
  error_code?: string | null
  error_message?: string | null
}

export async function createJob(body: {
  title_query: string
  resolved: ResolveCandidate
  model: string
  formats: string[]
  email?: string
  acknowledged_spoilers: true
  turnstile_token?: string
  character_cap: 10 | 20 | 30 | 40 | 50 | 100 | 150
  season?: number | null
}): Promise<{ job_id: string }> {
  const res = await fetch('/api/jobs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: { code: 'JOB_CREATE_FAILED' } }))
    throw new Error(err?.detail?.code ?? err?.detail ?? 'JOB_CREATE_FAILED')
  }
  return res.json()
}

export async function getJob(jobId: string): Promise<JobStatus> {
  const res = await fetch(`/api/jobs/${jobId}`)
  if (!res.ok) throw new Error('JOB_FETCH_FAILED')
  return res.json()
}

export interface ArtifactInfo {
  format: string
  url: string
}

export async function uploadArtifact(
  jobId: string,
  format: string,
  blob: Blob,
): Promise<void> {
  const form = new FormData()
  form.append('file', blob, `character-map.${format}`)
  const res = await fetch(`/api/jobs/${jobId}/artifacts?format=${format}`, {
    method: 'POST',
    body: form,
  })
  if (!res.ok) {
    console.warn('Artifact upload failed', format, res.status)
  }
}

export async function getArtifacts(jobId: string): Promise<ArtifactInfo[]> {
  const res = await fetch(`/api/jobs/${jobId}/artifacts`)
  if (!res.ok) return []
  return res.json()
}

export interface Limits {
  jobs: { per_minute: number; per_hour: number; per_day: number }
  resolve: { per_minute: number; per_day: number }
  cost: { limit_usd: number; spent_usd: number; remaining_usd: number }
}

export async function getLimits(): Promise<Limits | null> {
  try {
    const res = await fetch('/api/limits')
    if (!res.ok) return null
    return res.json()
  } catch {
    return null
  }
}

export async function trackEvent(
  eventType: string,
  properties: Record<string, unknown> = {},
  jobId?: string,
): Promise<void> {
  try {
    await fetch('/api/analytics', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ event_type: eventType, properties, job_id: jobId }),
      keepalive: true,
    })
  } catch {
    // Analytics never blocks the UI.
  }
}
