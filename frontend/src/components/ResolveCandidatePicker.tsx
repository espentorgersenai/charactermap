import { ResolveCandidate } from '../api/client'

interface Props {
  candidates: ResolveCandidate[]
  selected: ResolveCandidate | null
  onSelect: (candidate: ResolveCandidate) => void
}

export default function ResolveCandidatePicker({ candidates, selected, onSelect }: Props) {
  if (candidates.length === 0) {
    return (
      <div className="p-4 text-center text-sm text-gray-500 bg-gray-50 dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700">
        No results — try a different title or add the author&apos;s name.
      </div>
    )
  }

  return (
    <div>
      <p className="text-sm font-medium mb-2 text-gray-700 dark:text-gray-300">Select a match:</p>
      <ul className="space-y-2">
        {candidates.slice(0, 5).map((c) => (
          <li key={c.id}>
            <button
              onClick={() => onSelect(c)}
              className={`w-full text-left flex items-start gap-3 p-3 rounded-lg border transition-colors ${
                selected?.id === c.id
                  ? 'border-blue-500 bg-blue-50 dark:bg-blue-950'
                  : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-500 bg-white dark:bg-gray-800'
              }`}
            >
              {/* Cover image */}
              {c.cover_url ? (
                <img
                  src={c.cover_url}
                  alt={c.title}
                  className="w-12 h-16 object-cover rounded shrink-0"
                />
              ) : (
                <div className="w-12 h-16 bg-gray-100 dark:bg-gray-700 rounded shrink-0 flex items-center justify-center text-gray-400 text-xs">
                  No cover
                </div>
              )}

              {/* Info */}
              <div className="flex-1 min-w-0">
                <p className="font-medium text-sm truncate">{c.title}</p>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {c.year && `${c.year} · `}
                  {c.author || c.director}
                </p>
                {/* Adaptation badge */}
                {c.adaptation && (
                  <p className="text-xs text-green-700 dark:text-green-400 mt-1">
                    🎬 Adapted: {c.adaptation.title}
                    {c.adaptation.year ? ` (${c.adaptation.year})` : ''}
                    {c.adaptation.rating ? ` · ★ ${c.adaptation.rating.toFixed(1)}` : ''}
                  </p>
                )}
                {/* Confidence indicator */}
                <p className="text-xs text-gray-400 mt-0.5">
                  {(c.confidence_score * 100).toFixed(0)}% match
                </p>
              </div>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
