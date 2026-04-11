import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useToastStore = defineStore('toast', () => {
  const toasts = ref([])
  let nextId = 0

  function show(message, type = 'info') {
    const id = nextId++
    const icons = { success: '✓', error: '✕', info: 'ℹ' }
    
    toasts.value.push({
      id,
      message,
      type,
      icon: icons[type] || 'ℹ',
      removing: false
    })

    setTimeout(() => {
      remove(id)
    }, 3000)
  }

  function remove(id) {
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
