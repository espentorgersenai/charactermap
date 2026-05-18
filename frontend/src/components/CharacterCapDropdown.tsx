import { CHARACTER_CAPS, type CharacterCap } from '../hooks/useFormPrefill'

interface Props {
  value: CharacterCap
  onChange: (v: CharacterCap) => void
}

// Approximate cost / time hints relative to cap=20 baseline (~$0.06, ~50s on Sonnet).
// Not precise — the LLM self-limits well below the cap most of the time, so
// these are upper bounds shown to set expectations.
const HINTS: Record<CharacterCap, string> = {
  10: 'fastest · ~$0.04',
  20: 'default · ~$0.06',
  30: 'denser · ~$0.08',
  40: 'rich · ~$0.10',
  50: 'maximum · ~$0.12',
}

export default function CharacterCapDropdown({ value, onChange }: Props) {
  return (
    <div>
      <label className="block text-sm font-medium mb-1">
        Character cap{' '}
        <span className="text-gray-500 font-normal">
          (max characters on the map · higher = more cost + time)
        </span>
      </label>
      <select
        value={value}
        onChange={e => onChange(Number(e.target.value) as CharacterCap)}
        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
      >
        {CHARACTER_CAPS.map(cap => (
          <option key={cap} value={cap}>
            {cap} characters — {HINTS[cap]}
          </option>
        ))}
      </select>
    </div>
  )
}
