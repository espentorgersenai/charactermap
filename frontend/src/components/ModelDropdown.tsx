const MODELS = [
  { id: 'claude-sonnet-4-6', label: 'Claude Sonnet 4.6' },
  { id: 'claude-opus-4-7',   label: 'Claude Opus 4.7'   },
  { id: 'gpt-5.5',           label: 'GPT-5.5'            },
  { id: 'gemini-2.5-pro',    label: 'Gemini 2.5 Pro'     },
] as const

interface Props { value: string; onChange: (model: string) => void }

export default function ModelDropdown({ value, onChange }: Props) {
  return (
    <div className="py-1">
      <label className="block text-[10px] uppercase tracking-[0.2em] text-award-cream-dim mb-1">
        Model
      </label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="input-underline appearance-none cursor-pointer"
      >
        {MODELS.map((m) => (
          <option key={m.id} value={m.id} style={{ background: '#1C1810' }}>
            {m.label}
          </option>
        ))}
      </select>
    </div>
  )
}
