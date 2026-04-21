import { ref } from 'vue'

const STORAGE_KEY = 'booruhub_search_history'
const MAX_ITEMS = 20

function loadFromStorage(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed.slice(0, MAX_ITEMS) : []
  } catch {
    return []
  }
}

function saveToStorage(items: string[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(items.slice(0, MAX_ITEMS)))
}

const history = ref<string[]>(loadFromStorage())

export function useSearchHistory() {
  function addQuery(query: string) {
    const q = query.trim()
    if (!q) return
    // Remove duplicate if exists, then prepend
    history.value = [q, ...history.value.filter(h => h !== q)].slice(0, MAX_ITEMS)
    saveToStorage(history.value)
  }

  function removeQuery(query: string) {
    history.value = history.value.filter(h => h !== query)
    saveToStorage(history.value)
  }

  function clearHistory() {
    history.value = []
    localStorage.removeItem(STORAGE_KEY)
  }

  return { history, addQuery, removeQuery, clearHistory }
}
