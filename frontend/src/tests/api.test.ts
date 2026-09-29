import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { apiGetMappings, apiClearCache } from '../api'
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
