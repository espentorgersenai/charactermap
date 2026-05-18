import { useEffect, useState } from 'react'
import { getArtifacts, type ArtifactInfo } from '../api/client'

const FORMAT_LABELS: Record<string, string> = {
  markdown: '📄 Markdown',
  pdf:      '📑 PDF',
  png:      '🖼 PNG (2×)',
  svg:      '↗ SVG',
  json:     '{ } JSON',
}

export function DownloadList({ jobId }: { jobId: string }) {
  const [artifacts, setArtifacts] = useState<ArtifactInfo[]>([])

  useEffect(() => {
    getArtifacts(jobId)
      .then(setArtifacts)
      .catch(() => {/* non-fatal */})
  }, [jobId])

  if (artifacts.length === 0) return null

  return (
    <div className="flex flex-col gap-1.5">
      {artifacts.map(a => (
        <a
          key={a.format}
          href={a.url}
          download
          className="block w-full bg-[#1e1e1e] border border-[#2a2a2a] rounded-lg px-3 py-2.5 text-sm text-[#e5e7eb] font-medium hover:border-[#555] hover:text-white transition-colors no-underline"
        >
          {FORMAT_LABELS[a.format] ?? a.format}
        </a>
      ))}
    </div>
  )
}
