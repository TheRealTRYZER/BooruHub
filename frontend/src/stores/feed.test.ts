import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { nextTick } from 'vue'
import { useFeedStore } from './feed'

describe('Feed Store', () => {
  beforeEach(() => {
    localStorage.clear()
    sessionStorage.clear()
    setActivePinia(createPinia())
  })

  it('should have initial state', () => {
    const store = useFeedStore()
    expect(store.tags).toBe('')
    expect(store.sites).toEqual(['danbooru', 'e621', 'rule34'])
    expect(store.posts).toEqual([])
    expect(store.page).toBe(1)
    expect(store.hasMore).toBe(true)
  })

  it('should toggle site selection', async () => {
    const store = useFeedStore()
    
    // Remove site
    store.toggleSite('danbooru')
    expect(store.sites).not.toContain('danbooru')
    expect(store.sites.length).toBe(2)

    // Add back
    store.toggleSite('danbooru')
    expect(store.sites).toContain('danbooru')
    expect(store.sites.length).toBe(3)
  })

  it('should not allow removing all sites', () => {
    const store = useFeedStore()
    store.toggleSite('danbooru')
    store.toggleSite('e621')
    
    // Try to remove last site
    store.toggleSite('rule34')
    expect(store.sites).toEqual(['rule34'])
  })

  it('should reset feed state', () => {
    const store = useFeedStore()
    store.posts = [{ id: '1', source_site: 'danbooru', tags: [], rating: 'g', score: 0 } as any]
    store.page = 5
    store.hasMore = false

    store.resetFeed()
    expect(store.posts).toEqual([])
    expect(store.page).toBe(1)
    expect(store.hasMore).toBe(true)
  })

  it('should toggle split tags mode', () => {
    const store = useFeedStore()
    expect(store.isSplit).toBe(false)
    store.toggleSplit()
    expect(store.isSplit).toBe(true)
  })

  it('should persist search tags in sessionStorage', async () => {
    const store = useFeedStore()
    store.tags = 'test-tag'
    await nextTick()
    expect(sessionStorage.getItem('booruhub_tags')).toBe('test-tag')
  })

  it('should persist active sites in localStorage', async () => {
    const store = useFeedStore()
    store.toggleSite('danbooru')
    await nextTick()
    expect(JSON.parse(localStorage.getItem('booruhub_sites') || '[]')).toEqual(['e621', 'rule34'])
  })

  describe('Post Deduplication (registerPostHash)', () => {
    it('should register a hash for a single post and return false', () => {
      const store = useFeedStore()
      const post = { id: 1, source_site: 'danbooru', tags: ['safe', 'solo'], rating: 'g', score: 10 } as any
      store.posts = [post]

      const duplicateFound = store.registerPostHash(1, 'danbooru', 'abc123hash', ['safe', 'solo'])
      expect(duplicateFound).toBe(false)
      expect(store.posts[0].hash).toBe('abc123hash')
    })

    it('should deduplicate when a matching hash is found, merging tags and updating duplicate sites', () => {
      const store = useFeedStore()
      const post1 = { id: 1, source_site: 'danbooru', tags: ['safe', 'solo'], rating: 'g', score: 10 } as any
      const post2 = { id: 2, source_site: 'e621', tags: ['funny', 'solo', 'digital_media'], rating: 'g', score: 15 } as any
      
      store.posts = [post1, post2]

      // Register hash for first post (no duplicate yet)
      const dup1 = store.registerPostHash(1, 'danbooru', 'hashA', ['safe', 'solo'])
      expect(dup1).toBe(false)

      // Register hash for second post (duplicate of first)
      const dup2 = store.registerPostHash(2, 'e621', 'hashA', ['funny', 'solo', 'digital_media'])
      expect(dup2).toBe(true)

      // First post should survive and have merged tags (unique tags only)
      expect(store.posts).toHaveLength(1)
      expect(store.posts[0].id).toBe(1)
      expect(store.posts[0].tags.sort()).toEqual(['digital_media', 'funny', 'safe', 'solo'].sort())

      // First post should list e621 as a duplicate site
      expect(store.posts[0].duplicate_sites).toEqual(['e621'])
    })
  })
})
