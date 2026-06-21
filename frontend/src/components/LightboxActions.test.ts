import { mount } from '@vue/test-utils'
import { describe, it, expect, vi } from 'vitest'
import { createTestingPinia } from '@pinia/testing'
import LightboxActions from './LightboxActions.vue'
import { useLangStore } from '../stores/lang'

describe('LightboxActions.vue', () => {
  it('should render actions buttons and emit events when clicked', async () => {
    const pinia = createTestingPinia({
      createSpy: vi.fn
    })
    const lang = useLangStore(pinia)
    vi.mocked(lang.t).mockImplementation((key: string) => key)

    const wrapper = mount(LightboxActions, {
      props: {
        isFav: true,
        isDisliked: false
      },
      global: {
        plugins: [pinia]
      }
    })

    const buttons = wrapper.findAll('button')
    expect(buttons.length).toBe(4)

    // Check favorite button has active class
    expect(buttons[0]?.classes()).toContain('btn-fav-active')
    expect(buttons[1]?.classes()).not.toContain('btn-dislike-active')

    await buttons[0]?.trigger('click')
    expect(wrapper.emitted('toggleFav')).toBeTruthy()

    await buttons[1]?.trigger('click')
    expect(wrapper.emitted('toggleDislike')).toBeTruthy()

    await buttons[2]?.trigger('click')
    expect(wrapper.emitted('download')).toBeTruthy()

    await buttons[3]?.trigger('click')
    expect(wrapper.emitted('openOriginal')).toBeTruthy()
  })
})
