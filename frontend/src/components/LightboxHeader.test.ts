import { mount } from '@vue/test-utils'
import { describe, it, expect, vi } from 'vitest'
import { createTestingPinia } from '@pinia/testing'
import LightboxHeader from './LightboxHeader.vue'
import { useLangStore } from '../stores/lang'
import type { Post } from '../types'

describe('LightboxHeader.vue', () => {
  it('should render header details and emit switchSite', async () => {
    const mockPost = {
      id: 123,
      source_site: 'danbooru' as const,
      rating: 's',
      width: 1000,
      height: 1000,
      score: 42
    } as unknown as Post

    const pinia = createTestingPinia({
      createSpy: vi.fn
    })
    const lang = useLangStore(pinia)
    vi.mocked(lang.t).mockImplementation((key: string) => key)

    const wrapper = mount(LightboxHeader, {
      props: {
        displayedPost: mockPost,
        activePost: mockPost,
        allSites: ['danbooru', 'rule34'],
        activeSite: 'danbooru'
      },
      global: {
        plugins: [pinia]
      }
    })

    expect(wrapper.find('.lightbox-id').text()).toContain('#123')
    expect(wrapper.find('.lightbox-resolution').text()).toBe('1000x1000')
    expect(wrapper.find('.lightbox-score').text()).toContain('★ 42')

    // Click interactive badge
    const badges = wrapper.findAll('.lightbox-site-badge')
    expect(badges.length).toBe(2)
    await badges[1]?.trigger('click')
    expect(wrapper.emitted('switchSite')?.[0]).toEqual(['rule34'])
  })
})
