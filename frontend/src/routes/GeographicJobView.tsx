import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { getJob } from '../api/client'
import { GeographicMapView } from '../components/GeographicMapView'
import type { CharacterMap } from '../types/characterMap'

const BACKDROP_SRC = '/maps/westeros.jpg'

export default function GeographicJobView() {
  const { id } = useParams<{ id: string }>()
  const [charMap, setCharMap] = useState<CharacterMap | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    let cancelled = false
    getJob(id)
      .then((j) => {
        if (cancelled) return
        if (j.status !== 'done' || !j.character_map) {
          setError(`Job not ready (status: ${j.status}).`)
          return
        }
        setCharMap(j.character_map as unknown as CharacterMap)
      })
      .catch((e) => !cancelled && setError(String(e)))
    return () => {
      cancelled = true
    }
  }, [id])

  if (error) {
    return (
      <main className="max-w-3xl mx-auto px-5 py-8 text-award-cream">
        <Link to="/" className="text-sm text-award-gold hover:text-award-gold-light">← Home</Link>
        <p className="mt-6">{error}</p>
      </main>
    )
  }

  if (!charMap) {
    return (
      <main className="max-w-3xl mx-auto px-5 py-8 text-award-cream">
        <p>Loading map…</p>
      </main>
    )
  }

  return (
    <div className="flex h-full overflow-hidden">
      <div className="flex-1 min-w-0">
        <GeographicMapView charMap={charMap} backdropSrc={BACKDROP_SRC} />
      </div>
      <div className="w-[210px] flex-shrink-0 bg-[#161616] border-l border-[#222] p-4 overflow-y-auto flex flex-col gap-4">
        <Link to="/" className="text-[11px] text-[#555] hover:text-[#888]">← Home</Link>
        <Link to={`/job/${id}`} className="text-[11px] text-[#555] hover:text-[#888]">
          ← Faction view
        </Link>
        <div className="text-[11px] text-[#777] leading-snug">
          Geographic view: characters anchored at their home region on the
          Known World map.
        </div>
      </div>
    </div>
  )
}
