import { mount } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createTestingPinia } from '@pinia/testing'
import PostView from './PostView.vue'
import { useFeedStore } from '../stores/feed'
import { useLangStore } from '../stores/lang'

const mockRoute = {
  query: { id: '123', site: 'danbooru' }
}
const mockRouter = {
  replace: vi.fn(),
  push: vi.fn()
}

vi.mock('vue-router', () => ({
  useRoute: () => mockRoute,
  useRouter: () => mockRouter
}))

vi.mock('../api', () => ({
  apiCheckFavorite: vi.fn(() => Promise.resolve({ is_favorite: false, favorite_id: null })),
  apiAddFavorite: vi.fn(() => Promise.resolve()),
  apiRemoveFavorite: vi.fn(() => Promise.resolve()),
  apiSearch: vi.fn(() => Promise.resolve({ posts: [] }))
}))

describe('PostView.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockRoute.query = { id: '123', site: 'danbooru' }
  })

  it('should render page correctly when post is found', async () => {
    const wrapper = mount(PostView, {
      global: {
        plugins: [createTestingPinia({
          createSpy: vi.fn,
          initialState: {
            lang: { t: (key: string) => key },
            feed: {
              posts: [
                {
                  id: 123,
                  source_site: 'danbooru',
                  file_url: 'https://test.com/danbooru.jpg',
                  rating: 's',
                  tags: ['tag1', 'tag2'],
                  width: 100,
                  height: 100,
                  score: 10
                }
              ]
            }
          }
        })]
      }
    })

    // Allow onMounted ticks
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(wrapper.find('.post-detail-info-row').exists()).toBe(true)
    expect(wrapper.find('.post-card-badge.danbooru').text()).toBe('danbooru')
    expect(wrapper.find('.post-detail-image img').attributes('src')).toBe('https://test.com/danbooru.jpg')
    expect(wrapper.find('.post-card-rating').text()).toBe('S')
  })

  it('should support switching site versions when badges are clicked in the sidebar', async () => {
    const mockPostMultiple = {
      id: 123,
      source_site: 'danbooru',
      file_url: 'https://test.com/danbooru.jpg',
      rating: 's',
      tags: ['tag1'],
      width: 100,
      height: 100,
      score: 10,
      duplicate_sites: ['rule34'],
      duplicates: [
        {
          id: 456,
          source_site: 'rule34',
          file_url: 'https://test.com/rule34.jpg',
          rating: 'e',
          tags: ['tag1', 'lewd'],
          width: 150,
          height: 150,
          score: 50
        }
      ]
    }

    const wrapper = mount(PostView, {
      global: {
        plugins: [createTestingPinia({
          createSpy: vi.fn,
          initialState: {
            lang: { t: (key: string) => key },
            feed: {
              posts: [mockPostMultiple]
            }
          }
        })]
      }
    })

    // Allow onMounted ticks
    await new Promise((resolve) => setTimeout(resolve, 0))

    // Assert both badges are rendered in source row
    const badges = wrapper.findAll('.post-detail-info-value .post-card-badge')
    expect(badges.length).toBe(2)
    expect(badges[0].text()).toBe('danbooru')
    expect(badges[1].text()).toBe('rule34')

    // Click on the rule34 badge
    await badges[1].trigger('click')

    expect((wrapper.vm as any).activeSite).toBe('rule34')
    expect((wrapper.vm as any).mediaUrl).toBe('https://test.com/rule34.jpg')
    expect(wrapper.find('.post-card-rating').text()).toBe('E')
    expect(wrapper.find('.post-detail-info-row:nth-child(4) .post-detail-info-value').text()).toBe('★ 50')

    // Assert router replace was called to keep URL query parameters in sync
    expect(mockRouter.replace).toHaveBeenCalledWith({
      query: {
        id: '456',
        site: 'rule34'
      }
    })
  })

  it('should automatically resolve parent post even if landing directly on duplicate URL query', async () => {
    mockRoute.query = { id: '456', site: 'rule34' }

    const mockPostMultiple = {
      id: 123,
      source_site: 'danbooru',
      file_url: 'https://test.com/danbooru.jpg',
      rating: 's',
      tags: ['tag1'],
      width: 100,
      height: 100,
      score: 10,
      duplicate_sites: ['rule34'],
      duplicates: [
        {
          id: 456,
          source_site: 'rule34',
          file_url: 'https://test.com/rule34.jpg',
          rating: 'e',
          tags: ['tag1', 'lewd'],
          width: 150,
          height: 150,
          score: 50
        }
      ]
    }

    const wrapper = mount(PostView, {
      global: {
        plugins: [createTestingPinia({
          createSpy: vi.fn,
          initialState: {
            lang: { t: (key: string) => key },
            feed: {
              posts: [mockPostMultiple]
            }
          }
        })]
      }
    })

    // Allow onMounted ticks
    await new Promise((resolve) => setTimeout(resolve, 0))

    // Assert it successfully resolves mainPost and sets rule34 as activeSite
    expect((wrapper.vm as any).mainPost).not.toBeNull()
    expect((wrapper.vm as any).mainPost.id).toBe(123)
    expect((wrapper.vm as any).activeSite).toBe('rule34')
    expect((wrapper.vm as any).mediaUrl).toBe('https://test.com/rule34.jpg')
    expect(wrapper.find('.post-card-rating').text()).toBe('E')
  })

  it('should render parent/child relationships panel if parent_id or has_children exists', async () => {
    const mockPostWithParent = {
      id: 123,
      source_site: 'danbooru',
      file_url: 'https://test.com/danbooru.jpg',
      rating: 's',
      tags: ['tag1'],
      width: 100,
      height: 100,
      score: 10,
      parent_id: 999,
      has_children: false
    }

    // Mock apiSearch implementation for this test
    const { apiSearch } = await import('../api')
    vi.mocked(apiSearch).mockImplementation(((tags: string) => {
      if (tags.includes('id:999')) {
        return Promise.resolve({
          posts: [{
            id: 999,
            source_site: 'danbooru',
            preview_url: 'https://test.com/sibling.jpg',
            file_url: 'https://test.com/sibling.jpg',
            rating: 's',
            tags: ['tag1'],
            width: 100,
            height: 100,
            score: 5
          }],
          page: 1,
          total: 1,
          unfiltered_count: 1,
          resolved_tags: ''
        })
      }
      if (tags.includes('parent:999')) {
        return Promise.resolve({
          posts: [
            {
              id: 999,
              source_site: 'danbooru',
              preview_url: 'https://test.com/sibling.jpg',
              file_url: 'https://test.com/sibling.jpg',
              rating: 's',
              tags: ['tag1'],
              width: 100,
              height: 100,
              score: 5
            },
            {
              id: 123,
              source_site: 'danbooru',
              preview_url: 'https://test.com/danbooru.jpg',
              file_url: 'https://test.com/danbooru.jpg',
              rating: 's',
              tags: ['tag1'],
              width: 100,
              height: 100,
              score: 10
            }
          ],
          page: 1,
          total: 2,
          unfiltered_count: 2,
          resolved_tags: ''
        })
      }
      return Promise.resolve({ posts: [], page: 1, total: 0, unfiltered_count: 0, resolved_tags: '' })
    }) as any)

    const wrapper = mount(PostView, {
      global: {
        plugins: [createTestingPinia({
          createSpy: vi.fn,
          initialState: {
            lang: { t: (key: string) => key },
            feed: {
              posts: [mockPostWithParent]
            }
          }
        })]
      }
    })

    const lang = useLangStore()
    vi.mocked(lang.t).mockImplementation((key: string) => key)

    // Allow async ticks for onMounted and api calls
    await new Promise((resolve) => setTimeout(resolve, 50))
    await wrapper.vm.$nextTick()

    // Assert that the panel is visible and contains correct text and sibling thumbnails
    expect(wrapper.find('.post-relationship-panel').exists()).toBe(true)
    expect(wrapper.find('.post-relationship-header').text()).toContain('post_has_parent')
    
    const thumbs = wrapper.findAll('.post-relationship-thumb')
    expect(thumbs.length).toBe(2)
    expect(thumbs[0].attributes('src')).toBe('https://test.com/sibling.jpg')
    expect(thumbs[1].attributes('src')).toBe('https://test.com/danbooru.jpg')
    expect(thumbs[1].classes()).toContain('active')
  })

  it('should use a static image for backdropUrl and getPostThumbnail even if media is a video', async () => {
    const mockVideoPost = {
      id: 123,
      source_site: 'danbooru',
      preview_url: 'https://test.com/preview.jpg',
      sample_url: 'https://test.com/sample.mp4',
      file_url: 'https://test.com/file.mp4',
      rating: 's',
      tags: ['tag1'],
      width: 100,
      height: 100,
      parent_id: null,
      has_children: false
    }

    const wrapper = mount(PostView, {
      global: {
        plugins: [createTestingPinia({
          createSpy: vi.fn,
          initialState: {
            lang: { t: (key: string) => key },
            feed: {
              posts: [mockVideoPost]
            }
          }
        })]
      }
    })

    // Allow onMounted ticks
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect((wrapper.vm as any).backdropUrl).toBe('https://test.com/preview.jpg')
    expect((wrapper.vm as any).getPostThumbnail(mockVideoPost)).toBe('https://test.com/preview.jpg')
  })
})

