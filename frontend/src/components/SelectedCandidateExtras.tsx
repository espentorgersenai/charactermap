import { ResolveCandidate } from '../api/client'

interface Props {
  candidate: ResolveCandidate
  season: number | null
  onSeasonChange: (n: number | null) => void
  onClearAdaptation: () => void
}

// Renders the supplementary controls that appear once a candidate is selected:
//   • the 🎬 adaptation chip with an × to clear a wrong link (e.g. when a book
//     resolver pairs "Bomberen" with the Boston Strong film)
//   • a Season dropdown when the work is a TV series, so the user can pin
//     generation to a specific season (cast comes from /tv/{id}/season/{n}/
//     credits and the prompt is told to focus on that season).
export default function SelectedCandidateExtras({
  candidate, season, onSeasonChange, onClearAdaptation,
}: Props) {
  const seasons = candidate.seasons ?? []
  const adapt = candidate.adaptation
  const isTv =
    candidate.media_type === 'tv' ||
    candidate.adaptation?.media_type === 'tv'
  const showSeasonDropdown = isTv && seasons.length > 0

  if (!adapt && !showSeasonDropdown) return null

  return (
    <div className="mt-5 space-y-4">
      {adapt && (
        <div className="flex items-center gap-2">
          <span className="text-[10px] uppercase tracking-[0.2em] text-award-cream-dim">
            Linked adaptation
          </span>
          <span
            className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full"
            style={{
              background: 'rgba(28,24,16,0.8)',
              border: '1px solid rgba(168,140,42,0.4)',
              color: '#A88C2A',
            }}
          >
            <span aria-hidden>🎬</span>
            <span className="truncate max-w-[260px]">
              {adapt.title}{adapt.year ? ` (${adapt.year})` : ''}
            </span>
            <button
              onClick={onClearAdaptation}
              aria-label="Remove linked adaptation"
              title="Remove linked adaptation"
              className="ml-1 -mr-1 w-4 h-4 flex items-center justify-center rounded-full transition-colors hover:bg-award-crimson/30 hover:text-award-cream"
              style={{ color: 'rgba(196,180,154,0.7)' }}
            >
              ×
            </button>
          </span>
        </div>
      )}

      {showSeasonDropdown && (
        <div>
          <label className="block text-[10px] uppercase tracking-[0.2em] text-award-cream-dim mb-1">
            Season
          </label>
          <select
            value={season ?? ''}
            onChange={(e) => {
              const v = e.target.value
              onSeasonChange(v === '' ? null : parseInt(v, 10))
            }}
            className="bg-transparent text-award-cream border-b border-award-gold-dim focus:border-award-gold focus:outline-none py-1 text-sm w-full"
          >
            <option value="">All seasons</option>
            {seasons.map((s) => (
              <option key={s.number} value={s.number}>
                {s.name}{s.year ? ` · ${s.year}` : ''}
                {s.episode_count ? ` · ${s.episode_count} ep` : ''}
              </option>
            ))}
          </select>
          <p className="text-[10px] text-award-cream-dim mt-1">
            Pin to one season — narrows cast and storyline to that arc.
          </p>
        </div>
      )}
    </div>
  )
}
