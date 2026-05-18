import { ResolveCandidate } from '../api/client'

interface Props {
  candidate: ResolveCandidate
  onNotThis: () => void
}

export default function ResolveBanner({ candidate, onNotThis }: Props) {
  return (
    <div className="flex items-center justify-between p-3 bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-lg text-sm">
      <span className="text-blue-900 dark:text-blue-200">
        Generating for <em>{candidate.title}</em>
        {candidate.author ? ` by ${candidate.author}` : ''}
        {candidate.year ? ` (${candidate.year})` : ''}
      </span>
      <button
        onClick={onNotThis}
        className="text-blue-600 dark:text-blue-400 hover:underline text-xs ml-4 shrink-0"
      >
        not this?
      </button>
    </div>
  )
}
