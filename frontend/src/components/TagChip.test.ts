import { mount } from '@vue/test-utils'
import { describe, it, expect, vi } from 'vitest'
import TagChip from './TagChip.vue'

describe('TagChip.vue', () => {
  it('should render the tag text with underscores replaced by spaces', () => {
    const wrapper = mount(TagChip, {
      props: {
        tag: 'cool_tag_name'
      },
      global: {
        mocks: {
          $router: {
            push: vi.fn()
          }
        }
      }
    })
    
    expect(wrapper.text()).toBe('cool tag name')
  })

  it('should call router.push when clicked', async () => {
    const mockPush = vi.fn()
    const wrapper = mount(TagChip, {
      props: {
        tag: 'test_tag'
      },
      global: {
        mocks: {
          $router: {
            push: mockPush
          }
        }
      }
    })

    await wrapper.trigger('click')
    expect(mockPush).toHaveBeenCalledWith({
      name: 'feed',
      query: { tags: 'test_tag' }
    })
  })
})
