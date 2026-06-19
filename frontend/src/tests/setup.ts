import { vi } from 'vitest'

// Mock IntersectionObserver as a standard class for Vue components virtualization testing
class IntersectionObserverMock {
  private callback: ((entries: any[]) => void) | null = null

  constructor(callback: (entries: any[]) => void, _options?: any) {
    this.callback = callback
  }

  observe(el: any) {
    if (this.callback) {
      this.callback([{ target: el, isIntersecting: true }])
    }
  }

  unobserve(_el: any) {}

  disconnect() {}
}

vi.stubGlobal('IntersectionObserver', IntersectionObserverMock)
