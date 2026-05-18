import { useState } from 'react'

export function ShareButton({ jobId }: { jobId: string }) {
  const [copied, setCopied] = useState(false)

  const handleShare = async () => {
    try {
      await navigator.clipboard.writeText(`${window.location.origin}/job/${jobId}`)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      window.prompt('Copy this link:', `${window.location.origin}/job/${jobId}`)
    }
  }

  return (
    <button
      onClick={handleShare}
      className="px-4 py-2 text-sm font-semibold bg-[#2563eb] text-white rounded-lg hover:bg-[#1d4ed8] transition-colors"
    >
      {copied ? '✓ Copied!' : 'Share'}
    </button>
  )
}
