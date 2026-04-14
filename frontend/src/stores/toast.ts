import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { ToastItem } from '../types'

export const useToastStore = defineStore('toast', () => {
  const toasts = ref<ToastItem[]>([])
  let nextId = 0

  function show(message: string, type: 'success' | 'error' | 'info' = 'info') {
    const id = nextId++
    const icons: Record<string, string> = { success: '✓', error: '✕', info: 'ℹ' }

    toasts.value.push({
      id,
      message,
      type,
      icon: icons[type] || 'ℹ',
      removing: false,
    })

    setTimeout(() => {
      remove(id)
    }, 3000)
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

  return { toasts, show }
})
