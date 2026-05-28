import { useEffect, useRef, useState } from 'react'
import { getJob, JobProgressStage, JobStatus } from '../api/client'

// Time estimates as of Session 9 (grounded pipeline). Anthropic models now
// run the two-stage web_search path; OpenAI/Gemini still use legacy single-call.
const MODEL_ETAS: Record<string, string> = {
  'claude-sonnet-4-6': 'Typically 90–180s (web-grounded)',
  'claude-opus-4-8':   'Typically 120–240s (web-grounded)',
  'gpt-5.5':           'Typically 30–60s',
  'gemini-2.5-pro':    'Typically 30–60s',
}

export function getModelEta(model: string): string {
  return MODEL_ETAS[model] ?? 'Typically 30–60s'
}

// User-facing copy for each backend stage code. Kept here so the backend
// stays language-neutral and we can iterate UX text without redeploying
// the worker.
const STAGE_LABELS: Record<NonNullable<JobProgressStage>, string> = {
  searching:   'Searching the web for character details…',
  structuring: 'Building the character map…',
  generating:  'Generating the character map…',
  enriching:   'Looking up cast and adaptations…',
  rendering:   'Rendering Markdown and PDF…',
}

export function getStageLabel(stage: JobProgressStage, status: string): string {
  if (stage && STAGE_LABELS[stage]) return STAGE_LABELS[stage]
  if (status === 'queued') return 'Queued…'
  if (status === 'generating') return 'Generating the character map…'
  return 'Working…'
}

export function useJob(jobId: string | undefined) {
  const [job, setJob] = useState<JobStatus | null>(null)
  const [progress, setProgress] = useState(0.05)
  const esRef = useRef<EventSource | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (!jobId) return

    let cancelled = false

    function startPolling() {
      pollRef.current = setInterval(async () => {
        try {
          const j = await getJob(jobId!)
          if (!cancelled) setJob(j)
          if (j.status === 'done' || j.status === 'refused' || j.status === 'failed') {
            clearInterval(pollRef.current!)
          }
        } catch {/* ignore transient errors */}
      }, 2000)
    }

    const es = new EventSource(`/api/jobs/${jobId}/stream`)
    esRef.current = es

    es.addEventListener('status', (e) => {
      const data = JSON.parse((e as MessageEvent).data)
      if (!cancelled) {
        setProgress(data.progress ?? 0.4)
        setJob((prev) => {
          const base = prev ?? { job_id: jobId, status: data.status }
          return { ...base, status: data.status, progress_stage: data.stage ?? null }
        })
      }
    })

    es.addEventListener('done', () => {
      if (!cancelled) setProgress(1)
      getJob(jobId).then((j) => { if (!cancelled) setJob(j) })
      es.close()
    })

    es.addEventListener('error', (e) => {
      const raw = (e as MessageEvent).data
      const data = raw ? JSON.parse(raw) : {}
      if (!cancelled) {
        setJob((prev) => prev
          ? { ...prev, status: 'failed', error_code: data.error, error_message: data.message }
          : { job_id: jobId, status: 'failed', error_code: data.error, error_message: data.message }
        )
      }
      es.close()
    })

    es.onerror = () => {
      es.close()
      if (!cancelled) startPolling()
    }

    return () => {
      cancelled = true
      es.close()
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [jobId])

  return { job, progress }
}
