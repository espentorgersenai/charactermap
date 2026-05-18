import { useState } from 'react'
import HowThisWorksModal from './HowThisWorksModal'

export default function WhatThisIsBanner() {
  const [showModal, setShowModal] = useState(false)

  return (
    <>
      <div className="rounded-lg bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 p-4 text-sm text-gray-700 dark:text-gray-300">
        <p className="font-medium mb-1">What this is</p>
        <p>
          A small hobby project that went from idea to working website in about an hour. It asks an
          AI to make a visual character map for any book or film you name. It&apos;s fun. It is{' '}
          <em>not</em> a polished commercial product. The AI sometimes makes things up, misses major
          characters, mismatches actors, or — if your work is obscure — has no idea what you&apos;re
          talking about. Treat the maps as a starting point, not a reference.
        </p>
        <p className="mt-2">
          If you spot something wrong, you can swap actor photos manually, or just regenerate with a
          different model from the dropdown. Different models know different works.{' '}
          <button
            onClick={() => setShowModal(true)}
            className="text-blue-600 dark:text-blue-400 hover:underline"
          >
            How this works
          </button>
        </p>
      </div>
      {showModal && <HowThisWorksModal onClose={() => setShowModal(false)} />}
    </>
  )
}
