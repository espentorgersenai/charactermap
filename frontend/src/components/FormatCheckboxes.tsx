const FORMATS = [
  { id: 'interactive', label: 'Interactive map' },
  { id: 'png',         label: 'PNG'             },
  { id: 'svg',         label: 'SVG'             },
  { id: 'markdown',    label: 'Markdown'        },
  { id: 'pdf',         label: 'PDF'             },
  { id: 'json',        label: 'JSON'            },
] as const

interface Props { selected: string[]; onChange: (formats: string[]) => void }

export default function FormatCheckboxes({ selected, onChange }: Props) {
  function toggle(id: string) {
    onChange(selected.includes(id) ? selected.filter((f) => f !== id) : [...selected, id])
  }
  return (
    <fieldset>
      <legend className="block text-[10px] uppercase tracking-[0.2em] text-award-cream-dim mb-3">
        Output formats <span className="normal-case opacity-60">(select at least one)</span>
      </legend>
      <div className="flex flex-wrap gap-2">
        {FORMATS.map((f) => {
          const on = selected.includes(f.id)
          return (
            <button
              key={f.id}
              type="button"
              onClick={() => toggle(f.id)}
              aria-pressed={on}
              className="px-3.5 py-1.5 rounded-full text-xs font-medium transition-all duration-200"
              style={
                on
                  ? { background: 'rgba(212,175,55,0.14)', border: '1px solid rgba(212,175,55,0.5)', color: '#E2CA78', boxShadow: '0 0 10px rgba(212,175,55,0.12)' }
                  : { background: 'transparent', border: '1px solid rgba(61,48,32,0.8)', color: '#C4B49A' }
              }
            >
              {f.label}
            </button>
          )
        })}
      </div>
    </fieldset>
  )
}
