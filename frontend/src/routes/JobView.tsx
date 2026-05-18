import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useJob, getModelEta } from '../hooks/useJob'
import { CharacterMapCanvas } from '../components/CharacterMapCanvas'
import { DownloadList } from '../components/DownloadList'
import type { CharacterMap } from '../types/characterMap'

export default function JobView() {
  const { id } = useParams<{ id: string }>()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const model = searchParams.get('model') ?? 'claude-sonnet-4-6'
  const title = searchParams.get('title') ?? ''

  const { job, progress } = useJob(id)

  const [elapsed, setElapsed] = useState(0)
  useEffect(() => {
    const t = setInterval(() => setElapsed((s) => s + 1), 1000)
    return () => clearInterval(t)
  }, [])

  const eta = getModelEta(model)

  // ── Done ─────────────────────────────────────────────────────────────────
  if (job?.status === 'done' && job.character_map) {
    const charMap = job.character_map as unknown as CharacterMap
    return (
      <div className="flex h-screen overflow-hidden">
        {/* Canvas fills the viewport */}
        <div className="flex-1 min-w-0">
          <CharacterMapCanvas charMap={charMap} jobId={id!} />
        </div>

        {/* Right sidebar: downloads */}
        <div className="w-[190px] flex-shrink-0 bg-[#161616] border-l border-[#222] p-4 overflow-y-auto">
          <div className="mb-4">
            <p className="text-[11px] font-bold text-[#555] uppercase tracking-[0.06em] mb-2.5">
              Downloads
            </p>
            <DownloadList jobId={id!} />
          </div>
        </div>
      </div>
    )
  }

  // ── Refused ───────────────────────────────────────────────────────────────
  if (job?.status === 'refused') {
    return (
      <main className="max-w-3xl mx-auto px-4 py-8">
        <Link to="/" className="text-sm text-blue-600 dark:text-blue-400 hover:underline mb-6 inline-block">
          ← Back to home
        </Link>
        <div className="space-y-4 py-8 max-w-lg">
          <h1 className="text-2xl font-bold">Couldn't generate this map</h1>
          <p className="text-gray-600 dark:text-gray-300">{job.error_message}</p>
          <button
            onClick={() => navigate(`/?title=${encodeURIComponent(title)}&cycleModel=1`)}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm"
          >
            Try with a different model
          </button>
        </div>
      </main>
    )
  }

  // ── Failed ────────────────────────────────────────────────────────────────
  if (job?.status === 'failed') {
    return (
      <main className="max-w-3xl mx-auto px-4 py-8">
        <Link to="/" className="text-sm text-blue-600 dark:text-blue-400 hover:underline mb-6 inline-block">
          ← Back to home
        </Link>
        <div className="space-y-4 py-8 max-w-lg">
          <h1 className="text-2xl font-bold">Something went wrong</h1>
          <p className="text-gray-600 dark:text-gray-300">
            {job.error_message ?? 'An unexpected error occurred.'}
            {job.error_code && (
              <span className="text-xs text-gray-400 ml-2">({job.error_code})</span>
            )}
          </p>
          <div className="flex gap-3">
            <button
              onClick={() => navigate(-1)}
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm"
            >
              Try again
            </button>
            <a
              href={`mailto:espen.torgersen@gmail.com?subject=Character map error&body=Job ID: ${id}%0AError: ${job.error_code}`}
              className="px-4 py-2 border border-gray-300 rounded hover:bg-gray-50 text-sm"
            >
              Report this
            </a>
          </div>
        </div>
      </main>
    )
  }

  // ── In-progress / Loading ─────────────────────────────────────────────────
  return (
    <main className="max-w-3xl mx-auto px-4 py-8">
      <Link to="/" className="text-sm text-blue-600 dark:text-blue-400 hover:underline mb-6 inline-block">
        ← Back to home
      </Link>
      <div className="space-y-6 py-8">
        <h1 className="text-2xl font-bold">Generating your character map…</h1>
        {title && (
          <p className="text-gray-600 dark:text-gray-300">
            <span className="font-medium">{title}</span> · {model}
          </p>
        )}

        {/* Progress bar */}
        <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2.5">
          <div
            className="bg-blue-600 h-2.5 rounded-full transition-all duration-700"
            style={{ width: `${Math.round(progress * 100)}%` }}
          />
        </div>

        <div className="flex justify-between text-sm text-gray-500 dark:text-gray-400">
          <span>{job?.status === 'generating' ? 'Generating…' : 'Queued…'}</span>
          <span>{elapsed}s elapsed · {eta}</span>
        </div>

        <p className="text-xs text-gray-400">
          Job ID: <code className="font-mono bg-gray-100 dark:bg-gray-800 px-1 rounded">{id}</code>
        </p>
      </div>
    </main>
  )
}
