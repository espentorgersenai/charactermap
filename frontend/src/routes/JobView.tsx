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
      // h-full fills the flex-1 scroll container in App.tsx
      <div className="flex h-full overflow-hidden">
        {/* Canvas fills the available space */}
        <div className="flex-1 min-w-0">
          <CharacterMapCanvas charMap={charMap} jobId={id!} />
        </div>

        {/* Right sidebar: back link + downloads */}
        <div className="w-[210px] flex-shrink-0 bg-[#161616] border-l border-[#222] p-4 overflow-y-auto flex flex-col gap-4">
          <div>
            <Link
              to="/"
              className="text-[11px] text-[#555] hover:text-[#888] transition-colors"
            >
              ← Home
            </Link>
          </div>
          <div>
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
      <main className="max-w-3xl mx-auto px-5 py-8">
        <Link to="/" className="text-sm text-award-gold hover:text-award-gold-light transition-colors mb-6 inline-block">
          ← Back to home
        </Link>
        <div className="space-y-4 py-6 max-w-lg">
          <h1 className="font-serif text-2xl font-bold text-award-cream">Couldn't generate this map</h1>
          <p className="text-award-cream-muted">{job.error_message}</p>
          <button
            onClick={() => navigate(`/?title=${encodeURIComponent(title)}&cycleModel=1`)}
            className="px-5 py-2.5 bg-award-gold text-award-bg text-sm font-semibold rounded-lg hover:bg-award-gold-light transition-colors"
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
      <main className="max-w-3xl mx-auto px-5 py-8">
        <Link to="/" className="text-sm text-award-gold hover:text-award-gold-light transition-colors mb-6 inline-block">
          ← Back to home
        </Link>
        <div className="space-y-4 py-6 max-w-lg">
          <h1 className="font-serif text-2xl font-bold text-award-cream">Something went wrong</h1>
          <p className="text-award-cream-muted">
            {job.error_message ?? 'An unexpected error occurred.'}
            {job.error_code && (
              <span className="text-xs text-award-cream-dim ml-2">({job.error_code})</span>
            )}
          </p>
          <div className="flex gap-3">
            <button
              onClick={() => navigate(-1)}
              className="px-5 py-2.5 bg-award-gold text-award-bg text-sm font-semibold rounded-lg hover:bg-award-gold-light transition-colors"
            >
              Try again
            </button>
            <a
              href={`mailto:espen.torgersen@gmail.com?subject=Character map error&body=Job ID: ${id}%0AError: ${job.error_code}`}
              className="px-5 py-2.5 border border-award-border text-award-cream-muted text-sm rounded-lg hover:border-award-border-gold hover:text-award-cream transition-colors"
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
    <main className="max-w-2xl mx-auto px-5 py-8">
      <Link to="/" className="text-sm text-award-gold hover:text-award-gold-light transition-colors mb-6 inline-block">
        ← Back to home
      </Link>
      <div className="space-y-5 py-6">
        <h1 className="font-serif text-3xl font-bold text-award-cream leading-tight">
          Generating your character map…
        </h1>
        {title && (
          <p className="text-award-cream-muted">
            <span className="font-medium text-award-cream">{title}</span>
            <span className="text-award-cream-dim"> · {model}</span>
          </p>
        )}

        {/* Progress bar */}
        <div className="w-full bg-award-surface rounded-full h-1.5 overflow-hidden border border-award-border">
          <div
            className="bg-award-gold h-1.5 rounded-full transition-all duration-700"
            style={{ width: `${Math.round(progress * 100)}%` }}
          />
        </div>

        <div className="flex justify-between text-sm text-award-cream-dim">
          <span>{job?.status === 'generating' ? 'Generating…' : 'Queued…'}</span>
          <span>{elapsed}s elapsed · {eta}</span>
        </div>

        {/* Tips while waiting */}
        <div className="mt-6 p-4 bg-award-surface border border-award-border rounded-xl space-y-2">
          <p className="text-[11px] font-semibold text-award-cream-dim uppercase tracking-[0.08em]">
            While you wait
          </p>
          <p className="text-sm text-award-cream-muted">
            → Different models know different works — if results are poor, try Gemini for obscure titles.
          </p>
          <p className="text-sm text-award-cream-muted">
            → You'll get a shareable link when generation is complete.
          </p>
          <p className="text-sm text-award-cream-muted">
            → Bookmark this page — your map is saved for 90 days.
          </p>
        </div>

        {/* Job ID hidden in details */}
        <details className="text-xs text-award-cream-dim">
          <summary className="cursor-pointer hover:text-award-cream-muted transition-colors">
            Technical details
          </summary>
          <p className="mt-2 font-mono bg-award-surface border border-award-border px-2 py-1 rounded text-award-cream-dim inline-block">
            Job ID: {id}
          </p>
        </details>
      </div>
    </main>
  )
}
