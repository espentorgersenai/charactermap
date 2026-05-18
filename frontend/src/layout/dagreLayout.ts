import dagre from 'dagre'
import type { Edge, Node } from '@xyflow/react'
import type { CharacterMap, Character, Faction, Relationship, RelationshipType } from '../types/characterMap'

// ── Visual constants ────────────────────────────────────────────────────────
const NODE_WIDTH = 240
const NODE_HEIGHT = 64
const RANKSEP = 120
const NODESEP = 80
const FACTION_PADDING = 32
const FACTION_LABEL_H = 36
const FACTION_GAP = 120
const CANVAS_TOP = 48

// ── Faction colour mapping ──────────────────────────────────────────────────
const COLOUR_MAP: Record<string, string> = {
  blue:   '#3b82f6',
  red:    '#ef4444',
  green:  '#22c55e',
  amber:  '#f59e0b',
  violet: '#8b5cf6',
  slate:  '#64748b',
}

// ── Edge style mapping ──────────────────────────────────────────────────────
const EDGE_STYLES: Record<RelationshipType, { stroke: string; strokeDasharray?: string; strokeWidth: number }> = {
  alliance:     { stroke: '#22c55e', strokeWidth: 2 },
  family:       { stroke: '#22c55e', strokeWidth: 2 },
  romantic:     { stroke: '#ec4899', strokeWidth: 2 },
  antagonism:   { stroke: '#ef4444', strokeWidth: 2.5 },
  professional: { stroke: '#94a3b8', strokeDasharray: '5,3', strokeWidth: 1.5 },
  mentorship:   { stroke: '#f59e0b', strokeWidth: 2 },
  criminal:     { stroke: '#eab308', strokeDasharray: '5,3', strokeWidth: 1.5 },
}

// ── Per-faction dagre layout ────────────────────────────────────────────────
function layoutCharsInFaction(chars: Character[]): Map<string, { x: number; y: number }> {
  const g = new dagre.graphlib.Graph()
  g.setGraph({ rankdir: 'TB', ranksep: RANKSEP, nodesep: NODESEP })
  g.setDefaultEdgeLabel(() => ({}))
  chars.forEach(c => g.setNode(c.id, { width: NODE_WIDTH, height: NODE_HEIGHT }))
  dagre.layout(g)
  const positions = new Map<string, { x: number; y: number }>()
  chars.forEach(c => {
    const n = g.node(c.id)
    positions.set(c.id, { x: n.x - NODE_WIDTH / 2, y: n.y - NODE_HEIGHT / 2 })
  })
  return positions
}

// ── Main export ─────────────────────────────────────────────────────────────
export function buildLayout(charMap: CharacterMap): { nodes: Node[]; edges: Edge[] } {
  const { factions, characters, relationships } = charMap

  const factionChars = new Map<string, Character[]>(factions.map(f => [f.id, []]))
  characters.forEach(c => {
    const fid = c.faction_id ?? factions[0]?.id
    if (fid && factionChars.has(fid)) {
      factionChars.get(fid)!.push(c)
    } else if (factions.length > 0) {
      factionChars.get(factions[0].id)!.push(c)
    }
  })

  const nodes: Node[] = []
  const nodeIdSet = new Set<string>()
  let cursorX = FACTION_PADDING

  factions.forEach((faction: Faction) => {
    const chars = factionChars.get(faction.id) ?? []
    if (chars.length === 0) return

    const colour = COLOUR_MAP[faction.color_hint] ?? '#64748b'
    const charPositions = layoutCharsInFaction(chars)

    let maxRight = 0, maxBottom = 0
    charPositions.forEach(({ x, y }) => {
      maxRight  = Math.max(maxRight,  x + NODE_WIDTH)
      maxBottom = Math.max(maxBottom, y + NODE_HEIGHT)
    })

    const groupW = maxRight  + FACTION_PADDING * 2
    const groupH = maxBottom + FACTION_PADDING * 2 + FACTION_LABEL_H
    const groupX = cursorX
    const groupY = CANVAS_TOP

    nodes.push({
      id: `__faction_${faction.id}`,
      type: 'factionGroup',
      position: { x: groupX, y: groupY },
      style: { width: groupW, height: groupH },
      data: { label: faction.label, colour, description: faction.description },
      draggable: false,
      selectable: false,
      zIndex: 0,
    })

    chars.forEach(char => {
      const pos = charPositions.get(char.id)!
      nodes.push({
        id: char.id,
        type: 'characterCard',
        position: {
          x: groupX + FACTION_PADDING + pos.x,
          y: groupY + FACTION_LABEL_H + FACTION_PADDING + pos.y,
        },
        data: { character: char, colour, showBadges: false },
        zIndex: 1,
      })
      nodeIdSet.add(char.id)
    })

    cursorX += groupW + FACTION_GAP
  })

  const edges: Edge[] = relationships
    .filter((r: Relationship) => nodeIdSet.has(r.from_id) && nodeIdSet.has(r.to_id))
    .map((r: Relationship) => ({
      id: `${r.from_id}__${r.to_id}__${r.type}`,
      source: r.from_id,
      target: r.to_id,
      type: 'smoothstep',
      label: r.label,
      labelBgStyle: { fill: 'rgba(17,17,17,0.92)', rx: 3, ry: 3 },
      labelStyle: { fill: '#ccc', fontSize: 11, fontFamily: '-apple-system,sans-serif' },
      style: EDGE_STYLES[r.type] ?? EDGE_STYLES.professional,
      zIndex: 2,
    }))

  return { nodes, edges }
}
