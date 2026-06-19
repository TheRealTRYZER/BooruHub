import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export type Theme = 'dark' | 'light' | 'system'

function getSystemTheme(): 'dark' | 'light' {
  if (typeof window === 'undefined') return 'dark'
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function applyTheme(theme: Theme) {
  if (typeof document === 'undefined') return
  const resolved = theme === 'system' ? getSystemTheme() : theme
  document.documentElement.setAttribute('data-theme', resolved)
}

export const useThemeStore = defineStore('theme', () => {
  const storedRaw = localStorage.getItem('booruhub_theme')
  const validateTheme = (val: string | null): Theme => {
    return val === 'dark' || val === 'light' || val === 'system' ? val : 'dark'
  }
  const theme = ref<Theme>(validateTheme(storedRaw))

  applyTheme(theme.value)

  watch(theme, (val) => {
    localStorage.setItem('booruhub_theme', val)
    applyTheme(val)
  })

  function toggle() {
    if (theme.value === 'dark') theme.value = 'light'
    else if (theme.value === 'light') theme.value = 'system'
    else theme.value = 'dark'
  }

  function setTheme(val: Theme) {
    theme.value = val
  }

  // React to OS-level theme changes when in 'system' mode
  if (typeof window !== 'undefined') {
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
      if (theme.value === 'system') applyTheme('system')
    })
  }

  return { theme, toggle, setTheme }
})
