import { CHARACTER_CAPS, type CharacterCap } from '../hooks/useFormPrefill'

const HINTS: Record<CharacterCap, string> = {
  10: 'fastest · ~$0.04',
  20: 'default · ~$0.06',
  30: 'denser · ~$0.08',
  40: 'rich · ~$0.10',
  50: 'maximum · ~$0.12',
  100: 'epic · ~$0.30',
  150: 'special · ~$0.50',
}

interface Props { value: CharacterCap; onChange: (v: CharacterCap) => void }

export default function CharacterCapDropdown({ value, onChange }: Props) {
  return (
    <div className="py-1">
      <label className="block text-[10px] uppercase tracking-[0.2em] text-award-cream-dim mb-1">
        Character cap <span className="normal-case opacity-60">(higher = more detail)</span>
      </label>
      <select
        value={value}
        onChange={(e) => onChange(Number(e.target.value) as CharacterCap)}
        className="input-underline appearance-none cursor-pointer"
      >
        {CHARACTER_CAPS.map((cap) => (
          <option key={cap} value={cap} style={{ background: '#1C1810' }}>
            {cap} chars — {HINTS[cap]}
          </option>
        ))}
      </select>
    </div>
  )
}
