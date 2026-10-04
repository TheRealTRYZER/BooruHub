/**
 * Geometry shared by the posts-per-row control (`SearchToolbar`) and the grid
 * that renders the results (`PostGrid`).
 *
 * Both used to assume a flat 40px of page chrome, which never matched
 * `#page-container`: 48px on desktop and 20px on mobile. Because the toolbar
 * back-computes a card size from a desired column count and the grid
 * re-derives the count from that size, the mismatch made "8 posts" render as 6
 * or 7. Measuring the real container keeps the two in lockstep.
 */

const MOBILE_BREAKPOINT = 768
const MOBILE_GAP = 8
const DESKTOP_GAP = 16
const MAX_COLUMNS = 20
const MIN_CARD_SIZE = 75
const MAX_CARD_SIZE = 400

/** Horizontal padding `#page-container` applies at the current breakpoint. */
export function pageGutter(width: number): number {
  return width <= MOBILE_BREAKPOINT ? 20 : 48
}

/** Usable grid width: viewport minus the page padding and the max-width cap. */
export function gridTrackWidth(width: number): number {
  return Math.max(1, Math.min(width, 1400) - pageGutter(width))
}

export function gridGap(width: number): number {
  return width <= MOBILE_BREAKPOINT ? MOBILE_GAP : DESKTOP_GAP
}

/** How many cards of `cardSize` fit across the grid. */
export function columnsForCardSize(cardSize: number, width: number): number {
  const gap = gridGap(width)
  const cols = Math.floor((gridTrackWidth(width) + gap) / (cardSize + gap))
  return Math.max(1, Math.min(MAX_COLUMNS, cols))
}

/** The card size that yields exactly `columns` cards per row, clamped to the slider range. */
export function cardSizeForColumns(columns: number, width: number): number {
  const gap = gridGap(width)
  const cols = Math.max(1, Math.min(MAX_COLUMNS, Math.round(columns)))
  const size = Math.floor((gridTrackWidth(width) + gap) / cols) - gap
  return Math.max(MIN_CARD_SIZE, Math.min(MAX_CARD_SIZE, size))
}
