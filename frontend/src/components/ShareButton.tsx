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
      className="px-4 py-2 text-sm font-semibold text-[#e5e7eb] border-[1.5px] border-[#444] rounded-lg bg-transparent hover:border-[#666] transition-colors"
    >
      {copied ? '✓ Copied!' : 'Share'}
    </button>
  )
}
