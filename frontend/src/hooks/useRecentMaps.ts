const STORAGE_KEY = 'charmap_recent_maps'
const MAX_ENTRIES = 10

export interface RecentMapEntry {
  jobId: string
  title: string
  date: string // ISO string
  thumbnailUrl?: string
}

export function useRecentMaps() {
  function getAll(): RecentMapEntry[] {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      return raw ? (JSON.parse(raw) as RecentMapEntry[]) : []
    } catch {
      return []
    }
  }

  function addRecentMap(entry: RecentMapEntry) {
    try {
      const existing = getAll().filter((e) => e.jobId !== entry.jobId)
      const updated = [entry, ...existing].slice(0, MAX_ENTRIES)
      localStorage.setItem(STORAGE_KEY, JSON.stringify(updated))
    } catch {
      // ignore storage errors
    }
  }

  return { recentMaps: getAll(), addRecentMap }
}
