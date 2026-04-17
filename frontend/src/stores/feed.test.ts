import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useFeedStore } from './feed'

describe('Feed Store', () => {
  beforeEach(() => {
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

  it('should toggle site selection', () => {
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
})
