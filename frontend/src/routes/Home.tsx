import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import TitleSearch from '../components/TitleSearch'
import ModelDropdown from '../components/ModelDropdown'
import FormatCheckboxes from '../components/FormatCheckboxes'
import CharacterCapDropdown from '../components/CharacterCapDropdown'
import WhatThisIsBanner from '../components/WhatThisIsBanner'
import SpoilerWarningBanner from '../components/SpoilerWarningBanner'
import ResolveBanner from '../components/ResolveBanner'
import ResolveCandidatePicker from '../components/ResolveCandidatePicker'
import { useResolve } from '../hooks/useResolve'
import { useFormPrefill, type CharacterCap } from '../hooks/useFormPrefill'
import { useRecentMaps } from '../hooks/useRecentMaps'
import { ResolveCandidate, createJob } from '../api/client'

export default function Home() {
  const navigate = useNavigate()
  const { resolve, candidates, isLoading, error, hasSearched, reset } = useResolve()
  const { load, save } = useFormPrefill()
  const prefs = load()
  const { recentMaps } = useRecentMaps()

  const [model, setModel] = useState(prefs.model)
  const [formats, setFormats] = useState<string[]>(prefs.formats)
  const [email, setEmail] = useState('')
  const [workType, setWorkType] = useState<'book' | 'film_tv'>(prefs.workType)
  const [characterCap, setCharacterCap] = useState<CharacterCap>(prefs.characterCap)
  const [spoilerAcknowledged, setSpoilerAcknowledged] = useState(false)
  const [selectedCandidate, setSelectedCandidate] = useState<ResolveCandidate | null>(null)
  const [forceShowPicker, setForceShowPicker] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  useEffect(() => {
    save({ model, formats, workType, characterCap })
  }, [model, formats, workType, characterCap])

  const topCandidate = candidates[0] ?? null
  const autoSkip = !forceShowPicker && topCandidate !== null && topCandidate.confidence_score >= 0.9

  useEffect(() => {
    if (autoSkip && topCandidate) {
      setSelectedCandidate(topCandidate)
    }
  }, [autoSkip, topCandidate?.id])

  const canGenerate = spoilerAcknowledged && formats.length > 0 && selectedCandidate !== null

  function handleSearch(query: string) {
    reset()
    setSelectedCandidate(null)
    setForceShowPicker(false)
    resolve(query, workType)
  }

  async function handleGenerate() {
    if (!canGenerate || !selectedCandidate || submitting) return
    setSubmitError(null)
    setSubmitting(true)
    try {
      const { job_id } = await createJob({
        title_query: selectedCandidate.title,
        resolved: selectedCandidate,
        model,
        formats,
        email: email || undefined,
        acknowledged_spoilers: true,
        character_cap: characterCap,
      })
      const params = new URLSearchParams({ model, title: selectedCandidate.title })
      navigate(`/job/${job_id}?${params.toString()}`)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Failed to start the job'
      setSubmitError(msg)
      setSubmitting(false)
    }
  }

  return (
    <main className="max-w-2xl mx-auto px-4 py-8 space-y-6">
      <WhatThisIsBanner />

      <SpoilerWarningBanner
        acknowledged={spoilerAcknowledged}
        onAcknowledgeChange={setSpoilerAcknowledged}
      />

      {/* Type toggle */}
      <div>
        <label className="block text-sm font-medium mb-1">Type</label>
        <div className="flex gap-4">
          {(['book', 'film_tv'] as const).map((t) => (
            <label key={t} className="flex items-center gap-1.5 cursor-pointer">
              <input
                type="radio"
                name="workType"
                value={t}
                checked={workType === t}
                onChange={() => setWorkType(t)}
              />
              <span className="text-sm">{t === 'book' ? 'Book' : 'Film or TV'}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Title search */}
      <div>
        <label className="block text-sm font-medium mb-1">Title</label>
        <TitleSearch onSearch={handleSearch} isLoading={isLoading} />
      </div>

      {/* Resolve error */}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {/* Resolve state */}
      {candidates.length > 0 && autoSkip && (
        <ResolveBanner
          candidate={topCandidate!}
          onNotThis={() => {
            setForceShowPicker(true)
            setSelectedCandidate(null)
          }}
        />
      )}
      {candidates.length > 0 && !autoSkip && (
        <ResolveCandidatePicker
          candidates={candidates}
          selected={selectedCandidate}
          onSelect={setSelectedCandidate}
        />
      )}
      {candidates.length === 0 && !isLoading && !error && !hasSearched && (
        <p className="text-xs text-gray-400">Enter a title and press Search or Enter to resolve it.</p>
      )}
      {candidates.length === 0 && !isLoading && !error && hasSearched && (
        <p className="text-sm text-gray-500">No results — try a different title or add the author&apos;s name.</p>
      )}

      <ModelDropdown value={model} onChange={setModel} />
      <CharacterCapDropdown value={characterCap} onChange={setCharacterCap} />
      <FormatCheckboxes selected={formats} onChange={setFormats} />

      {/* Email */}
      <div>
        <label className="block text-sm font-medium mb-1">
          Email{' '}
          <span className="text-gray-500 font-normal">(optional — we'll send you the files)</span>
        </label>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@example.com"
          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      {/* Turnstile placeholder */}
      <div className="h-12 bg-gray-100 dark:bg-gray-800 rounded flex items-center justify-center text-xs text-gray-400">
        [Turnstile widget — Phase 5]
      </div>

      <button
        onClick={handleGenerate}
        disabled={!canGenerate || submitting}
        className="w-full py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {submitting ? 'Starting…' : 'Generate Character Map'}
      </button>
      {submitError && <p className="text-sm text-red-600">{submitError}</p>}

      {recentMaps.length > 0 && (
        <div className="mt-6 pt-6 border-t border-gray-200 dark:border-gray-700">
          <h2 className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-3">Your recent maps</h2>
          <ul className="space-y-2">
            {recentMaps.map((entry) => (
              <li key={entry.jobId}>
                <a
                  href={`/job/${entry.jobId}`}
                  className="flex items-center gap-3 p-2 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-900 transition-colors"
                >
                  {entry.thumbnailUrl && (
                    <img src={entry.thumbnailUrl} alt="" className="w-10 h-10 rounded object-cover" />
                  )}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{entry.title}</p>
                    <p className="text-xs text-gray-500">{new Date(entry.date).toLocaleDateString()}</p>
                  </div>
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}
    </main>
  )
}
