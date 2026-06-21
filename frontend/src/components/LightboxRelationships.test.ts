import { mount } from '@vue/test-utils'
import { describe, it, expect, vi } from 'vitest'
import { createTestingPinia } from '@pinia/testing'
import LightboxRelationships from './LightboxRelationships.vue'
import { useLangStore } from '../stores/lang'
import type { Post } from '../types'

describe('LightboxRelationships.vue', () => {
  it('should render post relationships list and emit navigate', async () => {
    const mockPost = {
      id: 123,
      source_site: 'danbooru',
      preview_url: 'https://test.com/123.jpg'
    } as unknown as Post

    const mockParent = {
      id: 999,
      source_site: 'danbooru',
      preview_url: 'https://test.com/999.jpg'
    } as unknown as Post

    const pinia = createTestingPinia({
      createSpy: vi.fn
    })
    const lang = useLangStore(pinia)
    vi.mocked(lang.t).mockImplementation((key: string) => key)

    const wrapper = mount(LightboxRelationships, {
      props: {
        displayedPost: mockPost,
        relationshipPosts: [mockParent, mockPost]
      },
      global: {
        plugins: [pinia]
      }
    })

    expect(wrapper.find('.post-relationship-panel').exists()).toBe(true)
    const thumbs = wrapper.findAll('.post-relationship-thumb')
    expect(thumbs.length).toBe(2)
    expect(thumbs[0]?.attributes('src')).toBe('https://test.com/999.jpg')
    expect(thumbs[1]?.attributes('src')).toBe('https://test.com/123.jpg')
    expect(thumbs[1]?.classes()).toContain('active')

    await thumbs[0]?.trigger('click')
    expect(wrapper.emitted('navigate')?.[0]).toEqual([mockParent])
  })
})
