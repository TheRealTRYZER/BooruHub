import { mount } from '@vue/test-utils'
import { describe, it, expect, vi } from 'vitest'
import { createTestingPinia } from '@pinia/testing'
import LightboxSidebar from './LightboxSidebar.vue'
import { useLangStore } from '../stores/lang'
import type { Post } from '../types'

describe('LightboxSidebar.vue', () => {
  it('should render grouped tags and emit searchTag when clicked', async () => {
    const mockPost = {
      id: 123,
      tags: ['artist_name', 'char_name', 'general_tag'],
      tags_metadata: {
        artist_name: 'artist',
        char_name: 'character',
        general_tag: 'general'
      }
    } as unknown as Post

    const pinia = createTestingPinia({
      createSpy: vi.fn
    })
    const lang = useLangStore(pinia)
    vi.mocked(lang.t).mockImplementation((key: string) => key)

    const wrapper = mount(LightboxSidebar, {
      props: {
        displayedPost: mockPost
      },
      global: {
        plugins: [pinia]
      }
    })

    expect(wrapper.find('.sidebar-title').text()).toContain('tags_count (3)')
    
    const chips = wrapper.findAll('.tag-chip')
    expect(chips.length).toBe(3)
    expect(chips[0]?.text()).toBe('artist name')

    await chips[0]?.trigger('click')
    expect(wrapper.emitted('searchTag')?.[0]).toEqual(['artist_name'])
  })
})
