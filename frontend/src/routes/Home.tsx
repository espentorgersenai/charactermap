import { useEffect, useState, useRef } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import TitleSearch from '../components/TitleSearch'
import ModelDropdown from '../components/ModelDropdown'
import FormatCheckboxes from '../components/FormatCheckboxes'
import CharacterCapDropdown from '../components/CharacterCapDropdown'
import ResolveBanner from '../components/ResolveBanner'
import ResolveCandidatePicker from '../components/ResolveCandidatePicker'
import SelectedCandidateExtras from '../components/SelectedCandidateExtras'
import HowThisWorksModal from '../components/HowThisWorksModal'
import Turnstile from '../components/Turnstile'
import { useResolve } from '../hooks/useResolve'
import { useFormPrefill, type CharacterCap } from '../hooks/useFormPrefill'
import { useRecentMaps } from '../hooks/useRecentMaps'
import { useLimits } from '../hooks/useLimits'
import { useScrollReveal } from '../hooks/useScrollReveal'
import { ResolveCandidate, createJob, trackEvent } from '../api/client'

// ── Photos ────────────────────────────────────────────────────────────────────
const HERO_PHOTO =
  'https://images.pexels.com/photos/109669/pexels-photo-109669.jpeg?auto=compress&cs=tinysrgb&w=1920'
const BOOK_PHOTO = '/library-hero.jpg'
const FILM_PHOTO =
  'https://images.pexels.com/photos/7991381/pexels-photo-7991381.jpeg?auto=compress&cs=tinysrgb&w=1200'

// ── Scroll-reveal wrapper ─────────────────────────────────────────────────────
function Reveal({
  children, delay = 0, className = '',
}: {
  children: React.ReactNode; delay?: number; className?: string
}) {
  const { ref, inView } = useScrollReveal()
  return (
    <div
      ref={ref as React.RefObject<HTMLDivElement>}
      className={`reveal ${inView ? 'in-view' : ''} ${delay ? `reveal-delay-${delay}` : ''} ${className}`}
    >
      {children}
    </div>
  )
}

// ── Hero scroll indicator ─────────────────────────────────────────────────────
function ScrollIndicator() {
  return (
    <div className="flex flex-col items-center gap-1.5 scroll-bob">
      <span className="text-[10px] uppercase tracking-[0.4em]" style={{ color: 'rgba(212,175,55,0.5)' }}>
        Scroll
      </span>
      <svg width="16" height="20" viewBox="0 0 16 20" fill="none">
        <rect x="6.5" y="2" width="3" height="6" rx="1.5" fill="rgba(212,175,55,0.5)" />
        <rect x="0.5" y="0.5" width="15" height="19" rx="7.5" stroke="rgba(212,175,55,0.3)" />
      </svg>
    </div>
  )
}

// ── Step label ────────────────────────────────────────────────────────────────
function StepLabel({ n, title }: { n: string; title: string }) {
  return (
    <div className="mb-8">
      <p className="text-[9px] uppercase tracking-[0.45em] mb-1" style={{ color: '#A88C2A' }}>{n}</p>
      <h2 className="font-serif text-3xl text-award-cream" style={{ letterSpacing: '-0.01em' }}>{title}</h2>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Maps backend error codes (from FastAPI HTTPException detail.code) to
// user-friendly copy. Falls back to a generic message for unknown codes.
const ERROR_COPY: Record<string, string> = {
  RATE_LIMITED: 'You\'re sending requests too quickly. Try again in a moment.',
  DAILY_BUDGET_EXHAUSTED:
    'The service has hit today\'s spending limit. Please try again tomorrow.',
  TURNSTILE_FAILED:
    'Captcha verification failed. Refresh the page and try again.',
  SPOILERS_NOT_ACKNOWLEDGED:
    'Please acknowledge the spoiler warning before generating.',
}

function friendlyError(raw: string): string {
  return ERROR_COPY[raw] ?? raw
}

const MODEL_CYCLE = [
  'claude-sonnet-4-6',
  'claude-opus-4-8',
  'gpt-5.5',
  'gemini-2.5-pro',
]

export default function Home() {
  const navigate   = useNavigate()
  const [searchParams] = useSearchParams()
  const { resolve, candidates, isLoading, error, hasSearched, reset } = useResolve()
  const { load, save } = useFormPrefill()
  const prefs = load()
  const { recentMaps } = useRecentMaps()
  const { limits } = useLimits()
  const dailyLeft = limits?.jobs.per_day ?? null
  const budgetExhausted =
    (limits?.cost.remaining_usd ?? 1) <= 0 || dailyLeft === 0
  const [showModal, setShowModal] = useState(false)

  const [model, setModel]               = useState(prefs.model)
  const [formats, setFormats]           = useState<string[]>(prefs.formats)
  const [email, setEmail]               = useState('')
  const [workType, setWorkType]         = useState<'book' | 'film_tv'>(prefs.workType)
  const [characterCap, setCharacterCap] = useState<CharacterCap>(prefs.characterCap)
  // Spoiler banner hidden in v1 (the WhatThisIsBanner already sets honest
  // expectations). Backend still hard-gates on `acknowledged_spoilers: true`
  // — the field is always sent as true from this page.
  const [selectedCandidate, setSelectedCandidate]     = useState<ResolveCandidate | null>(null)
  const [season, setSeason]                           = useState<number | null>(null)
  const [forceShowPicker, setForceShowPicker]         = useState(false)
  const [submitting, setSubmitting]   = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [turnstileToken, setTurnstileToken] = useState<string | null>(null)
  const [turnstileResetSignal, setTurnstileResetSignal] = useState(0)

  // VITE_TURNSTILE_SITE_KEY is set in production (.env.production) and
  // empty in dev. The widget is skipped entirely when unset so local dev
  // doesn't require a key.
  const turnstileSiteKey = import.meta.env.VITE_TURNSTILE_SITE_KEY as string | undefined
  const turnstileRequired = !!turnstileSiteKey

  const searchRef = useRef<HTMLDivElement>(null)

  // Refused/failed JobView sends users back here with ?title=…&cycleModel=1
  // to retry with the next-best model. Cycle wraps around the MODEL_CYCLE list.
  useEffect(() => {
    if (searchParams.get('cycleModel') !== '1') return
    const idx = MODEL_CYCLE.indexOf(model)
    const next = MODEL_CYCLE[(idx + 1) % MODEL_CYCLE.length]
    setModel(next)
    savePrefs({ model: next })
    const titleParam = searchParams.get('title')
    if (titleParam) handleSearch(titleParam)
    // strip the query so reloading doesn't re-cycle
    navigate('/', { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const savePrefs = (updates: Partial<Parameters<typeof save>[0]>) =>
    save({ model, formats, workType, characterCap, ...updates })

  const topCandidate = candidates[0] ?? null
  const autoSkip = !forceShowPicker && topCandidate !== null && topCandidate.confidence_score >= 0.9

  if (autoSkip && topCandidate && !selectedCandidate) setSelectedCandidate(topCandidate)

  const canGenerate =
    formats.length > 0 &&
    selectedCandidate !== null &&
    !budgetExhausted &&
    (!turnstileRequired || !!turnstileToken)

  function handleSearch(query: string) {
    reset(); setSelectedCandidate(null); setSeason(null); setForceShowPicker(false)
    resolve(query, workType)
  }

  // Replace the selected candidate while keeping reference identity (the
  // picker / banner key off it). Reset season any time the candidate changes
  // identity so an S2 pin from one show doesn't bleed into another.
  function chooseCandidate(c: ResolveCandidate | null) {
    setSelectedCandidate(c)
    setSeason(null)
  }

  function clearAdaptation() {
    if (!selectedCandidate) return
    setSelectedCandidate({ ...selectedCandidate, adaptation: null })
  }

  function handleTypeSelect(type: 'book' | 'film_tv') {
    setWorkType(type); savePrefs({ workType: type })
    setTimeout(() => searchRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 200)
  }

  async function handleGenerate() {
    if (!canGenerate || !selectedCandidate || submitting) return
    setSubmitError(null); setSubmitting(true)
    try {
      const { job_id } = await createJob({
        title_query: selectedCandidate.title, resolved: selectedCandidate,
        model, formats, email: email || undefined,
        acknowledged_spoilers: true, character_cap: characterCap,
        turnstile_token: turnstileToken ?? undefined,
        season,
      })
      navigate(`/job/${job_id}?${new URLSearchParams({ model, title: selectedCandidate.title })}`)
    } catch (e: unknown) {
      const raw = e instanceof Error ? e.message : 'Failed to start the job'
      setSubmitError(friendlyError(raw))
      setSubmitting(false)
      // Tokens are single-use server-side. Force a fresh challenge for the
      // retry so the next submit doesn't 403 with a stale token.
      setTurnstileToken(null)
      setTurnstileResetSignal((n) => n + 1)
    }
  }

  return (
    <div className="award-stage min-h-screen">

      {/* ════════════════════════════════════════════════════════
          HERO — full-viewport cinematic
      ════════════════════════════════════════════════════════ */}
      <section className="relative flex flex-col items-center justify-center overflow-hidden" style={{ minHeight: '100svh' }}>
        <div aria-hidden className="absolute inset-0"
          style={{ backgroundImage: `url(${HERO_PHOTO})`, backgroundSize: 'cover', backgroundPosition: 'center 30%', backgroundAttachment: 'fixed' }} />
        <div aria-hidden className="absolute inset-0"
          style={{ background: 'linear-gradient(to bottom, rgba(13,11,9,0.5) 0%, rgba(13,11,9,0.25) 40%, rgba(13,11,9,0.7) 80%, rgba(13,11,9,1) 100%)' }} />
        <div aria-hidden className="absolute inset-0"
          style={{ background: 'radial-gradient(ellipse 65% 55% at 50% 45%, rgba(212,175,55,0.12) 0%, transparent 70%)' }} />

        <div className="relative text-center px-6 z-10">
          <p className="hero-animate hero-animate-delay-1 text-[9px] uppercase tracking-[0.55em] mb-8" style={{ color: '#A88C2A' }}>
            Visual Character Maps
          </p>
          <h1
            className="hero-animate hero-animate-delay-2 font-serif font-bold text-gold-shimmer leading-none"
            style={{ fontSize: 'clamp(4rem, 10vw, 9rem)', letterSpacing: '-0.02em' }}
          >
            CharacterMap
          </h1>
          <p className="hero-animate hero-animate-delay-3 mt-5 text-[11px] uppercase tracking-[0.35em]" style={{ color: 'rgba(196,180,154,0.75)' }}>
            AI · Literature &amp; Film · Interactive Diagrams
          </p>
          <div className="hero-animate hero-animate-delay-4 mt-10 flex items-center justify-center gap-5 max-w-[280px] mx-auto">
            <div className="flex-1 h-px" style={{ background: 'linear-gradient(to right, transparent, rgba(212,175,55,0.65))' }} />
            <span style={{ color: '#D4AF37', fontSize: '0.55rem', letterSpacing: '0.4em' }}>✦ ✦ ✦</span>
            <div className="flex-1 h-px" style={{ background: 'linear-gradient(to left, transparent, rgba(212,175,55,0.65))' }} />
          </div>
          <p className="hero-animate hero-animate-delay-4 mt-6 text-xs text-award-cream-dim">
            Enter a title — get an interactive map of every character and their relationships.{' '}
            <button onClick={() => setShowModal(true)} className="underline transition-colors" style={{ color: '#D4AF37' }}>
              How it works
            </button>
          </p>
        </div>

        <div className="hero-animate hero-animate-delay-4 absolute bottom-10 left-1/2 -translate-x-1/2 z-10">
          <ScrollIndicator />
        </div>
      </section>

      {/* ════════════════════════════════════════════════════════
          TYPE SELECTOR — full-width immersive photo panels
      ════════════════════════════════════════════════════════ */}
      <section>
        <Reveal className="text-center py-10 px-6">
          <p className="text-[9px] uppercase tracking-[0.45em] mb-2" style={{ color: '#A88C2A' }}>Step 1</p>
          <h2 className="font-serif text-3xl text-award-cream" style={{ letterSpacing: '-0.01em' }}>What will you explore?</h2>
        </Reveal>

        <div className="flex" style={{ minHeight: '320px' }}>
          {(['book', 'film_tv'] as const).map((t) => {
            const isBook = t === 'book'
            const selected = workType === t
            return (
              <button
                key={t}
                onClick={() => handleTypeSelect(t)}
                className={`type-panel flex-1 ${selected ? 'selected' : ''}`}
                aria-pressed={selected}
              >
                <div className="type-panel-bg" style={{ backgroundImage: `url(${isBook ? BOOK_PHOTO : FILM_PHOTO})` }} />
                <div className="type-panel-overlay" style={{
                  background: selected
                    ? 'linear-gradient(to top, rgba(13,11,9,0.85) 0%, rgba(13,11,9,0.45) 60%, rgba(13,11,9,0.15) 100%)'
                    : 'linear-gradient(to top, rgba(13,11,9,0.92) 0%, rgba(13,11,9,0.7) 60%, rgba(13,11,9,0.45) 100%)',
                }} />
                <div className="type-panel-border" />
                <div className="type-panel-content h-full flex flex-col items-center justify-end pb-10 px-6">
                  <span className="text-4xl mb-3">{isBook ? '📚' : '🎬'}</span>
                  <p className="font-serif text-2xl font-semibold text-award-cream">{isBook ? 'Literature' : 'Film & TV'}</p>
                  <p className="mt-1 text-xs text-award-cream-muted tracking-wide">{isBook ? 'Novels · Short stories · Poetry' : 'Movies · Series · Documentaries'}</p>
                  {selected && (
                    <div className="mt-3 flex items-center gap-1.5 text-xs font-semibold" style={{ color: '#D4AF37' }}>
                      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                        <circle cx="7" cy="7" r="6.5" stroke="#D4AF37" />
                        <path d="M4 7l2 2 4-4" stroke="#D4AF37" strokeWidth="1.5" strokeLinecap="round" />
                      </svg>
                      Selected
                    </div>
                  )}
                </div>
              </button>
            )
          })}
        </div>
      </section>

      {/* Gold hairline */}
      <div className="gold-hairline mx-10 opacity-25 my-0" />

      {/* ════════════════════════════════════════════════════════
          SPOILER — inline, full-width strip
      ════════════════════════════════════════════════════════ */}
      {/* Spoiler banner hidden in v1 — revisit when shipping spoiler-safe mode. */}

      {/* ════════════════════════════════════════════════════════
          SEARCH + CONFIGURE — two-column on wide screens
      ════════════════════════════════════════════════════════ */}
      <section ref={searchRef} className="max-w-7xl mx-auto px-8 py-16">
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-x-24 gap-y-16">

          {/* ── Left: Search ── */}
          <div>
            <Reveal><StepLabel n="Step 2" title="Find your title" /></Reveal>

            <Reveal delay={1}>
              <TitleSearch
                onSearch={handleSearch}
                isLoading={isLoading}
                initialValue={searchParams.get('title') ?? undefined}
              />
            </Reveal>

            {error && <Reveal delay={1}><p className="text-sm text-award-crimson mt-4">{error}</p></Reveal>}

            <div aria-live="polite" className="mt-6">
              {candidates.length > 0 && autoSkip && (
                <Reveal>
                  <ResolveBanner
                    candidate={topCandidate!}
                    onNotThis={() => { setForceShowPicker(true); chooseCandidate(null) }}
                  />
                </Reveal>
              )}
              {candidates.length > 0 && !autoSkip && (
                <Reveal>
                  <ResolveCandidatePicker
                    candidates={candidates}
                    selected={selectedCandidate}
                    onSelect={chooseCandidate}
                  />
                </Reveal>
              )}
              {selectedCandidate && (
                <Reveal>
                  <SelectedCandidateExtras
                    candidate={selectedCandidate}
                    season={season}
                    onSeasonChange={setSeason}
                    onClearAdaptation={clearAdaptation}
                  />
                </Reveal>
              )}
              {candidates.length === 0 && !isLoading && !error && !hasSearched && (
                <p className="text-xs text-award-cream-dim">Enter any title and press Search or ↵</p>
              )}
              {candidates.length === 0 && !isLoading && !error && hasSearched && (
                <p className="text-sm text-award-cream-muted">No results — try a different title or add the author's name.</p>
              )}
            </div>

            {/* Recent maps — lives under search on wide screens */}
            {recentMaps.length > 0 && (
              <div className="mt-14">
                <div className="gold-hairline opacity-20 mb-6" />
                <Reveal>
                  <p className="text-[9px] font-bold uppercase tracking-[0.35em] mb-4" style={{ color: '#A88C2A' }}>Your recent maps</p>
                </Reveal>
                <ul className="space-y-0">
                  {recentMaps.map((entry, i) => (
                    <Reveal key={entry.jobId} delay={Math.min(i + 1, 4) as 1|2|3|4}>
                      <a
                        href={`/job/${entry.jobId}`}
                        onClick={() => trackEvent('recent_map_click', {}, entry.jobId)}
                        className="flex items-center gap-4 py-3 group transition-all"
                        style={{ borderBottom: '1px solid rgba(61,48,32,0.5)' }}
                      >
                        {entry.thumbnailUrl && (
                          <img src={entry.thumbnailUrl} alt="" className="w-10 h-10 rounded object-cover opacity-70 group-hover:opacity-90 transition-opacity" />
                        )}
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-award-cream truncate group-hover:text-award-gold-light transition-colors">{entry.title}</p>
                          <p className="text-[10px] text-award-cream-dim">{new Date(entry.date).toLocaleDateString()}</p>
                        </div>
                        <span className="text-award-gold-dim group-hover:text-award-gold transition-colors text-sm">→</span>
                      </a>
                    </Reveal>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* ── Right: Configure ── */}
          <div>
            <Reveal><StepLabel n="Step 3" title="Fine-tune your map" /></Reveal>

            <div className="space-y-10">
              <Reveal delay={1}><ModelDropdown value={model} onChange={(v) => { setModel(v); savePrefs({ model: v }) }} /></Reveal>
              <Reveal delay={2}><CharacterCapDropdown value={characterCap} onChange={(v) => { setCharacterCap(v); savePrefs({ characterCap: v }) }} /></Reveal>
              <Reveal delay={2}><FormatCheckboxes selected={formats} onChange={(v) => { setFormats(v); savePrefs({ formats: v }) }} /></Reveal>
              <Reveal delay={3}>
                <div>
                  <label className="block text-[10px] uppercase tracking-[0.2em] text-award-cream-dim mb-1">
                    Email <span className="normal-case opacity-70">(optional — we'll notify you)</span>
                  </label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@example.com"
                    className="input-underline"
                  />
                </div>
              </Reveal>
            </div>
          </div>
        </div>
      </section>

      {/* Gold hairline */}
      <div className="gold-hairline mx-10 opacity-25" />

      {/* ════════════════════════════════════════════════════════
          GENERATE — full-width dramatic CTA
      ════════════════════════════════════════════════════════ */}
      <section className="relative overflow-hidden py-24 px-6 text-center">
        <div aria-hidden className="absolute inset-0 pointer-events-none"
          style={{ background: 'radial-gradient(ellipse 70% 80% at 50% 50%, rgba(212,175,55,0.07) 0%, transparent 70%)' }} />

        <Reveal>
          <p className="text-[9px] uppercase tracking-[0.45em] mb-1" style={{ color: '#A88C2A' }}>Step 4</p>
          <h2 className="font-serif text-3xl text-award-cream mb-10" style={{ letterSpacing: '-0.01em' }}>Reveal the characters</h2>
        </Reveal>

        <Reveal delay={1} className="relative">
          {/* Daily quota hint. Hide when the user still has the full daily
              allotment (no one wants to see '15 generations left today' on
              first load), surface as soon as they've used at least one. */}
          {dailyLeft !== null && dailyLeft < 15 && !budgetExhausted && (
            <p className="text-[10px] text-award-cream-dim mb-3 tracking-wider">
              You have <span className="text-award-cream">{dailyLeft}</span>{' '}
              generation{dailyLeft === 1 ? '' : 's'} left today
            </p>
          )}
          {budgetExhausted && (
            <p className="text-[11px] text-award-crimson mb-3">
              Daily limit reached. Please try again tomorrow.
            </p>
          )}
          {!canGenerate && !budgetExhausted && (
            <p className="text-[10px] text-award-cream-dim mb-4 tracking-widest uppercase">
              {!selectedCandidate ? '— Search and select a title first —'
                : formats.length === 0 ? '— Select at least one output format —'
                : turnstileRequired && !turnstileToken ? '— Complete the captcha below —'
                : ''}
            </p>
          )}
          {turnstileRequired && (
            <div className="flex justify-center mb-6">
              <Turnstile
                siteKey={turnstileSiteKey}
                onToken={setTurnstileToken}
                onExpire={() => setTurnstileToken(null)}
                resetSignal={turnstileResetSignal}
              />
            </div>
          )}
          <button
            onClick={handleGenerate}
            disabled={!canGenerate || submitting}
            className={`inline-flex items-center justify-center px-20 py-5 rounded-full text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-award-gold focus-visible:ring-offset-4 focus-visible:ring-offset-award-bg transition-all duration-300 ${
              canGenerate && !submitting ? 'btn-gold-metal' : 'text-award-cream-dim cursor-not-allowed'
            }`}
            style={!canGenerate || submitting ? { border: '1px solid rgba(61,48,32,0.6)', background: 'rgba(28,24,16,0.7)' } : undefined}
          >
            {submitting ? (
              <span className="flex items-center gap-2">
                <svg className="animate-spin" width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.5" strokeOpacity="0.3" />
                  <path d="M14 8A6 6 0 0 0 8 2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                </svg>
                Starting…
              </span>
            ) : 'Generate Character Map'}
          </button>
          {submitError && <p className="text-sm text-award-crimson mt-4">{submitError}</p>}
        </Reveal>

        <Reveal delay={3} className="mt-10">
          <p className="text-[10px] text-award-cream-dim">
            Hobby project · Results may vary · Maps saved 90 days ·{' '}
            <button onClick={() => setShowModal(true)} className="underline" style={{ color: '#D4AF37' }}>How it works</button>
          </p>
        </Reveal>
      </section>

      {/* ════════════════════════════════════════════════════════
          STICKY GENERATE BAR — always visible at bottom
      ════════════════════════════════════════════════════════ */}
      <div
        className="fixed bottom-0 inset-x-0 z-50 flex items-center justify-between gap-4 px-8 py-4"
        style={{
          background: 'rgba(10,8,6,0.88)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          borderTop: '1px solid rgba(212,175,55,0.18)',
        }}
      >
        {/* Status chips */}
        <div className="flex items-center gap-3 flex-wrap min-w-0">
          <StatusChip done={!!selectedCandidate} label={selectedCandidate ? selectedCandidate.title : 'No title selected'} />
          <span className="text-award-gold-dim text-xs hidden sm:block">·</span>
          <StatusChip done={formats.length > 0} label={formats.length > 0 ? formats.join(', ') : 'No format'} />
        </div>

        {/* Generate button */}
        <button
          onClick={handleGenerate}
          disabled={!canGenerate || submitting}
          className={`shrink-0 px-8 py-2.5 rounded-full text-sm transition-all duration-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-award-gold ${
            canGenerate && !submitting ? 'btn-gold-metal' : 'text-award-cream-dim cursor-not-allowed'
          }`}
          style={!canGenerate || submitting ? { border: '1px solid rgba(61,48,32,0.6)', background: 'rgba(28,24,16,0.7)', animation: 'none', boxShadow: 'none' } : undefined}
        >
          {submitting ? 'Starting…' : 'Generate Character Map'}
        </button>
      </div>

      {/* Bottom padding so page content clears the sticky bar */}
      <div className="h-20" />

      {showModal && <HowThisWorksModal onClose={() => setShowModal(false)} />}
    </div>
  )
}

function StatusChip({ done, label }: { done: boolean; label: string }) {
  return (
    <span
      className="flex items-center gap-1.5 text-xs truncate max-w-[200px]"
      style={{ color: done ? '#D4AF37' : '#7A6A54' }}
    >
      <span>{done ? '✦' : '○'}</span>
      <span className="truncate">{label}</span>
    </span>
  )
}
