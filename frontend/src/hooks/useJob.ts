import { useEffect, useRef, useState } from 'react'
import { getJob, JobStatus } from '../api/client'

const MODEL_ETAS: Record<string, string> = {
  'claude-sonnet-4-6': 'Typically 30–45s',
  'claude-opus-4-7': 'Typically 60–90s',
  'claude-haiku-4-5-20251001': 'Typically 15–25s',
  'gpt-5.5': 'Typically 30–60s',
  'gemini-2.5-pro': 'Typically 30–60s',
}

export function getModelEta(model: string): string {
  return MODEL_ETAS[model] ?? 'Typically 30–60s'
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
        setJob((prev) => prev ? { ...prev, status: data.status } : { job_id: jobId, status: data.status })
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
