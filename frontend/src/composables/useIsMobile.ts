import { ref, onUnmounted } from 'vue'

const isMobile = ref(false)
let mql: MediaQueryList | null = null
let initialized = false
let refCount = 0

function update(e: MediaQueryList | MediaQueryListEvent) {
  isMobile.value = e.matches
}

export function useIsMobile() {
  refCount++
  if (!initialized) {
    initialized = true
    mql = window.matchMedia('(max-width: 768px)')
    isMobile.value = mql.matches
    mql.addEventListener('change', update)
  }
  onUnmounted(() => {
    refCount--
    if (refCount <= 0 && mql) {
      mql.removeEventListener('change', update)
      mql = null
      initialized = false
      refCount = 0
    }
  })
  return isMobile
}
