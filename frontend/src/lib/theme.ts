import { ref } from 'vue'

export type Theme = 'light' | 'dark'

const KEY = 'fd-theme'
const theme = ref<Theme>('light')

export function applyTheme(next: Theme) {
  theme.value = next
  document.documentElement.dataset.theme = next
  document.documentElement.style.colorScheme = next
  try {
    localStorage.setItem(KEY, next)
  } catch {
    /* ignore */
  }
}

export function initTheme() {
  let saved: string | null = null
  try {
    saved = localStorage.getItem(KEY)
  } catch {
    /* ignore */
  }
  applyTheme(saved === 'dark' ? 'dark' : 'light')
}

export function useTheme() {
  return {
    theme,
    toggle() {
      applyTheme(theme.value === 'light' ? 'dark' : 'light')
    },
    set: applyTheme,
  }
}
