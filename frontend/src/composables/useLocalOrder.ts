import { ref, watch } from 'vue'

const STORAGE_KEY = 'addtoview.watchlater_order'

function read(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed.filter((x) => typeof x === 'string') : []
  } catch {
    return []
  }
}

const order = ref<string[]>(read())

watch(order, (next) => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
  } catch {
    /* localStorage full / unavailable */
  }
}, { deep: true })

export function useLocalOrder() {
  function reorder(bvid: string, beforeBvid: string | null) {
    const without = order.value.filter((x) => x !== bvid)
    if (beforeBvid === null) {
      without.push(bvid)
    } else {
      const idx = without.indexOf(beforeBvid)
      if (idx === -1) without.push(bvid)
      else without.splice(idx, 0, bvid)
    }
    order.value = without
  }

  function rank(bvid: string): number {
    const i = order.value.indexOf(bvid)
    return i === -1 ? Number.MAX_SAFE_INTEGER : i
  }

  function ensureMembership(bvids: string[]) {
    // append any new bvids not yet in the order list (preserving their relative position)
    const known = new Set(order.value)
    const extras = bvids.filter((b) => !known.has(b))
    if (extras.length > 0) {
      order.value = [...order.value, ...extras]
    }
  }

  function clear() {
    order.value = []
  }

  return { order, reorder, rank, ensureMembership, clear }
}
