<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api, type WatchLaterItem } from '../api'
import VideoCard from '../components/VideoCard.vue'
import EmptyState from '../components/EmptyState.vue'
import { useToast } from '../composables/useToast'

const items = ref<WatchLaterItem[]>([])
const loading = ref(false)
const error = ref('')
const query = ref('')
const sort = ref<'add_at' | 'pubdate' | 'duration' | 'progress'>('add_at')
const filterUnseen = ref(false)
const filterShort = ref(false)
const selecting = ref(false)
const selected = ref<Set<string>>(new Set())
const toast = useToast()

const filtered = computed(() => {
  const q = query.value.trim().toLowerCase()
  let arr = items.value.slice()
  if (q) {
    arr = arr.filter((i) => i.title.toLowerCase().includes(q) || i.owner_name.toLowerCase().includes(q))
  }
  if (filterUnseen.value) {
    arr = arr.filter((i) => !i.progress || i.progress === 0)
  }
  if (filterShort.value) {
    arr = arr.filter((i) => i.duration > 0 && i.duration < 300)
  }
  arr.sort((a, b) => {
    const k = sort.value
    const av = Number((a as unknown as Record<string, unknown>)[k] ?? 0)
    const bv = Number((b as unknown as Record<string, unknown>)[k] ?? 0)
    return bv - av
  })
  return arr
})

const totalDuration = computed(() => filtered.value.reduce((acc, i) => acc + (i.duration || 0), 0))

function fmtTotalDuration(secs: number): string {
  if (secs < 60) return `${secs}秒`
  const m = Math.floor(secs / 60)
  if (m < 60) return `${m}分钟`
  const h = Math.floor(m / 60)
  const mr = m % 60
  return `${h}小时${mr}分钟`
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const r = await api.watchlater()
    items.value = r.items
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

async function removeOne(it: WatchLaterItem) {
  if (!it.aid) return
  try {
    await api.watchlaterRemoveByBvid(it.bvid, it.aid)
    items.value = items.value.filter((x) => x.bvid !== it.bvid)
    toast.success(`已移除：${it.title}`)
  } catch (e) {
    toast.error((e as Error).message)
  }
}

async function removeViewed() {
  if (!confirm('移除所有已观看的视频？')) return
  try {
    await api.watchlaterRemoveViewed()
    toast.success('已移除已观看的视频')
    await load()
  } catch (e) {
    toast.error((e as Error).message)
  }
}

function toggleSelected(bvid: string) {
  if (selected.value.has(bvid)) selected.value.delete(bvid)
  else selected.value.add(bvid)
  // shallow-set to trigger reactivity
  selected.value = new Set(selected.value)
}

function clearSelection() {
  selected.value = new Set()
  selecting.value = false
}

async function bulkRemove() {
  if (selected.value.size === 0) return
  if (!confirm(`移除选中的 ${selected.value.size} 个视频？`)) return
  const targets = items.value.filter((i) => selected.value.has(i.bvid) && i.aid)
  let ok = 0
  let bad = 0
  for (const t of targets) {
    try {
      await api.watchlaterRemoveByBvid(t.bvid, t.aid as number)
      ok++
    } catch {
      bad++
    }
  }
  toast.success(`已移除 ${ok} 个${bad ? `（${bad} 个失败）` : ''}`)
  clearSelection()
  await load()
}

onMounted(load)
</script>

<template>
  <section>
    <div class="flex flex-wrap items-center gap-2 mb-3">
      <h1 class="text-xl font-semibold mr-2">稍后再看</h1>
      <span class="text-soft text-sm">{{ items.length }} 个视频 · 总时长 {{ fmtTotalDuration(totalDuration) }}</span>

      <div class="flex-1"></div>

      <input
        v-model="query"
        placeholder="搜索…"
        class="glass-soft px-3 py-1.5 text-sm outline-none w-44"
      />
      <select v-model="sort" class="glass-soft px-2 py-1.5 text-sm">
        <option value="add_at">添加时间</option>
        <option value="pubdate">发布时间</option>
        <option value="duration">时长</option>
        <option value="progress">观看进度</option>
      </select>
      <button class="btn" :disabled="loading" @click="load">{{ loading ? '加载中' : '刷新' }}</button>
    </div>

    <div class="flex flex-wrap items-center gap-2 mb-4">
      <button class="btn text-xs" :class="{ '!bg-emerald-400/30': filterUnseen }" @click="filterUnseen = !filterUnseen">未看过</button>
      <button class="btn text-xs" :class="{ '!bg-emerald-400/30': filterShort }" @click="filterShort = !filterShort">短于 5 分钟</button>
      <span class="flex-1"></span>
      <button v-if="!selecting" class="btn text-xs" @click="selecting = true">批量选择</button>
      <template v-else>
        <span class="text-xs text-soft">{{ selected.size }} 个已选</span>
        <button class="btn text-xs" @click="bulkRemove" :disabled="selected.size === 0">移除选中</button>
        <button class="btn-ghost text-xs" @click="clearSelection">退出选择</button>
      </template>
      <button class="btn text-xs" @click="removeViewed">移除已观看</button>
    </div>

    <EmptyState v-if="error" tone="err" title="加载失败" :hint="error">
      <button class="btn-primary mt-3" @click="load">重试</button>
    </EmptyState>

    <EmptyState v-else-if="!loading && items.length === 0" title="稍后再看是空的" hint="点击右上角的“同步 N 天”开始拉取关注的 UP 主新视频。" />

    <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
      <div
        v-for="it in filtered"
        :key="it.bvid"
        class="relative"
      >
        <input
          v-if="selecting"
          type="checkbox"
          class="absolute left-2 top-2 z-10 w-5 h-5 rounded accent-pink-500"
          :checked="selected.has(it.bvid)"
          @change="toggleSelected(it.bvid)"
        />
        <VideoCard
          :bvid="it.bvid"
          :title="it.title"
          :cover="it.cover"
          :duration="it.duration"
          :pubdate="it.pubdate"
          :owner-mid="it.owner_mid"
          :owner-name="it.owner_name"
          :progress="it.progress"
          removable
          @remove="removeOne(it)"
        />
      </div>
    </div>
  </section>
</template>
