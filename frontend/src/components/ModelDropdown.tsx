const MODELS = [
  { id: 'claude-sonnet-4-6', label: 'Claude Sonnet 4.6' },
  { id: 'claude-opus-4-7', label: 'Claude Opus 4.7' },
  { id: 'claude-haiku-4-5-20251001', label: 'Claude Haiku 4.5' },
  { id: 'gpt-5.5', label: 'GPT-5.5' },
  { id: 'gemini-2.5-pro', label: 'Gemini 2.5 Pro' },
] as const

interface Props {
  value: string
  onChange: (model: string) => void
}

export default function ModelDropdown({ value, onChange }: Props) {
  return (
    <div>
      <label className="block text-sm font-medium mb-1">Model</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
      >
        {MODELS.map((m) => (
          <option key={m.id} value={m.id}>{m.label}</option>
        ))}
      </select>
    </div>
  )
}
