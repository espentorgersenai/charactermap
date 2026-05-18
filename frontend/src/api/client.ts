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

export interface JobStatus {
  job_id: string
  status: 'queued' | 'generating' | 'done' | 'refused' | 'failed'
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
