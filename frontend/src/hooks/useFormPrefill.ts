const STORAGE_KEY = 'charmap_form_prefs'

export const CHARACTER_CAPS = [10, 20, 30, 40, 50, 100, 150] as const
export type CharacterCap = typeof CHARACTER_CAPS[number]

interface FormPrefs {
  model: string
  formats: string[]
  workType: 'book' | 'film_tv'
  characterCap: CharacterCap
}

const DEFAULT_PREFS: FormPrefs = {
  model: 'claude-sonnet-4-6',
  formats: ['interactive'],
  workType: 'book',
  characterCap: 20,
}

function isValidCap(v: unknown): v is CharacterCap {
  return typeof v === 'number' && (CHARACTER_CAPS as readonly number[]).includes(v)
}

export function useFormPrefill() {
  function load(): FormPrefs {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (!raw) return DEFAULT_PREFS
      const parsed = JSON.parse(raw) as Partial<FormPrefs>
      return {
        model: parsed.model ?? DEFAULT_PREFS.model,
        formats:
          Array.isArray(parsed.formats) && parsed.formats.length > 0
            ? parsed.formats
            : DEFAULT_PREFS.formats,
        workType: parsed.workType === 'film_tv' ? 'film_tv' : 'book',
        characterCap: isValidCap(parsed.characterCap) ? parsed.characterCap : DEFAULT_PREFS.characterCap,
      }
    } catch {
      return DEFAULT_PREFS
    }
  }

  function save(prefs: FormPrefs) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs))
    } catch {
      // ignore storage errors (e.g., private browsing)
    }
  }

  return { load, save }
}
