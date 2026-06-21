import { mount } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createTestingPinia } from '@pinia/testing'
import LightboxModal from './LightboxModal.vue'
import { useLangStore } from '../stores/lang'
import type { Post } from '../types'

const mockRouter = {
  push: vi.fn(),
  replace: vi.fn()
}

vi.mock('vue-router', () => ({
  useRouter: () => mockRouter
}))

vi.mock('../api', () => ({
  apiCheckFavorite: vi.fn(() => Promise.resolve({ is_favorite: false, favorite_id: null })),
  apiAddFavorite: vi.fn(() => Promise.resolve()),
  apiRemoveFavorite: vi.fn(() => Promise.resolve()),
  apiSearch: vi.fn(() => Promise.resolve({ posts: [] })),
  registerAuthFailureCallback: vi.fn()
}))

describe('LightboxModal.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should render standard modal elements correctly', async () => {
    const mockPost = {
      id: 123,
      source_site: 'danbooru' as const,
      file_url: 'https://test.com/danbooru.jpg',
      rating: 's',
      tags: ['tag1', 'tag2'],
      width: 100,
      height: 100,
      score: 10
    } as unknown as Post

    const wrapper = mount(LightboxModal, {
      props: {
        post: mockPost,
        posts: [mockPost]
      },
      global: {
        plugins: [createTestingPinia({
          createSpy: vi.fn,
          initialState: {
            lang: { t: (key: string) => key }
          }
        })]
      }
    })

    await wrapper.vm.$nextTick()
    expect(wrapper.find('.lightbox-media.image').attributes('src')).toBe('https://test.com/danbooru.jpg')
    expect(wrapper.find('.lightbox-id').text()).toContain('#123')
  })

  it('should render parent/child relationships panel if parent_id or has_children exists', async () => {
    const mockPostWithParent = {
      id: 123,
      source_site: 'danbooru' as const,
      file_url: 'https://test.com/danbooru.jpg',
      rating: 's',
      tags: ['tag1'],
      width: 100,
      height: 100,
      score: 10,
      parent_id: 999,
      has_children: false
    } as unknown as Post

    const { apiSearch } = await import('../api')
    vi.mocked(apiSearch).mockImplementation(((tags: string) => {
      if (tags.includes('id:999')) {
        return Promise.resolve({
          posts: [{
            id: 999,
            source_site: 'danbooru',
            preview_url: 'https://test.com/parent.jpg',
            file_url: 'https://test.com/parent.jpg',
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
              preview_url: 'https://test.com/parent.jpg',
              file_url: 'https://test.com/parent.jpg',
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

    const wrapper = mount(LightboxModal, {
      props: {
        post: mockPostWithParent,
        posts: [mockPostWithParent]
      },
      global: {
        plugins: [createTestingPinia({
          createSpy: vi.fn,
          initialState: {
            lang: { t: (key: string) => key }
          }
        })]
      }
    })

    const lang = useLangStore()
    vi.mocked(lang.t).mockImplementation((key: string) => key)

    // Wait for the watchers and async API calls
    await new Promise((resolve) => setTimeout(resolve, 50))
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.post-relationship-panel').exists()).toBe(true)
    expect(wrapper.find('.post-relationship-header').text()).toContain('post_has_parent')

    const thumbs = wrapper.findAll('.post-relationship-thumb')
    expect(thumbs.length).toBe(2)
    expect(thumbs[0]?.attributes('src')).toBe('https://test.com/parent.jpg')
    expect(thumbs[1]?.attributes('src')).toBe('https://test.com/danbooru.jpg')
    expect(thumbs[1]?.classes()).toContain('active')

    // Click the parent thumbnail and verify active post updates
    await thumbs[0]?.trigger('click')
    await wrapper.vm.$nextTick()
    expect((wrapper.vm as any).displayedPost.id).toBe(999)
  })
})
