import { useState, KeyboardEvent } from 'react'

interface Props {
  onSearch: (query: string) => void
  isLoading: boolean
  disabled?: boolean
}

export default function TitleSearch({ onSearch, isLoading, disabled }: Props) {
  const [query, setQuery] = useState('')

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter' && query.trim()) {
      onSearch(query.trim())
    }
  }

  function handleClick() {
    if (query.trim()) onSearch(query.trim())
  }

  return (
    <div className="flex gap-2">
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Enter a book or film title…"
        disabled={disabled || isLoading}
        className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
      />
      <button
        onClick={handleClick}
        disabled={!query.trim() || isLoading || disabled}
        className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {isLoading ? 'Searching…' : 'Search'}
      </button>
    </div>
  )
}
