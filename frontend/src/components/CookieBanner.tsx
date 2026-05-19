import { useState } from 'react'
import { Link } from 'react-router-dom'

// SPEC §15.4 — a minimal one-button banner. No optional/marketing cookies,
// so EU rules don't need a consent gate. The banner just *notifies* that
// Turnstile uses a cookie for bot prevention.
//
// Dismissal persists in localStorage so it doesn't reappear on every visit.
const STORAGE_KEY = 'cm-cookie-banner-dismissed'

export default function CookieBanner() {
  const [dismissed, setDismissed] = useState<boolean>(
    () => localStorage.getItem(STORAGE_KEY) === '1',
  )

  if (dismissed) return null

  function dismiss() {
    localStorage.setItem(STORAGE_KEY, '1')
    setDismissed(true)
  }

  return (
    <div
      className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 max-w-xl w-[calc(100%-2rem)] flex flex-col sm:flex-row items-start sm:items-center gap-3 px-4 py-3 rounded-lg text-sm shadow-lg"
      style={{
        background: 'rgba(13,11,9,0.96)',
        border: '1px solid rgba(212,175,55,0.18)',
        backdropFilter: 'blur(12px)',
        WebkitBackdropFilter: 'blur(12px)',
        color: '#E5D9B7',
      }}
      role="dialog"
      aria-label="Cookie notice"
    >
      <p className="flex-1 leading-snug">
        We use Cloudflare Turnstile for bot prevention; it sets a cookie. No
        marketing or analytics cookies are used. See our{' '}
        <Link to="/privacy" className="underline hover:text-award-cream">
          privacy policy
        </Link>
        .
      </p>
      <button
        type="button"
        onClick={dismiss}
        className="shrink-0 px-3 py-1.5 rounded text-xs font-medium"
        style={{
          background: 'rgba(212,175,55,0.18)',
          color: '#E2CA78',
          border: '1px solid rgba(212,175,55,0.3)',
        }}
      >
        OK, got it
      </button>
    </div>
  )
}
