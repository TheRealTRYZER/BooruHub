import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { apiGetMappings, apiRegister, apiClearCache } from '../api'
import type { TagMapping } from '../types'

/**
 * /api/mappings returns a bare JSON array. The client used to read
 * `data.mappings` off it, which was always undefined, so the settings page
 * always rendered an empty mapping list.
 */
function mapping(id: number, unitag: string): TagMapping {
  return { id, user_id: 1, unitag, danbooru_tags: '', e621_tags: '', rule34_tags: '' }
}

describe('apiGetMappings', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    // api.ts keeps a module-level 60s GET cache keyed by URL; without this
    // the first response would satisfy every later call.
    apiClearCache()
    fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  function respondWith(body: unknown) {
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => body,
    })
  }

  it('returns the array the endpoint actually sends', async () => {
    const rows = [mapping(1, 'rating:general'), mapping(2, 'female')]
    respondWith(rows)

    const result = await apiGetMappings()

    expect(result).toEqual(rows)
    expect(result).toHaveLength(2)
  })

  it('returns an empty array for an empty response', async () => {
    respondWith([])

    await expect(apiGetMappings()).resolves.toEqual([])
  })

  it('still accepts the legacy wrapped shape', async () => {
    const rows = [mapping(1, 'male')]
    respondWith({ mappings: rows })

    await expect(apiGetMappings()).resolves.toEqual(rows)
  })

  it('tolerates a wrapped response with no mappings key', async () => {
    respondWith({})

    await expect(apiGetMappings()).resolves.toEqual([])
  })
})

describe('API error formatting', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    apiClearCache()
    fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  function rejectWith(status: number, body: unknown) {
    fetchMock.mockResolvedValue({
      ok: false,
      status,
      json: async () => body,
    })
  }

  it('surfaces the field and message from a validation detail array', async () => {
    rejectWith(422, {
      detail: [
        {
          type: 'string_too_short',
          loc: ['body', 'password'],
          msg: 'String should have at least 8 characters',
          input: '123456',
          ctx: { min_length: 8 },
        },
      ],
    })

    await expect(apiRegister('newuser', 'new@example.com', '123456')).rejects.toThrow(
      'password: String should have at least 8 characters',
    )
  })

  it('joins several validation errors into one message', async () => {
    rejectWith(422, {
      detail: [
        { loc: ['body', 'username'], msg: 'String should have at least 3 characters' },
        { loc: ['body', 'email'], msg: 'value is not a valid email address' },
      ],
    })

    await expect(apiRegister('ab', 'nope', '12345678')).rejects.toThrow(
      'username: String should have at least 3 characters; email: value is not a valid email address',
    )
  })

  it('keeps the plain string detail unchanged', async () => {
    rejectWith(409, { detail: 'Username or email already taken' })

    await expect(apiRegister('taken', 'taken@example.com', '12345678')).rejects.toThrow(
      'Username or email already taken',
    )
  })

  it('falls back to the HTTP status when the body has no detail', async () => {
    rejectWith(429, {})

    await expect(apiRegister('limited', 'limited@example.com', '12345678')).rejects.toThrow('HTTP 429')
  })
})
