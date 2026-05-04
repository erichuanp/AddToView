<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { api, biliVideoUrl, type ActionLog } from '../api'
import { closeLogsPanel, logsPanelVisible } from '../composables/useLogsPanel'

type LogFilter = 'changes' | 'all' | 'errors'

const items = ref<ActionLog[]>([])
const lastSeenId = ref(0)
const loading = ref(false)
const live = ref(true)
const filter = ref<LogFilter>('changes')
const limit = ref(200)
const errMsg = ref('')

const POLL_MS = 2500
let timer: number | null = null

const KIND_LABEL: Record<ActionLog['kind'], string> = {
  ingested: '入库',
  added: '已添加',
  removed: '已移除',
  filtered: '已过滤',
  viewed: '已观看',
  error: '错误',
}

const KIND_COLOR: Record<ActionLog['kind'], string> = {
  ingested: 'rgb(var(--text-soft))',
  added: 'rgb(var(--emerald))',
  removed: 'rgb(var(--rose))',
  filtered: 'rgb(var(--amber))',
  viewed: 'rgb(var(--text-soft))',
  error: 'rgb(var(--rose))',
}

const filtered = computed(() => {
  if (filter.value === 'all') return items.value
  if (filter.value === 'errors') return items.value.filter((x) => x.kind === 'error')
  // changes: 隐藏 ingested / viewed（只看真正的状态变化）
  return items.value.filter((x) => x.kind !== 'ingested' && x.kind !== 'viewed')
})

const counts = computed(() => {
  const acc: Record<string, number> = { ingested: 0, added: 0, filtered: 0, error: 0, removed: 0 }
  for (const it of items.value) acc[it.kind] = (acc[it.kind] ?? 0) + 1
  return acc
})

async function load() {
  loading.value = true
  errMsg.value = ''
  try {
    const r = await api.actions(limit.value)
    items.value = r.items
    lastSeenId.value = r.items[0]?.id ?? 0
  } catch (e) {
    errMsg.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

function startPolling() {
  if (timer != null) return
  timer = window.setInterval(() => {
    if (!live.value || document.hidden) return
    void load()
  }, POLL_MS)
}

function stopPolling() {
  if (timer != null) {
    window.clearInterval(timer)
    timer = null
  }
}

watch(
  logsPanelVisible,
  (v) => {
    if (v) {
      void load()
      startPolling()
    } else {
      stopPolling()
    }
  },
  { immediate: true },
)

onBeforeUnmount(stopPolling)

function fmtLogTime(iso: string): string {
  const d = new Date(iso)
  const pad = (n: number) => n.toString().padStart(2, '0')
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

// 拖拽：让用户能挪开窗口（万一挡住关心的视频卡片）。pointer 事件，桌面+触屏都行。
const pos = ref({ x: -1, y: -1 }) // -1 表示用默认（右下角）
const dragging = ref(false)
const dragOffset = { x: 0, y: 0 }
function startDrag(e: PointerEvent) {
  // 只在 header 上拖；输入按钮不拦截
  const target = e.target as HTMLElement
  if (target.closest('button, select, a, input')) return
  dragging.value = true
  const rect = (e.currentTarget as HTMLElement).parentElement!.getBoundingClientRect()
  dragOffset.x = e.clientX - rect.left
  dragOffset.y = e.clientY - rect.top
  ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
}
function onDrag(e: PointerEvent) {
  if (!dragging.value) return
  pos.value.x = Math.max(8, Math.min(window.innerWidth - 320, e.clientX - dragOffset.x))
  pos.value.y = Math.max(8, Math.min(window.innerHeight - 80, e.clientY - dragOffset.y))
}
function endDrag(e: PointerEvent) {
  dragging.value = false
  try {
    ;(e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId)
  } catch { /* ignore */ }
}

const panelStyle = computed(() => {
  if (pos.value.x < 0) {
    return { right: '16px', bottom: '16px' } as Record<string, string>
  }
  return { left: `${pos.value.x}px`, top: `${pos.value.y}px` } as Record<string, string>
})
</script>

<template>
  <Transition name="logs">
    <div
      v-if="logsPanelVisible"
      class="logs-panel glass-strong fixed z-40 flex flex-col rounded-xl shadow-lg"
      :style="panelStyle"
      role="dialog"
      aria-label="日志"
    >
      <header
        class="flex items-center gap-2 px-3 py-2 border-b border-[rgb(var(--border))] cursor-move select-none touch-none"
        @pointerdown="startDrag"
        @pointermove="onDrag"
        @pointerup="endDrag"
        @pointercancel="endDrag"
      >
        <span class="text-sm font-medium">日志</span>
        <span class="text-xs text-soft" :title="live ? '每 2.5 秒自动刷新' : '已暂停自动刷新'">
          <span class="dot" :class="live ? 'dot-ok' : 'dot-warn'"></span>
          {{ live ? '实时' : '暂停' }}
        </span>
        <button class="btn-ghost text-xs px-2 py-0.5 ml-auto" @click="live = !live">
          {{ live ? '暂停' : '继续' }}
        </button>
        <button class="btn-ghost text-xs px-2 py-0.5" :disabled="loading" @click="load">
          {{ loading ? '…' : '刷新' }}
        </button>
        <button class="btn-ghost text-base px-2 py-0.5" aria-label="关闭" @click="closeLogsPanel">✕</button>
      </header>

      <div class="flex items-center gap-2 flex-wrap px-3 py-2 border-b border-[rgb(var(--border))]">
        <div class="glass-soft text-xs flex overflow-hidden rounded-full">
          <button
            v-for="opt in (['changes', 'all', 'errors'] as LogFilter[])"
            :key="opt"
            class="px-2.5 py-0.5 transition"
            :class="filter === opt ? 'nav-active font-medium' : 'opacity-70 hover:opacity-100'"
            @click="filter = opt"
          >
            {{ opt === 'changes' ? '动作' : opt === 'all' ? '全部' : '仅错误' }}
          </button>
        </div>
        <select v-model.number="limit" class="glass-soft px-2 py-0.5 text-xs" @change="load">
          <option :value="100">100</option>
          <option :value="200">200</option>
          <option :value="500">500</option>
          <option :value="1000">1000</option>
        </select>
        <span class="text-xs text-soft ml-auto flex flex-wrap gap-x-2 gap-y-0">
          <span :style="{ color: KIND_COLOR.added }">+{{ counts.added ?? 0 }}</span>
          <span :style="{ color: KIND_COLOR.filtered }">⊘{{ counts.filtered ?? 0 }}</span>
          <span :style="{ color: KIND_COLOR.removed }">−{{ counts.removed ?? 0 }}</span>
          <span :style="{ color: KIND_COLOR.error }">!{{ counts.error ?? 0 }}</span>
        </span>
      </div>

      <div class="logs-body font-mono text-xs leading-relaxed p-2 overflow-auto">
        <p v-if="errMsg" class="text-soft px-1 py-1" :style="{ color: 'rgb(var(--rose))' }">{{ errMsg }}</p>
        <p v-else-if="!loading && filtered.length === 0" class="text-soft px-1 py-2">
          没有日志可显示。试试切换到"全部"，或在顶部点一次同步。
        </p>
        <div
          v-for="it in filtered"
          :key="it.id"
          class="flex items-baseline gap-2 px-1 py-0.5 rounded hover:bg-[rgba(127,127,127,0.08)]"
        >
          <span class="text-soft flex-shrink-0">{{ fmtLogTime(it.created_at) }}</span>
          <span
            class="flex-shrink-0 font-semibold"
            :style="{ color: KIND_COLOR[it.kind] }"
          >{{ KIND_LABEL[it.kind] }}</span>
          <a
            :href="biliVideoUrl(it.bvid)"
            target="_blank"
            rel="noopener"
            class="flex-shrink-0 hover:underline"
          >{{ it.bvid }}</a>
          <span v-if="it.owner_name" class="text-soft flex-shrink-0">@{{ it.owner_name }}</span>
          <span class="truncate min-w-0" :title="it.title">{{ it.title }}</span>
          <span v-if="it.reason" class="text-soft truncate min-w-0 ml-auto pl-2" :title="it.reason">{{ it.reason }}</span>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.logs-panel {
  width: min(640px, calc(100vw - 32px));
  max-height: min(60vh, 540px);
}
.logs-body {
  flex: 1;
  min-height: 200px;
}

.logs-enter-active, .logs-leave-active { transition: opacity 160ms ease, transform 160ms ease; }
.logs-enter-from, .logs-leave-to { opacity: 0; transform: translateY(8px); }
</style>
