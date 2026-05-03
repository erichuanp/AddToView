import { ref } from 'vue'

/** Module-level reactive "now" — ticks every 30 seconds so anything that
 * derives from it (relative-time labels) re-renders without per-component
 * timers. Idle browsers still throw setInterval; that's acceptable cost.
 */
const now = ref(Date.now())

if (typeof window !== 'undefined') {
  setInterval(() => {
    now.value = Date.now()
  }, 30_000)
  // also tick when the tab regains focus, so a long-suspended tab refreshes
  // immediately instead of waiting up to 30s
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) now.value = Date.now()
  })
}

export function useNow() {
  return now
}
