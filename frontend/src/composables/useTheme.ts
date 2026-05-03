import { ref, watch } from 'vue'

export type ThemeChoice = 'light' | 'dark' | 'auto'

const STORAGE_KEY = 'addtoview.theme'

function readChoice(): ThemeChoice {
  const v = (typeof localStorage !== 'undefined' && localStorage.getItem(STORAGE_KEY)) || 'auto'
  return v === 'light' || v === 'dark' || v === 'auto' ? v : 'auto'
}

const choice = ref<ThemeChoice>(readChoice())
const systemDark = ref(false)
let mediaQuery: MediaQueryList | null = null

function effective(): 'light' | 'dark' {
  if (choice.value === 'auto') return systemDark.value ? 'dark' : 'light'
  return choice.value
}

function apply() {
  if (typeof document === 'undefined') return
  document.documentElement.classList.toggle('dark', effective() === 'dark')
}

if (typeof window !== 'undefined') {
  mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
  systemDark.value = mediaQuery.matches
  mediaQuery.addEventListener('change', (e) => {
    systemDark.value = e.matches
    apply()
  })
  // apply on first import so the initial paint matches
  apply()
}

watch(choice, () => {
  try {
    localStorage.setItem(STORAGE_KEY, choice.value)
  } catch {
    /* localStorage may be disabled */
  }
  apply()
})

export function useTheme() {
  return {
    choice,
    systemDark,
    effective,
    setChoice(next: ThemeChoice) {
      choice.value = next
    },
  }
}
