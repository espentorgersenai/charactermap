import { useState } from 'react'
import { useReactFlow } from '@xyflow/react'
import { toPng, toSvg } from 'html-to-image'
import { uploadArtifact } from '../api/client'

const CANVAS_BG = '#111111'

// Title → safe filename slug. Mirror of backend _slugify in artifacts.py.
function slugify(s: string): string {
  const base = (s || '')
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^a-zA-Z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .toLowerCase()
  return base.slice(0, 60) || 'character-map'
}

export function ExportMenu({ jobId, title }: { jobId: string; title: string }) {
  const { toObject } = useReactFlow()
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)
  const slug = slugify(title)
  const fname = (ext: string) => `${slug}-character-map.${ext}`

  function download(dataUrl: string, filename: string) {
    const a = document.createElement('a')
    a.href = dataUrl
    a.download = filename
    a.click()
  }

  function getViewport(): HTMLElement {
    const el = document.querySelector('.react-flow__viewport') as HTMLElement | null
    if (!el) throw new Error('React Flow viewport not found')
    return el
  }

  const exportPng = async () => {
    setBusy('png')
    try {
      const dataUrl = await toPng(getViewport(), { pixelRatio: 2, backgroundColor: CANVAS_BG })
      download(dataUrl, fname('png'))
      const blob = await (await fetch(dataUrl)).blob()
      await uploadArtifact(jobId, 'png', blob)
    } finally {
      setBusy(null)
      setOpen(false)
    }
  }

  const exportSvg = async () => {
    setBusy('svg')
    try {
      const dataUrl = await toSvg(getViewport(), { backgroundColor: CANVAS_BG })
      download(dataUrl, fname('svg'))
      const blob = await (await fetch(dataUrl)).blob()
      await uploadArtifact(jobId, 'svg', blob)
    } finally {
      setBusy(null)
      setOpen(false)
    }
  }

  const exportJson = async () => {
    setBusy('json')
    try {
      const obj = toObject()
      const json = JSON.stringify(obj, null, 2)
      download(
        `data:application/json;charset=utf-8,${encodeURIComponent(json)}`,
        fname('charmap.json'),
      )
      await uploadArtifact(jobId, 'json', new Blob([json], { type: 'application/json' }))
    } finally {
      setBusy(null)
      setOpen(false)
    }
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(v => !v)}
        className="px-4 py-2 text-sm font-semibold text-[#e5e7eb] border-[1.5px] border-[#444] rounded-lg bg-transparent hover:border-[#666] transition-colors"
      >
        Export ▾
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute top-full mt-1 left-0 bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg overflow-hidden z-20 min-w-[150px] shadow-xl">
            {[
              { key: 'png',  label: '🖼 PNG (2×)',  fn: exportPng  },
              { key: 'svg',  label: '↗ SVG',        fn: exportSvg  },
              { key: 'json', label: '{ } JSON',      fn: exportJson },
            ].map(({ key, label, fn }) => (
              <button
                key={key}
                onClick={fn}
                disabled={busy !== null}
                className="w-full px-4 py-2.5 text-left text-sm text-[#e5e7eb] hover:bg-[#242424] disabled:opacity-50 transition-colors"
              >
                {busy === key ? '…' : label}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
