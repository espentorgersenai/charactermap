import type { Edge, Node } from '@xyflow/react'
import type { CharacterMap, Character, Faction, Relationship, RelationshipType } from '../types/characterMap'

// ── Visual constants ────────────────────────────────────────────────────────
const NODE_WIDTH = 240
const NODE_HEIGHT = 64
const COL_GAP = 24       // horizontal gap between columns within a faction
const ROW_GAP = 16       // vertical gap between rows within a faction
const MAX_COLS = 2       // max columns per faction before wrapping
const FACTION_PADDING = 32
const FACTION_LABEL_H = 36
const FACTION_COL_GAP = 80   // horizontal gap between faction columns
const FACTION_ROW_GAP = 60   // vertical gap between faction rows
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

// ── Per-faction vertical grid layout ────────────────────────────────────────
// Stacks characters in up to MAX_COLS columns, top-to-bottom within each column.
// Avoids dagre for unconnected nodes (dagre collapses them to one horizontal rank).
function layoutCharsInFaction(chars: Character[]): Map<string, { x: number; y: number }> {
  const cols = Math.min(chars.length, MAX_COLS)
  const positions = new Map<string, { x: number; y: number }>()
  chars.forEach((c, i) => {
    const col = i % cols
    const row = Math.floor(i / cols)
    positions.set(c.id, {
      x: col * (NODE_WIDTH + COL_GAP),
      y: row * (NODE_HEIGHT + ROW_GAP),
    })
  })
  return positions
}

// ── Faction size helper ──────────────────────────────────────────────────────
function factionSize(chars: Character[]): { w: number; h: number } {
  const positions = layoutCharsInFaction(chars)
  let maxRight = 0, maxBottom = 0
  positions.forEach(({ x, y }) => {
    maxRight  = Math.max(maxRight,  x + NODE_WIDTH)
    maxBottom = Math.max(maxBottom, y + NODE_HEIGHT)
  })
  return {
    w: maxRight  + FACTION_PADDING * 2,
    h: maxBottom + FACTION_PADDING * 2 + FACTION_LABEL_H,
  }
}

// ── Main export ─────────────────────────────────────────────────────────────
// Factions are arranged in a square grid (ceil(√N) columns) so the overall
// map shape is compact and inter-faction edges cross at varied angles.
export function buildLayout(charMap: CharacterMap): { nodes: Node[]; edges: Edge[] } {
  const { factions, characters, relationships } = charMap

  // Group characters by faction
  const factionChars = new Map<string, Character[]>(factions.map(f => [f.id, []]))
  characters.forEach(c => {
    const fid = c.faction_id ?? factions[0]?.id
    if (fid && factionChars.has(fid)) {
      factionChars.get(fid)!.push(c)
    } else if (factions.length > 0) {
      factionChars.get(factions[0].id)!.push(c)
    }
  })

  const nonEmpty = factions.filter(f => (factionChars.get(f.id)?.length ?? 0) > 0)
  const GRID_COLS = Math.max(2, Math.ceil(Math.sqrt(nonEmpty.length)))

  // Per-column max width, per-row max height (for uniform column/row sizing)
  const colWidths: number[] = new Array(GRID_COLS).fill(0)
  const rowHeights: number[] = []
  nonEmpty.forEach((faction, idx) => {
    const col = idx % GRID_COLS
    const row = Math.floor(idx / GRID_COLS)
    const { w, h } = factionSize(factionChars.get(faction.id) ?? [])
    colWidths[col] = Math.max(colWidths[col], w)
    rowHeights[row] = Math.max(rowHeights[row] ?? 0, h)
  })

  // Cumulative column X offsets and row Y offsets
  const colX: number[] = [FACTION_PADDING]
  for (let c = 1; c < GRID_COLS; c++) {
    colX.push(colX[c - 1] + colWidths[c - 1] + FACTION_COL_GAP)
  }
  const rowY: number[] = [CANVAS_TOP]
  for (let r = 1; r < rowHeights.length; r++) {
    rowY.push(rowY[r - 1] + rowHeights[r - 1] + FACTION_ROW_GAP)
  }

  const nodes: Node[] = []
  const nodeIdSet = new Set<string>()

  nonEmpty.forEach((faction, idx) => {
    const gridCol = idx % GRID_COLS
    const gridRow = Math.floor(idx / GRID_COLS)
    const chars = factionChars.get(faction.id) ?? []
    const colour = COLOUR_MAP[faction.color_hint] ?? '#64748b'
    const charPositions = layoutCharsInFaction(chars)
    const { w: groupW, h: groupH } = factionSize(chars)
    const groupX = colX[gridCol]
    const groupY = rowY[gridRow]

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
