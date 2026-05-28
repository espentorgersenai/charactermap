import { useMemo, useState } from 'react'
import type { Character, CharacterMap } from '../types/characterMap'
import { resolveRegion, WESTEROS_ANCHORS } from '../geographic/westeros'

interface Props {
  charMap: CharacterMap
  backdropSrc: string
}

interface Placed {
  character: Character
  /** Anchor x fraction (0–1) of the backdrop. */
  ax: number
  /** Anchor y fraction (0–1) of the backdrop. */
  ay: number
  /** Per-character offset in pixels relative to the anchor center. */
  ox: number
  oy: number
  regionLabel: string
}

const CARD_W = 220
const CARD_H = 64
const TILE_GAP_X = CARD_W + 10
const TILE_GAP_Y = CARD_H + 8
const TILE_COLS = 3

/** Lay characters around their region anchor in a small grid. */
function placeAroundAnchor(
  chars: Character[],
  ax: number,
  ay: number,
  regionLabel: string,
): Placed[] {
  return chars.map((c, i) => {
    const col = i % TILE_COLS
    const row = Math.floor(i / TILE_COLS)
    // Center the grid horizontally on the anchor, stack downward
    const ox = (col - (TILE_COLS - 1) / 2) * TILE_GAP_X
    const oy = row * TILE_GAP_Y
    return { character: c, ax, ay, ox, oy, regionLabel }
  })
}

export function GeographicMapView({ charMap, backdropSrc }: Props) {
  const { placed, unplaced } = useMemo(() => {
    const buckets = new Map<string, Character[]>()
    const unplaced: Character[] = []
    for (const c of charMap.characters) {
      const anchor = resolveRegion(c.home_region)
      if (!anchor) {
        unplaced.push(c)
        continue
      }
      const list = buckets.get(anchor.id) ?? []
      list.push(c)
      buckets.set(anchor.id, list)
    }
    const placed: Placed[] = []
    for (const anchor of WESTEROS_ANCHORS) {
      const list = buckets.get(anchor.id)
      if (!list || list.length === 0) continue
      placed.push(...placeAroundAnchor(list, anchor.x, anchor.y, anchor.label))
    }
    return { placed, unplaced }
  }, [charMap])

  const [size, setSize] = useState<{ w: number; h: number } | null>(null)

  return (
    <div className="w-full h-full overflow-auto bg-[#0b0b0b]">
      <div className="relative inline-block min-w-full">
        <img
          src={backdropSrc}
          alt="World map backdrop"
          onLoad={(e) => {
            const el = e.currentTarget
            setSize({ w: el.naturalWidth, h: el.naturalHeight })
          }}
          className="block max-w-none select-none pointer-events-none"
          draggable={false}
          style={{ width: 'min(2400px, 100%)' }}
        />
        {size && (
          <>
            {WESTEROS_ANCHORS.map((a) => (
              <div
                key={`label-${a.id}`}
                className="absolute pointer-events-none text-[10px] uppercase tracking-[0.18em] font-bold text-white/70 drop-shadow-[0_0_3px_rgba(0,0,0,0.9)]"
                style={{
                  left: `calc(${a.x * 100}% - 60px)`,
                  top: `calc(${a.y * 100}% - 78px)`,
                  width: '120px',
                  textAlign: 'center',
                }}
              >
                {a.label}
              </div>
            ))}
            {placed.map((p) => (
              <CharacterPin key={p.character.id} placed={p} />
            ))}
          </>
        )}
      </div>
      {unplaced.length > 0 && (
        <div className="sticky bottom-0 bg-[#161616]/95 backdrop-blur border-t border-[#222] p-4">
          <p className="text-[11px] uppercase tracking-[0.2em] text-[#777] mb-3">
            Unplaced ({unplaced.length})
          </p>
          <div className="flex flex-wrap gap-2">
            {unplaced.map((c) => (
              <UnplacedChip key={c.id} character={c} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function CharacterPin({ placed }: { placed: Placed }) {
  const c = placed.character
  const initials = c.name
    .split(' ')
    .slice(0, 2)
    .map((w) => w[0])
    .join('')
    .toUpperCase()
  return (
    <div
      className="absolute flex items-center gap-2 bg-[#1e1e1e]/95 backdrop-blur rounded-[10px] border border-white/15 px-2 py-1.5 shadow-lg"
      style={{
        left: `calc(${placed.ax * 100}% + ${placed.ox}px - ${CARD_W / 2}px)`,
        top: `calc(${placed.ay * 100}% + ${placed.oy}px)`,
        width: `${CARD_W}px`,
      }}
      title={`${c.name} — ${placed.regionLabel}`}
    >
      <div className="flex-shrink-0">
        {c.actor?.headshot_url && c.actor?.tmdb_person_id ? (
          <a
            href={`https://www.themoviedb.org/person/${c.actor.tmdb_person_id}`}
            target="_blank"
            rel="noopener noreferrer"
            className="block w-10 h-10 rounded-full overflow-hidden ring-1 ring-white/20 hover:ring-white/50 transition"
          >
            <img
              src={c.actor.headshot_url}
              alt={c.actor.name}
              draggable={false}
              loading="lazy"
              className="w-full h-full object-cover"
            />
          </a>
        ) : (
          <div className="w-10 h-10 rounded-full flex items-center justify-center text-xs font-bold text-white bg-[#3a3a3a]">
            {initials}
          </div>
        )}
      </div>
      <div className="min-w-0">
        <div className="text-[12px] font-semibold text-white leading-tight truncate">
          {c.name}
        </div>
        <div className="text-[10px] text-[#aaa] leading-tight truncate">
          {c.role || placed.regionLabel}
        </div>
      </div>
    </div>
  )
}

function UnplacedChip({ character: c }: { character: Character }) {
  const initials = c.name
    .split(' ')
    .slice(0, 2)
    .map((w) => w[0])
    .join('')
    .toUpperCase()
  return (
    <div
      className="flex items-center gap-2 bg-[#1e1e1e] rounded-full border border-white/10 pl-1 pr-3 py-1"
      title={c.home_region ?? 'No region'}
    >
      {c.actor?.headshot_url ? (
        <img
          src={c.actor.headshot_url}
          alt={c.actor.name}
          className="w-6 h-6 rounded-full object-cover"
          loading="lazy"
        />
      ) : (
        <div className="w-6 h-6 rounded-full flex items-center justify-center text-[9px] font-bold text-white bg-[#444]">
          {initials}
        </div>
      )}
      <span className="text-[11px] text-white/85">{c.name}</span>
    </div>
  )
}
