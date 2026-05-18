import { ResolveCandidate } from '../api/client'

interface Props { candidate: ResolveCandidate; onNotThis: () => void }

export default function ResolveBanner({ candidate, onNotThis }: Props) {
  return (
    <div className="flex items-center justify-between gap-4 py-4" style={{ borderBottom: '1px solid rgba(212,175,55,0.2)' }}>
      <div>
        <span style={{ color: '#D4AF37' }}>✦</span>
        <span className="text-sm text-award-cream ml-2 font-medium italic">{candidate.title}</span>
        {(candidate.author || candidate.year) && (
          <span className="text-xs text-award-cream-dim ml-2">
            {candidate.author ? `by ${candidate.author}` : ''}{candidate.year ? ` (${candidate.year})` : ''}
          </span>
        )}
      </div>
      <button onClick={onNotThis} className="text-xs text-award-cream-dim hover:text-award-cream-muted underline shrink-0 transition-colors">
        not this?
      </button>
    </div>
  )
}
