import { describe, it, expect } from 'vitest'
import { replaceAfterOrderScore } from './tagQuery'

describe('replaceAfterOrderScore', () => {
  it('replaces everything after order:score', () => {
    expect(replaceAfterOrderScore('order:score rating:general', 'cat_ears')).toBe('order:score cat_ears')
    expect(replaceAfterOrderScore('order:score a b c', 'x')).toBe('order:score x')
  })

  it('keeps what comes before order:score', () => {
    expect(replaceAfterOrderScore('rating:general order:score a', 'x')).toBe('rating:general order:score x')
  })

  it('adds the tag when order:score is last', () => {
    expect(replaceAfterOrderScore('order:score', 'x')).toBe('order:score x')
  })

  it('uses the tag alone when there is no order:score', () => {
    expect(replaceAfterOrderScore('a b', 'x')).toBe('x')
    expect(replaceAfterOrderScore('', 'x')).toBe('x')
  })

  it('is case-insensitive and ignores extra spaces', () => {
    expect(replaceAfterOrderScore('  ORDER:SCORE   a ', 'x')).toBe('ORDER:SCORE x')
  })
})
