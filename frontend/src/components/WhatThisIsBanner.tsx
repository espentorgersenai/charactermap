import { useState } from 'react'
import HowThisWorksModal from './HowThisWorksModal'

export default function WhatThisIsBanner() {
  const [showModal, setShowModal] = useState(false)

  return (
    <>
      <div className="flex items-center justify-between gap-4">
        <p className="text-xs text-award-cream-dim leading-snug">
          AI generates visual character maps for any book or film.
          Results may vary — treat as a starting point.
        </p>
        <button
          onClick={() => setShowModal(true)}
          className="shrink-0 text-xs font-medium transition-colors whitespace-nowrap"
          style={{ color: '#D4AF37' }}
          onMouseEnter={(e) => { e.currentTarget.style.color = '#E2CA78' }}
          onMouseLeave={(e) => { e.currentTarget.style.color = '#D4AF37' }}
        >
          How it works →
        </button>
      </div>
      {showModal && <HowThisWorksModal onClose={() => setShowModal(false)} />}
    </>
  )
}
