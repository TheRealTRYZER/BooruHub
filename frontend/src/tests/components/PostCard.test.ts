import { mount } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createTestingPinia } from '@pinia/testing'
import PostCard from '../../components/PostCard.vue'

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

  it('should render post metadata correctly', async () => {
    const wrapper = mount(PostCard, {
      props: {
        post: mockPost as any,
        isOffScreen: false,
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

    await wrapper.vm.$nextTick()

    expect(wrapper.find('.post-card-badge.danbooru').text()).toBe('danbooru')
    expect(wrapper.find('.post-card-rating').text()).toBe('S')
  })

  it('should toggle favorite status when button is clicked', async () => {
    const wrapper = mount(PostCard, {
      props: {
        post: mockPost as any,
        isOffScreen: false,
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

    await wrapper.vm.$nextTick()

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
        post: mockMultiplePost as any,
        isOffScreen: false,
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

    await wrapper.vm.$nextTick()

    // Both danbooru and + rule34 badges should be present
    const badges = wrapper.findAll('.post-card-badge.interactive-badge')
    expect(badges.length).toBe(2)
    
    const badge0 = badges[0]
    const badge1 = badges[1]
    expect(badge0).toBeDefined()
    expect(badge1).toBeDefined()

    if (badge0 && badge1) {
      expect(badge0.text()).toBe('danbooru')
      expect(badge1.text()).toBe('+ rule34')

      // Danbooru badge should initially be the active site version
      expect(badge0.classes()).toContain('active-site')
      expect((wrapper.vm as any).activeSite).toBe('danbooru')
      expect((wrapper.vm as any).currentUrl).toBe('https://test.com/danbooru-prev.jpg')

      // Switch to Rule34 version by clicking its badge
      await badge1.trigger('click')
    }

    expect((wrapper.vm as any).activeSite).toBe('rule34')
    expect((wrapper.vm as any).currentUrl).toBe('https://test.com/rule34-prev.jpg')
    expect(wrapper.find('.post-card-rating').text()).toBe('E')
    expect(wrapper.find('.post-card-score').text()).toBe('★ 45')
  })

  it('should filter out video URLs when resolving preview image source', async () => {
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
      hash: 'existing-hash'
    }

    const wrapper = mount(PostCard, {
      props: {
        post: mockVideoPost as any
      },
      global: {
        plugins: [createTestingPinia({
          createSpy: vi.fn,
          initialState: {
            feed: { previewQuality: 'full' },
            lang: { t: (key: string) => key }
          }
        })],
      }
    })

    expect((wrapper.vm as any).currentUrl).toBe('https://test.com/preview.jpg')
  })

  it('should not allow guest users to swipe-dislike', async () => {
    const wrapper = mount(PostCard, {
      props: {
        post: mockPost as any
      },
      global: {
        plugins: [createTestingPinia({
          createSpy: vi.fn,
          initialState: {
            auth: { isAuthenticated: false },
            lang: { t: (key: string) => key }
          }
        })],
      }
    })

    const vm = wrapper.vm as any
    vm.swipeDiff = -100 // Swiped left
    vm.onTouchEnd()

    expect(vm.swipeDiff).toBe(0) // Should have snapped back
  })

  it('should render a crop canvas host instead of img for very tall static posts', async () => {
    const longPost = {
      id: 321,
      source_site: 'rule34',
      preview_url: 'https://test.com/prev.jpg',
      sample_url: 'https://test.com/sample.jpg',
      file_url: 'https://test.com/original.jpg',
      file_ext: 'jpg',
      rating: 'e',
      tags: ['tag1'],
      width: 1000,
      height: 10000,
    }

    const wrapper = mount(PostCard, {
      props: { post: longPost as any, isOffScreen: false },
      global: {
        plugins: [createTestingPinia({
          createSpy: vi.fn,
          initialState: { lang: { t: (key: string) => key } }
        })],
      }
    })

    await wrapper.vm.$nextTick()

    expect((wrapper.vm as any).isLong).toBe(true)
    expect((wrapper.vm as any).useCrop).toBe(true)
    expect(wrapper.find('.post-card-crop-host').exists()).toBe(true)
    expect(wrapper.find('.post-card-img').exists()).toBe(false)
  })

  it('should keep the plain img path for very tall animated posts', async () => {
    const longAnimatedPost = {
      id: 654,
      source_site: 'rule34',
      preview_url: 'https://test.com/prev.jpg',
      sample_url: 'https://test.com/sample.jpg',
      file_url: 'https://test.com/original.gif',
      file_ext: 'gif',
      rating: 'e',
      tags: ['tag1'],
      width: 1000,
      height: 10000,
    }

    const wrapper = mount(PostCard, {
      props: { post: longAnimatedPost as any, isOffScreen: false },
      global: {
        plugins: [createTestingPinia({
          createSpy: vi.fn,
          initialState: { lang: { t: (key: string) => key } }
        })],
      }
    })

    await wrapper.vm.$nextTick()

    expect((wrapper.vm as any).isLong).toBe(true)
    expect((wrapper.vm as any).useCrop).toBe(false)
    const img = wrapper.find('.post-card-img')
    expect(img.exists()).toBe(true)
    expect(img.classes()).toContain('post-card-img-cropped')
  })
})
