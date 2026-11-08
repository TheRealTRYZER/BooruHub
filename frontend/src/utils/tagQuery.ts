/**
 * Query for a tag clicked in the lightbox: everything after `order:score` is
 * replaced by the tag. Without `order:score` the tag becomes the whole query.
 */
export function replaceAfterOrderScore(current: string, tag: string): string {
  const tokens = current.trim().split(/\s+/).filter(Boolean)
  const i = tokens.findIndex((t) => t.toLowerCase() === 'order:score')
  return i === -1 ? tag : [...tokens.slice(0, i + 1), tag].join(' ')
}
