import { ResolveCandidate } from '../api/client'

interface Props {
  candidates: ResolveCandidate[]
  selected: ResolveCandidate | null
  onSelect: (candidate: ResolveCandidate) => void
}

export default function ResolveCandidatePicker({ candidates, selected, onSelect }: Props) {
  if (candidates.length === 0) return (
    <p className="text-sm text-award-cream-dim py-4">No results — try a different title or add the author's name.</p>
  )
  return (
    <div>
      <p className="text-[10px] uppercase tracking-[0.2em] text-award-cream-dim mb-4">Select a match</p>
      <ul className="space-y-0">
        {candidates.slice(0, 5).map((c) => (
          <li key={c.id}>
            <button
              onClick={() => onSelect(c)}
              className="w-full text-left flex items-center gap-4 py-4 transition-all group"
              style={{
                borderBottom: '1px solid rgba(61,48,32,0.5)',
                ...(selected?.id === c.id ? { borderBottomColor: 'rgba(212,175,55,0.3)' } : {}),
              }}
            >
              {c.cover_url ? (
                <img src={c.cover_url} alt={c.title} className="w-10 h-14 object-cover rounded shrink-0 opacity-80" />
              ) : (
                <div className="w-10 h-14 rounded shrink-0 flex items-center justify-center text-award-cream-dim text-xs" style={{ background: 'rgba(28,24,16,0.8)', border: '1px solid rgba(61,48,32,0.5)' }}>
                  —
                </div>
              )}
              <div className="flex-1 min-w-0">
                <p className={`text-sm font-medium truncate transition-colors ${selected?.id === c.id ? 'text-award-gold-light' : 'text-award-cream group-hover:text-award-cream'}`}>
                  {selected?.id === c.id && <span className="text-award-gold mr-1.5">✦</span>}
                  {c.title}
                </p>
                <p className="text-xs text-award-cream-dim mt-0.5">{c.year && `${c.year} · `}{c.author || c.director}</p>
                {c.adaptation && (
                  <p className="text-xs mt-1" style={{ color: '#A88C2A' }}>🎬 {c.adaptation.title}{c.adaptation.year ? ` (${c.adaptation.year})` : ''}</p>
                )}
              </div>
              <span className="text-[10px] text-award-cream-dim shrink-0">{(c.confidence_score * 100).toFixed(0)}%</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
