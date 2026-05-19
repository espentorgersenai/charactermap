import { useEffect, useRef } from 'react'

declare global {
  interface Window {
    turnstile?: {
      render: (
        el: HTMLElement,
        opts: {
          sitekey: string
          callback: (token: string) => void
          'expired-callback'?: () => void
          'error-callback'?: () => void
          theme?: 'auto' | 'light' | 'dark'
          size?: 'normal' | 'flexible' | 'compact'
        },
      ) => string
      reset: (widgetId?: string) => void
      remove: (widgetId?: string) => void
    }
  }
}

const SCRIPT_SRC = 'https://challenges.cloudflare.com/turnstile/v0/api.js'

let scriptPromise: Promise<void> | null = null

// Load Cloudflare's turnstile script once. Repeated renders reuse the cached
// promise so we don't inject the <script> tag multiple times.
function loadScript(): Promise<void> {
  if (scriptPromise) return scriptPromise
  scriptPromise = new Promise((resolve, reject) => {
    if (typeof window === 'undefined') return resolve()
    if (window.turnstile) return resolve()
    const existing = document.querySelector<HTMLScriptElement>(
      `script[src^="${SCRIPT_SRC}"]`,
    )
    if (existing) {
      existing.addEventListener('load', () => resolve(), { once: true })
      existing.addEventListener('error', () => reject(new Error('Turnstile script failed')), { once: true })
      return
    }
    const s = document.createElement('script')
    s.src = SCRIPT_SRC
    s.async = true
    s.defer = true
    s.onload = () => resolve()
    s.onerror = () => reject(new Error('Turnstile script failed'))
    document.head.appendChild(s)
  })
  return scriptPromise
}

interface Props {
  onToken: (token: string) => void
  onExpire?: () => void
  // The site key. Pass null/undefined to render nothing (dev mode).
  siteKey?: string | null
  // External nudge to force a re-render of the widget. Bump this number after
  // a submit so the next attempt requires a fresh challenge (tokens are
  // single-use server-side).
  resetSignal?: number
}

export default function Turnstile({ onToken, onExpire, siteKey, resetSignal }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const widgetIdRef = useRef<string | null>(null)

  useEffect(() => {
    if (!siteKey || !containerRef.current) return
    let cancelled = false

    loadScript().then(() => {
      if (cancelled || !window.turnstile || !containerRef.current) return
      widgetIdRef.current = window.turnstile.render(containerRef.current, {
        sitekey: siteKey,
        theme: 'dark',
        callback: (token) => onToken(token),
        'expired-callback': () => onExpire?.(),
        'error-callback': () => onExpire?.(),
      })
    })

    return () => {
      cancelled = true
      if (window.turnstile && widgetIdRef.current) {
        try {
          window.turnstile.remove(widgetIdRef.current)
        } catch {
          // Re-mount races with script unload — safe to ignore.
        }
        widgetIdRef.current = null
      }
    }
  }, [siteKey, onToken, onExpire])

  // Tokens are single-use. After form submit, the parent bumps `resetSignal`
  // to invalidate the held token and force a new challenge.
  useEffect(() => {
    if (resetSignal === undefined) return
    if (window.turnstile && widgetIdRef.current) {
      try {
        window.turnstile.reset(widgetIdRef.current)
      } catch {
        /* widget already removed */
      }
    }
  }, [resetSignal])

  if (!siteKey) return null
  return <div ref={containerRef} />
}
