import { describe, it, expect } from 'vitest'
import { cardSizeForColumns, columnsForCardSize, gridGap, gridTrackWidth } from './gridLayout'

const PHONE_NARROW = 320
const PHONE = 375
const DESKTOP_CAPPED = 1200
const DESKTOP_WIDE = 1600
const OPTIONS = [1, 2, 3, 4, 5, 6, 7, 8, 10, 12]

describe('gridLayout', () => {
  it('measures the track from the page padding and the max-width cap', () => {
    // #page-container is 20px of padding per side on phones, 24px on desktop,
    // and its 1400px max-width includes that padding.
    expect(gridTrackWidth(PHONE)).toBe(PHONE - 20)
    expect(gridTrackWidth(DESKTOP_CAPPED)).toBe(DESKTOP_CAPPED - 48)
    expect(gridTrackWidth(DESKTOP_WIDE)).toBe(1400 - 48)
  })

  it('uses the tighter gap on phones', () => {
    expect(gridGap(PHONE)).toBe(8)
    expect(gridGap(DESKTOP_WIDE)).toBe(16)
  })

  it('round-trips every column count that is actually achievable', () => {
    for (const width of [1024, DESKTOP_CAPPED, DESKTOP_WIDE]) {
      for (const cols of OPTIONS) {
        const size = cardSizeForColumns(cols, width)
        // Counts that hit a clamp bound cannot round-trip by construction.
        if (size === 75 || size === 400) continue
        expect(columnsForCardSize(size, width)).toBe(cols)
      }
    }
  })

  it('clamps the card size to the slider range', () => {
    expect(cardSizeForColumns(1, DESKTOP_WIDE)).toBe(400)
    expect(cardSizeForColumns(30, DESKTOP_WIDE)).toBe(75)
    expect(cardSizeForColumns(12, PHONE)).toBe(75)
  })

  it('keeps a rendered row inside the track at every option and phone width', () => {
    for (const width of [PHONE_NARROW, 360, PHONE, 414]) {
      const gap = gridGap(width)
      const track = gridTrackWidth(width)
      for (const cols of OPTIONS) {
        const size = cardSizeForColumns(cols, width)
        const rendered = columnsForCardSize(size, width)
        expect(rendered).toBeLessThanOrEqual(cols)
        expect(rendered * (size + gap) - gap).toBeLessThanOrEqual(track)
      }
    }
  })

  it('fits the largest card count a phone can hold instead of overflowing', () => {
    // A 375px screen has room for four 75px cards with the 8px mobile gap.
    expect(columnsForCardSize(cardSizeForColumns(12, PHONE), PHONE)).toBe(4)
  })
})
