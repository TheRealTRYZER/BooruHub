import { mount } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createTestingPinia } from '@pinia/testing'
import { nextTick } from 'vue'
import SearchToolbar from '../../components/SearchToolbar.vue'
import { useFeedStore } from '../../stores/feed'

vi.mock('../../api', () => ({
  apiSuggestTags: vi.fn(() => Promise.resolve({ suggestions: [{ tag: 'solo', category: 'general', post_count: 100 }] })),
  apiAddBookmark: vi.fn(() => Promise.resolve()),
  registerAuthFailureCallback: vi.fn()
}))

describe('SearchToolbar.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should render a text input populated with feed.tags', async () => {
    const wrapper = mount(SearchToolbar, {
      global: {
        plugins: [createTestingPinia({
          createSpy: vi.fn,
          initialState: {
            lang: { t: (key: string) => key },
            feed: {
              tags: '1girl solo',
              sites: ['danbooru'],
              isSplit: false
            },
            auth: {
              isAuthenticated: true
            }
          }
        })]
      }
    })
    
    await nextTick()
    const input = wrapper.find('.search-input-element')
    expect(input.exists()).toBe(true)
    expect((input.element as HTMLInputElement).value).toBe('1girl solo')
  })

  it('should update feed.tags when the input value changes', async () => {
    const wrapper = mount(SearchToolbar, {
      global: {
        plugins: [createTestingPinia({
          createSpy: vi.fn,
          initialState: {
            lang: { t: (key: string) => key },
            feed: {
              tags: '',
              sites: ['danbooru'],
              isSplit: false
            },
            auth: {
              isAuthenticated: true
            }
          }
        })]
      }
    })
    
    const store = useFeedStore()
    const input = wrapper.find('.search-input-element')
    await input.setValue('test_tag')
    expect(store.tags).toBe('test_tag')
  })
})
