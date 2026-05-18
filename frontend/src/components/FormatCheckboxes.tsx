const FORMATS = [
  { id: 'interactive', label: 'Interactive map' },
  { id: 'png', label: 'PNG image' },
  { id: 'svg', label: 'SVG vector' },
  { id: 'markdown', label: 'Markdown' },
  { id: 'pdf', label: 'PDF' },
  { id: 'json', label: 'JSON' },
] as const

interface Props {
  selected: string[]
  onChange: (formats: string[]) => void
}

export default function FormatCheckboxes({ selected, onChange }: Props) {
  function toggle(id: string) {
    onChange(selected.includes(id) ? selected.filter((f) => f !== id) : [...selected, id])
  }

  return (
    <div>
      <label className="block text-sm font-medium mb-2">
        Output formats <span className="text-gray-500">(select at least one)</span>
      </label>
      <div className="flex flex-wrap gap-2">
        {FORMATS.map((f) => (
          <label key={f.id} className="flex items-center gap-1.5 cursor-pointer">
            <input
              type="checkbox"
              checked={selected.includes(f.id)}
              onChange={() => toggle(f.id)}
              className="rounded"
            />
            <span className="text-sm">{f.label}</span>
          </label>
        ))}
      </div>
    </div>
  )
}
