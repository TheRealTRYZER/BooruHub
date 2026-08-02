import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { ToastItem } from '../types'

export const useToastStore = defineStore('toast', () => {
  const toasts = ref<ToastItem[]>([])
  let nextId = 0

  // Suppress identical messages spammed in rapid succession (e.g. repeated 429
  // rate-limit errors from the infinite-scroll auto-retry loop).
  let lastDupMsg = ''
  let lastDupTime = 0
  const DUP_WINDOW_MS = 1500

  function show(message: string, type: 'success' | 'error' | 'info' = 'info', action?: { label: string; callback: () => void }) {
    const now = Date.now()
    if (!action && message === lastDupMsg && now - lastDupTime < DUP_WINDOW_MS) {
      return
    }
    lastDupMsg = message
    lastDupTime = now

    const id = nextId++
    const icons: Record<string, string> = { success: '✓', error: '✕', info: 'ℹ' }

    toasts.value.push({
      id,
      message,
      type,
      icon: icons[type] || 'ℹ',
      removing: false,
      action
    })

    setTimeout(() => {
      remove(id)
    }, action ? 6000 : 3000)
  }

  function remove(id: number) {
    const t = toasts.value.find(x => x.id === id)
    if (t) {
      t.removing = true
      setTimeout(() => {
        toasts.value = toasts.value.filter(x => x.id !== id)
      }, 300)
    }
  }

  return { toasts, show, remove }
})
