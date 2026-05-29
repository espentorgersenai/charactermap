export type ColorHint = 'blue' | 'red' | 'green' | 'amber' | 'violet' | 'slate'
export type Importance = 'protagonist' | 'major' | 'supporting' | 'minor'
export type RelationshipType =
  | 'alliance' | 'family' | 'romantic' | 'antagonism'
  | 'professional' | 'mentorship' | 'criminal'
export type SpoilerLevel = 0 | 1 | 2 | 3

export interface Faction {
  id: string
  label: string
  description: string
  color_hint: ColorHint
}

export interface ActorInfo {
  name: string
  tmdb_person_id: number
  headshot_url: string | null
}

export interface CreatorInfo {
  kind: 'author' | 'director'
  name: string
  tmdb_person_id?: number | null
  headshot_url?: string | null
}

export interface Character {
  id: string
  name: string
  role: string
  description: string
  faction_id: string | null
  importance: Importance
  is_deceased_in_work: boolean
  spoiler_level: SpoilerLevel | null
  actor?: ActorInfo
  home_region?: string | null
  is_pov?: boolean
}

export interface Relationship {
  from_id: string
  to_id: string
  type: RelationshipType
  label: string
  spoiler_level: SpoilerLevel | null
}

export interface CharacterMap {
  title: string
  subtitle: string
  blurb: string
  spoiler_mode: 'full'
  setting_preamble?: string
  factions: Faction[]
  characters: Character[]
  relationships: Relationship[]
  coverage_note?: string
  notes: string
  creator?: CreatorInfo | null
  source_url?: string | null
}
