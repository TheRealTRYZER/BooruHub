import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useToastStore } from '../../stores/toast'

describe('Toast Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
  })

  it('should add a toast when shown', () => {
    const store = useToastStore()
    store.show('hello', 'info')
    expect(store.toasts).toHaveLength(1)
    expect(store.toasts[0]?.message).toBe('hello')
  })

  it('should dedupe identical messages shown in rapid succession', () => {
    const store = useToastStore()
    store.show('Rate limit exceeded', 'error')
    store.show('Rate limit exceeded', 'error')
    store.show('Rate limit exceeded', 'error')
    expect(store.toasts).toHaveLength(1)

    // A different message still gets through
    store.show('Something else', 'error')
    expect(store.toasts).toHaveLength(2)
  })

  it('should allow the same message again after the dedupe window elapses', () => {
    const store = useToastStore()
    store.show('Rate limit exceeded', 'error')
    expect(store.toasts).toHaveLength(1)

    vi.advanceTimersByTime(1600)

    store.show('Rate limit exceeded', 'error')
    expect(store.toasts).toHaveLength(2)
  })

  it('should never dedupe toasts that carry an action button', () => {
    const store = useToastStore()
    const action = { label: 'Undo', callback: () => {} }
    store.show('Removed', 'info', action)
    store.show('Removed', 'info', action)
    expect(store.toasts).toHaveLength(2)
  })
})
