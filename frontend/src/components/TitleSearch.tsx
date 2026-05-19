import { useState, KeyboardEvent } from 'react'

interface Props {
  onSearch: (query: string) => void
  isLoading: boolean
  disabled?: boolean
  initialValue?: string
}

export default function TitleSearch({ onSearch, isLoading, disabled, initialValue }: Props) {
  const [query, setQuery] = useState(initialValue ?? '')

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter' && query.trim()) onSearch(query.trim())
  }

  return (
    <div className="flex items-end gap-4">
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Enter a title…"
        disabled={disabled || isLoading}
        className="input-underline flex-1 text-lg disabled:opacity-40"
        aria-label="Title search"
      />
      <button
        onClick={() => query.trim() && onSearch(query.trim())}
        disabled={!query.trim() || isLoading || disabled}
        className="btn-gold-metal px-7 py-2.5 rounded-full text-sm disabled:opacity-35 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-award-gold"
        style={
          !query.trim() || isLoading || disabled
            ? { background: 'rgba(28,24,16,0.7)', border: '1px solid rgba(61,48,32,0.6)', color: '#7A6A54', animation: 'none', boxShadow: 'none' }
            : undefined
        }
      >
        {isLoading ? 'Searching…' : 'Search'}
      </button>
    </div>
  )
}
