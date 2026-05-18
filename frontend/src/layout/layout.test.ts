import { describe, it, expect } from 'vitest'
import { buildLayout, pickHandles, NODE_WIDTH, NODE_HEIGHT } from './layout'
import type {
  Character,
  CharacterMap,
  Faction,
  Relationship,
} from '../types/characterMap'

// ── Helpers ────────────────────────────────────────────────────────────────
function faction(id: string, overrides: Partial<Faction> = {}): Faction {
  return {
    id,
    label: `Faction ${id}`,
    description: '',
    color_hint: 'slate',
    ...overrides,
  }
}

function character(id: string, factionId: string | null, overrides: Partial<Character> = {}): Character {
  return {
    id,
    name: `Char ${id}`,
    role: '',
    description: '',
    faction_id: factionId,
    importance: 'supporting',
    is_deceased_in_work: false,
    spoiler_level: 0,
    ...overrides,
  }
}

function rel(from: string, to: string, overrides: Partial<Relationship> = {}): Relationship {
  return {
    from_id: from,
    to_id: to,
    type: 'alliance',
    label: '',
    spoiler_level: 0,
    ...overrides,
  }
}

function map(parts: Partial<CharacterMap> = {}): CharacterMap {
  return {
    title: 'T',
    subtitle: '',
    blurb: '',
    spoiler_mode: 'full',
    factions: [],
    characters: [],
    relationships: [],
    notes: '',
    ...parts,
  }
}

// ── pickHandles ────────────────────────────────────────────────────────────
describe('pickHandles', () => {
  const o = { x: 0, y: 0 }

  it('picks right→left when target is to the right', () => {
    expect(pickHandles(o, { x: 100, y: 0 })).toEqual({
      sourceHandle: 'src-right',
      targetHandle: 'tgt-left',
    })
  })

  it('picks left→right when target is to the left', () => {
    expect(pickHandles(o, { x: -100, y: 0 })).toEqual({
      sourceHandle: 'src-left',
      targetHandle: 'tgt-right',
    })
  })

  it('picks bottom→top when target is below', () => {
    expect(pickHandles(o, { x: 0, y: 100 })).toEqual({
      sourceHandle: 'src-bottom',
      targetHandle: 'tgt-top',
    })
  })

  it('picks top→bottom when target is above', () => {
    expect(pickHandles(o, { x: 0, y: -100 })).toEqual({
      sourceHandle: 'src-top',
      targetHandle: 'tgt-bottom',
    })
  })

  it('prefers horizontal axis when |dx| === |dy| (tie)', () => {
    // Math.abs(dx) >= Math.abs(dy) → horizontal branch wins
    expect(pickHandles(o, { x: 50, y: 50 })).toEqual({
      sourceHandle: 'src-right',
      targetHandle: 'tgt-left',
    })
  })

  it('picks dominant axis when one slightly larger', () => {
    expect(pickHandles(o, { x: 30, y: 100 })).toEqual({
      sourceHandle: 'src-bottom',
      targetHandle: 'tgt-top',
    })
    expect(pickHandles(o, { x: 100, y: -30 })).toEqual({
      sourceHandle: 'src-right',
      targetHandle: 'tgt-left',
    })
  })
})

// ── buildLayout ────────────────────────────────────────────────────────────
describe('buildLayout', () => {
  it('returns empty when there are no factions', () => {
    const { nodes, edges } = buildLayout(map())
    expect(nodes).toEqual([])
    expect(edges).toEqual([])
  })

  it('emits one faction group + one character for a single faction with one char', () => {
    const f = faction('f1')
    const c = character('c1', 'f1')
    const { nodes, edges } = buildLayout(map({ factions: [f], characters: [c] }))

    expect(nodes).toHaveLength(2)
    const factionNode = nodes.find(n => n.type === 'factionGroup')!
    const charNode = nodes.find(n => n.type === 'characterCard')!

    expect(factionNode.id).toBe('__faction_f1')
    expect(charNode.id).toBe('c1')
    expect(charNode.parentId).toBe('__faction_f1')
    expect(charNode.extent).toBe('parent')
    expect((charNode.style as { width: number }).width).toBe(NODE_WIDTH)
    expect(edges).toEqual([])
  })

  it('filters out empty factions', () => {
    const f1 = faction('f1')
    const f2 = faction('f2')
    const c = character('c1', 'f1')
    const { nodes } = buildLayout(map({ factions: [f1, f2], characters: [c] }))

    const factionNodes = nodes.filter(n => n.type === 'factionGroup')
    expect(factionNodes).toHaveLength(1)
    expect(factionNodes[0].id).toBe('__faction_f1')
  })

  it('assigns characters with unknown faction_id to the first faction', () => {
    const f1 = faction('f1')
    const f2 = faction('f2')
    const c1 = character('c1', 'nonexistent')
    const c2 = character('c2', 'f2')
    const { nodes } = buildLayout(map({ factions: [f1, f2], characters: [c1, c2] }))

    const orphan = nodes.find(n => n.id === 'c1')!
    expect(orphan.parentId).toBe('__faction_f1')
  })

  it('assigns characters with null faction_id to the first faction', () => {
    const f1 = faction('f1')
    const c = character('c1', null)
    const { nodes } = buildLayout(map({ factions: [f1], characters: [c] }))

    const charNode = nodes.find(n => n.id === 'c1')!
    expect(charNode.parentId).toBe('__faction_f1')
  })

  it('arranges 4 factions in a 2-col grid (ceil(sqrt(4)) = 2)', () => {
    const factions = ['a', 'b', 'c', 'd'].map(id => faction(id))
    const chars = factions.map(f => character(`c-${f.id}`, f.id))
    const { nodes } = buildLayout(map({ factions, characters: chars }))

    const groups = nodes.filter(n => n.type === 'factionGroup')
    expect(groups).toHaveLength(4)

    const byId = Object.fromEntries(groups.map(g => [g.id, g.position]))
    // Same row: a & b have equal y; c & d have equal y
    expect(byId['__faction_a'].y).toBe(byId['__faction_b'].y)
    expect(byId['__faction_c'].y).toBe(byId['__faction_d'].y)
    // Same col: a & c have equal x; b & d have equal x
    expect(byId['__faction_a'].x).toBe(byId['__faction_c'].x)
    expect(byId['__faction_b'].x).toBe(byId['__faction_d'].x)
    // Second row sits below first row
    expect(byId['__faction_c'].y).toBeGreaterThan(byId['__faction_a'].y)
  })

  it('arranges 9 factions in a 3-col grid (ceil(sqrt(9)) = 3)', () => {
    const factions = Array.from({ length: 9 }, (_, i) => faction(`f${i}`))
    const chars = factions.map(f => character(`c-${f.id}`, f.id))
    const { nodes } = buildLayout(map({ factions, characters: chars }))

    const groups = nodes.filter(n => n.type === 'factionGroup')
    // First three should share a row
    expect(groups[0].position.y).toBe(groups[1].position.y)
    expect(groups[1].position.y).toBe(groups[2].position.y)
    // Fourth wraps to next row
    expect(groups[3].position.y).toBeGreaterThan(groups[0].position.y)
  })

  it('respects MAX_COLS=2 inside a faction — third char wraps to row 2', () => {
    const f = faction('f')
    const chars = ['c1', 'c2', 'c3'].map(id => character(id, 'f'))
    const { nodes } = buildLayout(map({ factions: [f], characters: chars }))

    const cn = (id: string) => nodes.find(n => n.id === id)!
    // c1 col=0 row=0; c2 col=1 row=0; c3 col=0 row=1
    expect(cn('c1').position.x).toBe(cn('c3').position.x)
    expect(cn('c1').position.y).toBe(cn('c2').position.y)
    expect(cn('c3').position.y).toBeGreaterThan(cn('c1').position.y)
  })

  it('uses faction-relative positions for character nodes', () => {
    const f = faction('f')
    const c = character('c1', 'f')
    const { nodes } = buildLayout(map({ factions: [f], characters: [c] }))
    const charNode = nodes.find(n => n.id === 'c1')!
    // First character starts at (FACTION_PADDING, FACTION_LABEL_H + FACTION_PADDING)
    // = (40, 40 + 40) = (40, 80) — verify it's not absolute by checking it's small
    expect(charNode.position.x).toBeLessThan(200)
    expect(charNode.position.y).toBeLessThan(200)
  })

  it('emits an edge for each relationship between known characters', () => {
    const f = faction('f')
    const c1 = character('c1', 'f')
    const c2 = character('c2', 'f')
    const r = rel('c1', 'c2', { type: 'romantic', label: 'married' })
    const { edges } = buildLayout(
      map({ factions: [f], characters: [c1, c2], relationships: [r] }),
    )

    expect(edges).toHaveLength(1)
    expect(edges[0]).toMatchObject({
      source: 'c1',
      target: 'c2',
      label: 'married',
    })
    // Handles should be set by pickHandles
    expect(edges[0].sourceHandle).toMatch(/^src-/)
    expect(edges[0].targetHandle).toMatch(/^tgt-/)
  })

  it('drops relationships whose endpoints are not in the map', () => {
    const f = faction('f')
    const c1 = character('c1', 'f')
    const orphanRel = rel('c1', 'ghost')
    const { edges } = buildLayout(
      map({ factions: [f], characters: [c1], relationships: [orphanRel] }),
    )
    expect(edges).toEqual([])
  })

  it('encodes relationship type in edge id for de-duplication', () => {
    const f = faction('f')
    const c1 = character('c1', 'f')
    const c2 = character('c2', 'f')
    const r1 = rel('c1', 'c2', { type: 'family' })
    const r2 = rel('c1', 'c2', { type: 'antagonism' })
    const { edges } = buildLayout(
      map({ factions: [f], characters: [c1, c2], relationships: [r1, r2] }),
    )
    const ids = edges.map(e => e.id)
    expect(new Set(ids).size).toBe(2)
    expect(ids).toContain('c1__c2__family')
    expect(ids).toContain('c1__c2__antagonism')
  })

  it('sets a faction-group width that accommodates the character grid', () => {
    const f = faction('f')
    const chars = ['c1', 'c2'].map(id => character(id, 'f'))
    const { nodes } = buildLayout(map({ factions: [f], characters: chars }))
    const groupNode = nodes.find(n => n.type === 'factionGroup')!
    const { width, height } = groupNode.style as { width: number; height: number }
    // Two columns of NODE_WIDTH + padding, single row of NODE_HEIGHT
    expect(width).toBeGreaterThanOrEqual(2 * NODE_WIDTH)
    expect(height).toBeGreaterThanOrEqual(NODE_HEIGHT)
  })
})
