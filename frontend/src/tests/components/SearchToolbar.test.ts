import { mount } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createTestingPinia } from '@pinia/testing'
import { nextTick } from 'vue'
import SearchToolbar from '../../components/SearchToolbar.vue'
import { useFeedStore } from '../../stores/feed'
import { useLangStore } from '../../stores/lang'
import { apiSuggestTags } from '../../api'
import type { TagSuggestion } from '../../types'

vi.mock('../../api', () => ({
  apiSuggestTags: vi.fn(() => Promise.resolve({ suggestions: [{ tag: 'solo', category: 'general', post_count: 100 }] })),
  apiAddBookmark: vi.fn(() => Promise.resolve()),
  registerAuthFailureCallback: vi.fn()
}))

const mockedSuggest = vi.mocked(apiSuggestTags)

function tag(name: string, extra: Partial<TagSuggestion> = {}): TagSuggestion {
  return { tag: name, is_mapped: false, ...extra }
}

function mountToolbar(tags = '') {
  const pinia = createTestingPinia({
    createSpy: vi.fn,
    initialState: {
      feed: { tags, sites: ['danbooru'], isSplit: false },
      auth: { isAuthenticated: true }
    }
  })
  const lang = useLangStore(pinia)
  vi.mocked(lang.t).mockImplementation(
    (key: string, params?: Record<string, unknown>) =>
      params ? `${key} ${JSON.stringify(params)}` : key
  )

  const wrapper = mount(SearchToolbar, {
    attachTo: document.body,
    global: { plugins: [pinia] }
  })
  return { wrapper, store: useFeedStore(pinia) }
}

async function flush() {
  await Promise.resolve()
  await Promise.resolve()
  await nextTick()
}

describe('SearchToolbar.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('should render a text input populated with feed.tags', async () => {
    const { wrapper } = mountToolbar('1girl solo')

    await nextTick()
    const input = wrapper.find('.search-input-element')
    expect(input.exists()).toBe(true)
    expect((input.element as HTMLInputElement).value).toBe('1girl solo')
    wrapper.unmount()
  })

  it('should update feed.tags when the input value changes', async () => {
    const { wrapper, store } = mountToolbar()
    const input = wrapper.find('.search-input-element')
    await input.setValue('test_tag')
    expect(store.tags).toBe('test_tag')
    wrapper.unmount()
  })

  describe('tag suggestions', () => {
    it('keeps the visible rows in place when the remote pass re-ranks them', async () => {
      vi.useFakeTimers()
      mockedSuggest.mockImplementation((_q, _limit, _signal, fast) =>
        fast
          ? Promise.resolve({ suggestions: [tag('aaa'), tag('bbb')] })
          : Promise.resolve({ suggestions: [tag('bbb'), tag('aaa'), tag('aardvark')] })
      )

      const { wrapper } = mountToolbar()
      const input = wrapper.find('.search-input-element')
      await input.setValue('aa')
      await flush()
      await vi.advanceTimersByTimeAsync(300)
      await flush()

      expect(wrapper.findAll('.search-suggestion-item').map(el => el.text())).toEqual(['aaa', 'bbb', 'aardvark'])
      wrapper.unmount()
    })

    it('brings the list back when focus returns instead of waiting for another keystroke', async () => {
      vi.useFakeTimers()
      mockedSuggest.mockResolvedValue({ suggestions: [tag('solo')] })

      const { wrapper } = mountToolbar('so')
      const input = wrapper.find('.search-input-element')

      await input.trigger('focus')
      await flush()
      expect(wrapper.find('.search-suggestions.visible').exists()).toBe(true)

      await input.trigger('blur')
      await input.trigger('focus')
      await vi.advanceTimersByTimeAsync(200)
      await flush()

      expect(wrapper.find('.search-suggestions.visible').exists()).toBe(true)
      wrapper.unmount()
    })

    it('closes the list once focus really leaves the input', async () => {
      vi.useFakeTimers()
      mockedSuggest.mockResolvedValue({ suggestions: [tag('solo')] })

      const { wrapper } = mountToolbar('so')
      const input = wrapper.find('.search-input-element')

      await input.trigger('focus')
      await flush()
      expect(wrapper.find('.search-suggestions.visible').exists()).toBe(true)

      await input.trigger('blur')
      await vi.advanceTimersByTimeAsync(200)
      await flush()

      expect(wrapper.find('.search-suggestions.visible').exists()).toBe(false)
      wrapper.unmount()
    })

    it('fills in the word being typed after a completed tag', async () => {
      mockedSuggest.mockResolvedValue({ suggestions: [tag('solo')] })

      const { wrapper } = mountToolbar('1girl')
      const input = wrapper.find('.search-input-element')
      await input.setValue('1girl so')
      await flush()

      expect(mockedSuggest).toHaveBeenCalledWith('so', expect.any(Number), expect.anything(), true)

      await input.setValue('1girl -so')
      await flush()
      expect(mockedSuggest).toHaveBeenLastCalledWith('so', expect.any(Number), expect.anything(), true)

      wrapper.unmount()
    })

    it('accepts a suggestion with a click and re-focuses the input', async () => {
      mockedSuggest.mockResolvedValue({ suggestions: [tag('solo')] })

      const { wrapper } = mountToolbar('so')
      const input = wrapper.find('.search-input-element')
      await input.trigger('focus')
      await flush()

      const rows = wrapper.findAll('.search-suggestion-item')
      expect(rows).toHaveLength(1)
      await rows[0]!.trigger('mousedown')

      expect((input.element as HTMLInputElement).value).toBe('solo ')
      wrapper.unmount()
    })
  })

  describe('posts per row control', () => {
    it('shows how many cards currently fit in a row', async () => {
      const { wrapper, store } = mountToolbar()
      store.cardSize = 250

      await nextTick()
      expect(wrapper.find('.col-select-count').text()).toBe(String(Math.floor((window.innerWidth - 48 + 16) / (250 + 16))))
      wrapper.unmount()
    })

    it('turns a chosen column count into a card size the grid can honour', async () => {
      const { wrapper, store } = mountToolbar()

      await wrapper.find('.col-select-btn').trigger('click')
      const items = wrapper.findAll('.col-dropdown-item')
      expect(items).toHaveLength(10)

      // COL_OPTIONS = [1, 2, 3, 4, ...] and the label goes through lang.t.
      const fourLabel = items[3]!
      expect(fourLabel.text()).toContain('"count":4')
      await fourLabel.trigger('click')
      await nextTick()

      const gap = 16
      const cols = Math.floor((window.innerWidth - 48 + gap) / (store.cardSize + gap))
      expect(cols).toBe(4)
      expect(wrapper.find('.col-dropdown-menu').exists()).toBe(false)
      wrapper.unmount()
    })
  })
})
