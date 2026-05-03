import { reactive } from 'vue'

export interface Toast {
  id: number
  text: string
  tone: 'info' | 'success' | 'warn' | 'error'
}

const state = reactive<{ items: Toast[] }>({ items: [] })
let nextId = 1

export function useToast() {
  function push(text: string, tone: Toast['tone'] = 'info', ttl = 4000) {
    const id = nextId++
    state.items.push({ id, text, tone })
    setTimeout(() => {
      const idx = state.items.findIndex((t) => t.id === id)
      if (idx >= 0) state.items.splice(idx, 1)
    }, ttl)
    return id
  }
  function dismiss(id: number) {
    const idx = state.items.findIndex((t) => t.id === id)
    if (idx >= 0) state.items.splice(idx, 1)
  }
  return {
    state,
    push,
    info: (t: string) => push(t, 'info'),
    success: (t: string) => push(t, 'success'),
    warn: (t: string) => push(t, 'warn'),
    error: (t: string) => push(t, 'error', 6000),
    dismiss,
  }
}
