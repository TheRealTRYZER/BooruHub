import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { defineComponent, h, nextTick } from 'vue'
import { mount } from '@vue/test-utils'
import { useTagSuggestions } from './useTagSuggestions'
import { apiSuggestTags } from '../api'
import type { TagSuggestion } from '../types'

vi.mock('../api', () => ({
  apiSuggestTags: vi.fn()
}))

const mockedSuggest = vi.mocked(apiSuggestTags)

function tag(name: string, extra: Partial<TagSuggestion> = {}): TagSuggestion {
  return { tag: name, is_mapped: false, ...extra }
}

/**
 * Mounts a throwaway component so the composable's `onUnmounted` cleanup has an
 * owner, and hands back a disposer for the same reason.
 */
function withSetup<T>(fn: () => T) {
  let result!: T
  const wrapper = mount(
    defineComponent({
      setup() {
        result = fn()
        return () => h('div')
      }
    })
  )
  return { result, dispose: () => wrapper.unmount() }
}

async function flush() {
  await Promise.resolve()
  await Promise.resolve()
  await nextTick()
}

describe('useTagSuggestions', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('shows the local-only pass immediately, without waiting for the debounce', async () => {
    mockedSuggest.mockImplementation((_q, _limit, _signal, fast) =>
      fast
        ? Promise.resolve({ suggestions: [tag('solo')] })
        : Promise.resolve({ suggestions: [tag('solo'), tag('solol')] })
    )

    const { result, dispose } = withSetup(() => useTagSuggestions())
    result.query('so')

    await flush()
    expect(result.items.value.map(t => t.tag)).toEqual(['solo'])

    dispose()
  })

  it('keeps the visible order stable when the remote pass re-ranks the list', async () => {
    mockedSuggest.mockImplementation((_q, _limit, _signal, fast) =>
      fast
        ? Promise.resolve({ suggestions: [tag('aaa'), tag('bbb')] })
        : Promise.resolve({ suggestions: [tag('bbb'), tag('aaa'), tag('aardvark', { post_count: 9 })] })
    )

    const { result, dispose } = withSetup(() => useTagSuggestions())
    result.query('aa')

    await flush()
    expect(result.items.value.map(t => t.tag)).toEqual(['aaa', 'bbb'])

    await vi.advanceTimersByTimeAsync(300)
    await flush()

    // 'bbb' outranks 'aaa' remotely, but the rows must not jump under the cursor.
    expect(result.items.value.map(t => t.tag)).toEqual(['aaa', 'bbb', 'aardvark'])

    dispose()
  })

  it('enriches rows in place instead of dropping what the local pass knew', async () => {
    mockedSuggest.mockImplementation((_q, _limit, _signal, fast) =>
      fast
        ? Promise.resolve({ suggestions: [tag('cat_ears'), tag('catgirl', { search_count: 3 })] })
        : Promise.resolve({ suggestions: [tag('cat_ears', { category: 'general', post_count: 500, from_danbooru: true })] })
    )

    const { result, dispose } = withSetup(() => useTagSuggestions())
    result.query('cat')

    await flush()
    expect(result.items.value[1]?.search_count).toBe(3)

    await vi.advanceTimersByTimeAsync(300)
    await flush()

    const ears = result.items.value[0]
    expect(ears?.tag).toBe('cat_ears')
    expect(ears?.post_count).toBe(500)
    expect(ears?.from_danbooru).toBe(true)
    // A remote pass without the tag must not erase the "frequent" marker.
    expect(result.items.value[1]?.search_count).toBe(3)

    dispose()
  })

  it('shows remote-only matches when the local pass came back empty', async () => {
    mockedSuggest.mockImplementation((_q, _limit, _signal, fast) =>
      fast ? Promise.resolve({ suggestions: [] }) : Promise.resolve({ suggestions: [tag('zzz_exclusive')] })
    )

    const { result, dispose } = withSetup(() => useTagSuggestions())
    result.query('zz')

    await flush()
    expect(result.isOpen.value).toBe(false)

    await vi.advanceTimersByTimeAsync(300)
    await flush()

    expect(result.items.value.map(t => t.tag)).toEqual(['zzz_exclusive'])

    dispose()
  })

  it('does not clear visible rows when the remote pass fails', async () => {
    mockedSuggest.mockImplementation((_q, _limit, _signal, fast) =>
      fast ? Promise.resolve({ suggestions: [tag('solo')] }) : Promise.reject(new Error('HTTP 500'))
    )

    const { result, dispose } = withSetup(() => useTagSuggestions())
    result.query('so')

    await flush()
    await vi.advanceTimersByTimeAsync(300)
    await flush()

    expect(result.items.value.map(t => t.tag)).toEqual(['solo'])

    dispose()
  })

  it('ignores a prefix shorter than two characters', async () => {
    mockedSuggest.mockResolvedValue({ suggestions: [tag('a')] })

    const { result, dispose } = withSetup(() => useTagSuggestions())
    result.query('a')

    await flush()
    expect(apiSuggestTags).not.toHaveBeenCalled()
    expect(result.items.value).toEqual([])

    dispose()
  })

  it('drops a stale response when the prefix changed mid-flight', async () => {
    const slowResolvers: Array<(value: { suggestions: TagSuggestion[] }) => void> = []
    mockedSuggest.mockImplementation((_q, _limit, _signal, fast) =>
      fast
        ? Promise.resolve({ suggestions: [tag('ol_old')] })
        : new Promise(resolve => { slowResolvers.push(resolve) })
    )

    const { result, dispose } = withSetup(() => useTagSuggestions())
    result.query('ol')
    await flush()
    await vi.advanceTimersByTimeAsync(300)
    await flush()

    result.query('ne')
    await flush()

    slowResolvers[0]?.({ suggestions: [tag('ol_late')] })
    await flush()

    expect(result.items.value.map(t => t.tag)).toEqual(['ol_old'])

    dispose()
  })

  it('keeps the list open when focus returns inside the blur grace period', async () => {
    mockedSuggest.mockResolvedValue({ suggestions: [tag('solo')] })

    let focused = false
    const { result, dispose } = withSetup(() => useTagSuggestions({ isFocused: () => focused }))
    result.query('so')
    await flush()

    result.onBlur()
    focused = true
    result.onFocus()

    await vi.advanceTimersByTimeAsync(200)
    await flush()

    expect(result.items.value.map(t => t.tag)).toEqual(['solo'])

    dispose()
  })

  it('closes once focus is really gone and reports the close', async () => {
    mockedSuggest.mockResolvedValue({ suggestions: [tag('solo')] })
    const onClose = vi.fn()

    const { result, dispose } = withSetup(() => useTagSuggestions({ isFocused: () => false, onClose }))
    result.query('so')
    await flush()

    result.onBlur()
    await vi.advanceTimersByTimeAsync(200)
    await flush()

    expect(result.items.value).toEqual([])
    expect(onClose).toHaveBeenCalledTimes(1)

    dispose()
  })

  it('ignores responses once the owner went inactive', async () => {
    mockedSuggest.mockResolvedValue({ suggestions: [tag('solo')] })

    let active = true
    const { result, dispose } = withSetup(() => useTagSuggestions({ isActive: () => active }))
    result.query('so')

    active = false
    await flush()

    expect(result.items.value).toEqual([])

    dispose()
  })

  it('aborts pending work on unmount', async () => {
    let capturedSignal: AbortSignal | undefined
    mockedSuggest.mockImplementation((_q, _limit, signal) => {
      capturedSignal = signal
      return new Promise(() => {})
    })

    const { result, dispose } = withSetup(() => useTagSuggestions())
    result.query('so')
    await flush()

    expect(capturedSignal?.aborted).toBe(false)
    dispose()
    expect(capturedSignal?.aborted).toBe(true)
  })

  it('replaces the list instead of carrying leftovers into the next prefix', async () => {
    mockedSuggest.mockImplementation((q) =>
      Promise.resolve({ suggestions: [tag(`${q}_only`)] })
    )

    const { result, dispose } = withSetup(() => useTagSuggestions())
    result.query('ca')
    await flush()
    expect(result.items.value.map(t => t.tag)).toEqual(['ca_only'])

    result.query('cat')
    await flush()
    expect(result.items.value.map(t => t.tag)).toEqual(['cat_only'])

    dispose()
  })

  it('never lists the same tag twice when the remote pass drops one', async () => {
    mockedSuggest.mockImplementation((_q, _limit, _signal, fast) =>
      fast
        ? Promise.resolve({ suggestions: [tag('aaa'), tag('bbb')] })
        : Promise.resolve({ suggestions: [tag('aaa')] })
    )

    const { result, dispose } = withSetup(() => useTagSuggestions())
    result.query('aa')

    await flush()
    await vi.advanceTimersByTimeAsync(300)
    await flush()

    const tags = result.items.value.map(t => t.tag)
    expect(tags).toEqual(['aaa', 'bbb'])
    expect(new Set(tags).size).toBe(tags.length)

    dispose()
  })

  it('caps the merged list at the requested limit', async () => {
    const many = Array.from({ length: 10 }, (_, i) => tag(`t${i}`))
    mockedSuggest.mockImplementation((_q, _limit, _signal, fast) =>
      Promise.resolve({ suggestions: fast ? many.slice(0, 10) : many })
    )

    const { result, dispose } = withSetup(() => useTagSuggestions({ limit: 4 }))
    result.query('tt')

    await flush()
    await vi.advanceTimersByTimeAsync(300)
    await flush()

    expect(result.items.value).toHaveLength(4)

    dispose()
  })
})
