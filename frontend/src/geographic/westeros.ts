// Westeros / Essos region-to-pixel anchors for the Known World backdrop.
//
// Coordinates are expressed as fractions of the backdrop image so the same
// map renders at any size. The reference image is the Adam Whitehead
// "Known World" map (2014) dropped at `public/maps/westeros.jpg` — see
// frontend/public/maps/README.md for the exact placement.
//
// Each anchor is the center point of the region's cluster. The placement
// component fans character cards out in a small grid around the anchor so
// regions with many characters (Crownlands, North) don't collapse onto a
// single pixel.

export interface RegionAnchor {
  /** Canonical region id used as a normalization target. */
  id: string
  /** Human-readable label for tooltips and the legend. */
  label: string
  /** X position as a fraction of backdrop width (0–1). */
  x: number
  /** Y position as a fraction of backdrop height (0–1). */
  y: number
  /** Free-form synonyms the LLM might emit. Lowercase, no leading articles. */
  aliases: string[]
}

export const WESTEROS_ANCHORS: RegionAnchor[] = [
  {
    id: 'the-north',
    label: 'The North',
    x: 0.12, y: 0.22,
    aliases: ['north', 'winterfell', 'stark lands', 'the north'],
  },
  {
    id: 'beyond-the-wall',
    label: 'Beyond the Wall',
    x: 0.13, y: 0.11,
    aliases: [
      'beyond the wall', 'lands of always winter', 'wildlings', 'free folk',
      'frostfangs', 'the wall',
    ],
  },
  {
    id: 'the-vale',
    label: 'The Vale',
    x: 0.20, y: 0.36,
    aliases: ['vale', 'vale of arryn', 'eyrie', 'arryn', 'the vale'],
  },
  {
    id: 'the-riverlands',
    label: 'The Riverlands',
    x: 0.14, y: 0.42,
    aliases: [
      'riverlands', 'tully', 'riverrun', 'twins', 'frey', 'harrenhal',
      'the riverlands',
    ],
  },
  {
    id: 'the-westerlands',
    label: 'The Westerlands',
    x: 0.10, y: 0.50,
    aliases: [
      'westerlands', 'casterly rock', 'lannister', 'lannisport', 'the westerlands',
    ],
  },
  {
    id: 'the-iron-islands',
    label: 'The Iron Islands',
    x: 0.07, y: 0.42,
    aliases: ['iron islands', 'pyke', 'greyjoy', 'ironborn', 'the iron islands'],
  },
  {
    id: 'the-reach',
    label: 'The Reach',
    x: 0.12, y: 0.58,
    aliases: ['reach', 'highgarden', 'tyrell', 'oldtown', 'the reach'],
  },
  {
    id: 'the-stormlands',
    label: 'The Stormlands',
    x: 0.18, y: 0.55,
    aliases: ['stormlands', "storm's end", 'baratheon', 'the stormlands'],
  },
  {
    id: 'the-crownlands',
    label: 'The Crownlands',
    x: 0.20, y: 0.46,
    aliases: [
      'crownlands', "king's landing", 'kings landing', 'red keep', 'iron throne',
      'the crownlands',
    ],
  },
  {
    id: 'dragonstone',
    label: 'Dragonstone',
    x: 0.23, y: 0.46,
    aliases: ['dragonstone', 'targaryen seat'],
  },
  {
    id: 'dorne',
    label: 'Dorne',
    x: 0.18, y: 0.66,
    aliases: ['dorne', 'sunspear', 'martell', 'water gardens'],
  },
  {
    id: 'essos-free-cities',
    label: 'Essos — Free Cities',
    x: 0.36, y: 0.46,
    aliases: [
      'free cities', 'pentos', 'braavos', 'lys', 'tyrosh', 'myr', 'volantis',
      'qohor', 'norvos', 'lorath', 'essos',
    ],
  },
  {
    id: 'dothraki-sea',
    label: 'Essos — Dothraki Sea',
    x: 0.54, y: 0.46,
    aliases: ['dothraki sea', 'dothraki', 'vaes dothrak'],
  },
  {
    id: 'slavers-bay',
    label: "Essos — Slaver's Bay",
    x: 0.50, y: 0.62,
    aliases: [
      "slaver's bay", 'slavers bay', 'meereen', 'yunkai', 'astapor',
      'bay of dragons',
    ],
  },
  {
    id: 'further-east',
    label: 'Essos — Further East',
    x: 0.78, y: 0.50,
    aliases: [
      'asshai', 'qarth', 'jade sea', 'yi ti', 'shadow lands', "shadow lands",
      'further east',
    ],
  },
  {
    id: 'summer-isles',
    label: 'Summer Isles',
    x: 0.28, y: 0.80,
    aliases: ['summer isles', 'summer islands'],
  },
]

const _LEADING_ARTICLE = /^(the|a|an)\s+/i

function _normalize(raw: string): string {
  return raw
    .toLowerCase()
    .replace(_LEADING_ARTICLE, '')
    .replace(/[^a-z0-9\s]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}

/** Resolve a free-form home_region string to a RegionAnchor.
 *
 * Match priority: exact alias → substring containment. Returns null for
 * regions we don't know (caller renders them in an "Unplaced" gutter).
 */
export function resolveRegion(raw: string | null | undefined): RegionAnchor | null {
  if (!raw) return null
  const n = _normalize(raw)
  if (!n) return null
  for (const a of WESTEROS_ANCHORS) {
    if (a.aliases.some(alias => _normalize(alias) === n)) return a
  }
  for (const a of WESTEROS_ANCHORS) {
    if (a.aliases.some(alias => n.includes(_normalize(alias)))) return a
  }
  return null
}
