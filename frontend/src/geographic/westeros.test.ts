import { describe, it, expect } from 'vitest'
import { resolveRegion, WESTEROS_ANCHORS } from './westeros'

describe('resolveRegion', () => {
  it('exact alias matches', () => {
    expect(resolveRegion('The North')?.id).toBe('the-north')
    expect(resolveRegion('Winterfell')?.id).toBe('the-north')
    expect(resolveRegion('The Westerlands')?.id).toBe('the-westerlands')
  })

  it('strips leading articles', () => {
    expect(resolveRegion('the vale')?.id).toBe('the-vale')
    expect(resolveRegion('vale')?.id).toBe('the-vale')
  })

  it('substring containment fallback', () => {
    expect(resolveRegion('Casterly Rock seat')?.id).toBe('the-westerlands')
    expect(resolveRegion("Storm's End garrison")?.id).toBe('the-stormlands')
  })

  it('returns null for unknown regions', () => {
    expect(resolveRegion('Atlantis')).toBeNull()
    expect(resolveRegion('')).toBeNull()
    expect(resolveRegion(null)).toBeNull()
    expect(resolveRegion(undefined)).toBeNull()
  })

  it('handles Essos regions', () => {
    expect(resolveRegion('Pentos')?.id).toBe('essos-free-cities')
    expect(resolveRegion("Slaver's Bay")?.id).toBe('slavers-bay')
    expect(resolveRegion('Vaes Dothrak')?.id).toBe('dothraki-sea')
  })

  it('every anchor has unique id', () => {
    const ids = WESTEROS_ANCHORS.map((a) => a.id)
    expect(new Set(ids).size).toBe(ids.length)
  })
})
