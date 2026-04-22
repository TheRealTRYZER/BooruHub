import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export type Theme = 'dark' | 'light' | 'system'

function getSystemTheme(): 'dark' | 'light' {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function applyTheme(theme: Theme) {
  const resolved = theme === 'system' ? getSystemTheme() : theme
  document.documentElement.setAttribute('data-theme', resolved)
}

export const useThemeStore = defineStore('theme', () => {
  const stored = (localStorage.getItem('booruhub_theme') as Theme) || 'dark'
  const theme = ref<Theme>(stored)

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
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    if (theme.value === 'system') applyTheme('system')
  })

  return { theme, toggle, setTheme }
})
