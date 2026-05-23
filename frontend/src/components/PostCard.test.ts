import { mount } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createTestingPinia } from '@pinia/testing'
import PostCard from './PostCard.vue'

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: vi.fn()
  })
}))



beforeEach(() => {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  })
})

describe('PostCard.vue', () => {
  const mockPost = {
    id: 123,
    source_site: 'danbooru',
    preview_url: 'https://test.com/img.jpg',
    rating: 's',
    tags: ['tag1', 'tag2'],
    width: 100,
    height: 100,
    hash: 'existing-hash' // Set hash to render card instantly
  }

  it('should render post metadata correctly', () => {
    const wrapper = mount(PostCard, {
      props: {
        post: mockPost as any
      },
      global: {
        plugins: [createTestingPinia({
          createSpy: vi.fn,
          initialState: {
            lang: { 
              t: (key: string) => key 
            }
          }
        })],
      }
    })

    expect(wrapper.find('.post-card-badge.danbooru').text()).toBe('danbooru')
    expect(wrapper.find('.post-card-rating').text()).toBe('S')
  })

  it('should toggle favorite status when button is clicked', async () => {
    const wrapper = mount(PostCard, {
      props: {
        post: mockPost as any
      },
      global: {
        plugins: [createTestingPinia({
          createSpy: vi.fn,
          initialState: {
            auth: { isAuthenticated: true },
            lang: { t: (key: string) => key }
          }
        })],
        mocks: {
          $router: { push: vi.fn() }
        }
      }
    })

    const favBtn = wrapper.find('.post-card-fav')
    expect(favBtn.text()).toBe('🤍')
    await favBtn.trigger('click')
  })

  it('should reactively update currentUrl based on feed store previewQuality', async () => {
    const mockPostExtended = {
      id: 123,
      source_site: 'danbooru',
      preview_url: 'https://test.com/preview.jpg',
      sample_url: 'https://test.com/sample.jpg',
      file_url: 'https://test.com/file.jpg',
      rating: 's',
      tags: ['tag1'],
      width: 100,
      height: 100,
      hash: 'existing-hash' // Set hash to render card instantly
    }

    const wrapper = mount(PostCard, {
      props: {
        post: mockPostExtended as any
      },
      global: {
        plugins: [createTestingPinia({
          createSpy: vi.fn,
          initialState: {
            feed: { previewQuality: 'thumbnail' },
            lang: { t: (key: string) => key }
          }
        })],
      }
    })

    expect((wrapper.vm as any).currentUrl).toBe('https://test.com/preview.jpg')
  })



  it('should support switching between site versions when badges are clicked', async () => {
    const mockMultiplePost = {
      id: 111,
      source_site: 'danbooru',
      preview_url: 'https://test.com/danbooru-prev.jpg',
      rating: 's',
      tags: ['tag1'],
      width: 100,
      height: 100,
      hash: 'resolved-hash',
      duplicate_sites: ['rule34'],
      duplicates: [
        {
          id: 222,
          source_site: 'rule34',
          preview_url: 'https://test.com/rule34-prev.jpg',
          rating: 'e',
          tags: ['tag1', 'lewd'],
          width: 120,
          height: 120,
          score: 45
        }
      ]
    }

    const wrapper = mount(PostCard, {
      props: {
        post: mockMultiplePost as any
      },
      global: {
        plugins: [createTestingPinia({
          createSpy: vi.fn,
          initialState: {
            lang: { t: (key: string) => key }
          }
        })],
      }
    })

    // Both danbooru and + rule34 badges should be present
    const badges = wrapper.findAll('.post-card-badge.interactive-badge')
    expect(badges.length).toBe(2)
    expect(badges[0].text()).toBe('danbooru')
    expect(badges[1].text()).toBe('+ rule34')

    // Danbooru badge should initially be the active site version
    expect(badges[0].classes()).toContain('active-site')
    expect((wrapper.vm as any).activeSite).toBe('danbooru')
    expect((wrapper.vm as any).currentUrl).toBe('https://test.com/danbooru-prev.jpg')

    // Switch to Rule34 version by clicking its badge
    await badges[1].trigger('click')

    expect((wrapper.vm as any).activeSite).toBe('rule34')
    expect((wrapper.vm as any).currentUrl).toBe('https://test.com/rule34-prev.jpg')
    expect(wrapper.find('.post-card-rating').text()).toBe('E')
    expect(wrapper.find('.post-card-score').text()).toBe('★ 45')
  })
})
