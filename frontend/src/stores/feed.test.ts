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

  describe('Post Deduplication (addPosts & MD5)', () => {
    it('should add unique posts and calculate their hash instantly', () => {
      const store = useFeedStore()
      const post = { id: 1, source_site: 'danbooru', md5: 'abc123md5', tags: ['safe', 'solo'], rating: 'g', score: 10 } as any
      
      store.addPosts([post])
      expect(store.posts).toHaveLength(1)
      expect(store.posts[0].hash).toBe('md5-abc123md5')
    })

    it('should instantly filter duplicates, merge tags, and aggregate site badges upon adding', () => {
      const store = useFeedStore()
      const post1 = { id: 1, source_site: 'danbooru', md5: 'match_md5', tags: ['safe', 'solo'], rating: 'g', score: 10 } as any
      const post2 = { id: 2, source_site: 'e621', md5: 'match_md5', tags: ['funny', 'solo', 'digital_media'], rating: 'g', score: 15 } as any
      
      store.addPosts([post1, post2])

      // Only the first post should survive in the store
      expect(store.posts).toHaveLength(1)
      expect(store.posts[0].id).toBe(1)
      
      // Tags must be merged correctly
      expect(store.posts[0].tags.sort()).toEqual(['digital_media', 'funny', 'safe', 'solo'].sort())
      
      // The duplicate site name must be added to duplicate_sites badge list
      expect(store.posts[0].duplicate_sites).toEqual(['e621'])
    })
  })

  describe('rootMargin Setting', () => {
    it('should have a default value of 2500', () => {
      const store = useFeedStore()
      expect(store.rootMargin).toBe(2500)
    })

    it('should persist rootMargin changes to localStorage', async () => {
      const store = useFeedStore()
      store.rootMargin = 3000
      await nextTick()
      expect(localStorage.getItem('booruhub_root_margin')).toBe('3000')
    })
  })
})
