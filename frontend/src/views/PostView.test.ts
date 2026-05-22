import { mount } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createTestingPinia } from '@pinia/testing'
import PostView from './PostView.vue'
import { useFeedStore } from '../stores/feed'

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
})
