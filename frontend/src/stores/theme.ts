import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'

export type Theme = 'dark' | 'light' | 'system'
export type StyleName =
  | 'graphite'
  | 'neon-noir'
  | 'aurora'
  | 'acid'
  | 'signal-orange'
  | 'deep-sea'
  | 'crimson-noir'
  | 'sunset'
  | 'catppuccin'
  | 'rose-pine'
  | 'tokyo-night'
  | 'nord'
  | 'kanagawa'

export type BackgroundKind = 'dots' | 'scan' | 'rings' | 'sparks'

export interface StyleMeta {
  id: StyleName
  name: string
  group: 'base' | 'neon' | 'pastel'
  /** Which animated background the style uses. */
  bg: BackgroundKind
  /** Dark-theme preview colors for the picker: surface, accent, second accent. */
  swatch: [string, string, string]
}

export const STYLE_META: StyleMeta[] = [
  { id: 'graphite', name: 'Graphite', group: 'base', bg: 'dots', swatch: ['#0c0c0c', '#fafafa', '#a3a3a3'] },
  { id: 'neon-noir', name: 'Neon noir', group: 'neon', bg: 'scan', swatch: ['#0d070b', '#ff2e93', '#00e5ff'] },
  { id: 'aurora', name: 'Aurora', group: 'neon', bg: 'rings', swatch: ['#050d0b', '#3dffa8', '#2ea8ff'] },
  { id: 'acid', name: 'Acid', group: 'neon', bg: 'scan', swatch: ['#0b0d05', '#c6ff00', '#ff3d00'] },
  { id: 'signal-orange', name: 'Signal orange', group: 'neon', bg: 'sparks', swatch: ['#0d0a08', '#ff4f00', '#f2ecd8'] },
  { id: 'deep-sea', name: 'Deep sea', group: 'neon', bg: 'dots', swatch: ['#050810', '#2f7bff', '#00f0c8'] },
  { id: 'crimson-noir', name: 'Crimson noir', group: 'neon', bg: 'sparks', swatch: ['#0d0506', '#ff1f3d', '#ffd166'] },
  { id: 'sunset', name: 'Sunset', group: 'neon', bg: 'sparks', swatch: ['#0c0706', '#ff7a59', '#ffd23f'] },
  { id: 'catppuccin', name: 'Catppuccin', group: 'pastel', bg: 'rings', swatch: ['#0b0b10', '#fab387', '#94e2d5'] },
  { id: 'rose-pine', name: 'Rosé Pine', group: 'pastel', bg: 'sparks', swatch: ['#0c0a0b', '#ebbcba', '#f6c177'] },
  { id: 'tokyo-night', name: 'Tokyo Night', group: 'pastel', bg: 'dots', swatch: ['#07080d', '#7aa2f7', '#73daca'] },
  { id: 'nord', name: 'Nord', group: 'pastel', bg: 'dots', swatch: ['#080a0d', '#88c0d0', '#a3be8c'] },
  { id: 'kanagawa', name: 'Kanagawa', group: 'pastel', bg: 'scan', swatch: ['#0a0a0e', '#e6c384', '#7e9cd8'] }
]

export const STYLES: StyleName[] = STYLE_META.map((m) => m.id)

/** 'auto' follows the style's own background; 'off' draws none. */
export type BackgroundChoice = 'auto' | BackgroundKind | 'off'
export const BACKGROUND_CHOICES: BackgroundChoice[] = ['auto', 'dots', 'scan', 'rings', 'sparks', 'off']

function getSystemTheme(): 'dark' | 'light' {
  if (typeof window === 'undefined') return 'dark'
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function applyTheme(theme: Theme) {
  if (typeof document === 'undefined') return
  const resolved = theme === 'system' ? getSystemTheme() : theme
  document.documentElement.setAttribute('data-theme', resolved)
}

function applyStyle(style: StyleName) {
  if (typeof document === 'undefined') return
  document.documentElement.setAttribute('data-style', style)
}

export const useThemeStore = defineStore('theme', () => {
  const storedRaw = localStorage.getItem('booruhub_theme')
  const validateTheme = (val: string | null): Theme => {
    return val === 'dark' || val === 'light' || val === 'system' ? val : 'dark'
  }
  const theme = ref<Theme>(validateTheme(storedRaw))

  const validateStyle = (val: string | null): StyleName => {
    return (STYLES as string[]).includes(val ?? '') ? (val as StyleName) : 'graphite'
  }
  const style = ref<StyleName>(validateStyle(localStorage.getItem('booruhub_style')))

  const validateBackground = (val: string | null): BackgroundChoice => {
    return (BACKGROUND_CHOICES as string[]).includes(val ?? '') ? (val as BackgroundChoice) : 'auto'
  }
  const background = ref<BackgroundChoice>(validateBackground(localStorage.getItem('booruhub_background')))

  // The background actually drawn: the user's pick, or the style's default.
  const backgroundKind = computed<BackgroundKind | 'off'>(() => {
    if (background.value !== 'auto') return background.value
    return STYLE_META.find((m) => m.id === style.value)?.bg ?? 'dots'
  })

  applyTheme(theme.value)
  applyStyle(style.value)

  watch(theme, (val) => {
    localStorage.setItem('booruhub_theme', val)
    applyTheme(val)
  })

  watch(style, (val) => {
    localStorage.setItem('booruhub_style', val)
    applyStyle(val)
  })

  watch(background, (val) => {
    localStorage.setItem('booruhub_background', val)
  })

  function toggle() {
    if (theme.value === 'dark') theme.value = 'light'
    else if (theme.value === 'light') theme.value = 'system'
    else theme.value = 'dark'
  }

  function setTheme(val: Theme) {
    theme.value = val
  }

  function setStyle(val: StyleName) {
    style.value = val
  }

  function setBackground(val: BackgroundChoice) {
    background.value = val
  }

  // React to OS-level theme changes when in 'system' mode
  if (typeof window !== 'undefined') {
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
      if (theme.value === 'system') applyTheme('system')
    })
  }

  return { theme, style, background, backgroundKind, toggle, setTheme, setStyle, setBackground }
})
