import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import TitleSearch from '../components/TitleSearch'
import ModelDropdown from '../components/ModelDropdown'
import FormatCheckboxes from '../components/FormatCheckboxes'
import WhatThisIsBanner from '../components/WhatThisIsBanner'
import SpoilerWarningBanner from '../components/SpoilerWarningBanner'
import { useResolve } from '../hooks/useResolve'
import { ResolveCandidate } from '../api/client'

const DEFAULT_FORMATS = ['interactive']

export default function Home() {
  const navigate = useNavigate()
  const { resolve, candidates, isLoading, error, reset } = useResolve()

  const [model, setModel] = useState('claude-sonnet-4-6')
  const [formats, setFormats] = useState<string[]>(DEFAULT_FORMATS)
  const [email, setEmail] = useState('')
  const [workType, setWorkType] = useState<'book' | 'film_tv'>('book')
  const [spoilerAcknowledged, setSpoilerAcknowledged] = useState(false)
  const [selectedCandidate, setSelectedCandidate] = useState<ResolveCandidate | null>(null)

  const canGenerate = spoilerAcknowledged && formats.length > 0 && selectedCandidate !== null

  function handleSearch(query: string) {
    reset()
    setSelectedCandidate(null)
    resolve(query, workType)
  }

  function handleGenerate() {
    if (!canGenerate) return
    // Phase 2 will POST /api/jobs here. For now navigate to stub.
    navigate('/job/stub-phase-1')
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

      {/* Candidates — simple list (ResolveCandidatePicker replaces this in Task 6) */}
      {candidates.length > 0 && (
        <div>
          <p className="text-sm font-medium mb-2">Select a match:</p>
          <ul className="space-y-2">
            {candidates.map((c) => (
              <li key={c.id}>
                <button
                  onClick={() => setSelectedCandidate(c)}
                  className={`w-full text-left p-3 rounded-lg border text-sm ${
                    selectedCandidate?.id === c.id
                      ? 'border-blue-500 bg-blue-50 dark:bg-blue-950'
                      : 'border-gray-200 dark:border-gray-700 hover:border-gray-300'
                  }`}
                >
                  <span className="font-medium">{c.title}</span>
                  {c.year && <span className="text-gray-500 ml-2">({c.year})</span>}
                  {c.author && <span className="text-gray-500 ml-2">by {c.author}</span>}
                  <span className="text-gray-400 ml-2 text-xs">
                    {(c.confidence_score * 100).toFixed(0)}% match
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {candidates.length === 0 && !isLoading && !error && (
        <p className="text-xs text-gray-400">Enter a title and press Search or Enter to resolve it.</p>
      )}

      <ModelDropdown value={model} onChange={setModel} />
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
        disabled={!canGenerate}
        className="w-full py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        Generate Character Map
      </button>
    </main>
  )
}
