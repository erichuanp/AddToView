<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { api, type WatchLaterItem } from '../api'
import VideoListItem from '../components/VideoListItem.vue'
import CoverWall from '../components/CoverWall.vue'
import EmptyState from '../components/EmptyState.vue'
import PredictBanner from '../components/PredictBanner.vue'
import SummaryModal from '../components/SummaryModal.vue'
import { useToast } from '../composables/useToast'
import { useLocalOrder } from '../composables/useLocalOrder'
import { bumpWatchlater, watchlaterChangedAt } from '../composables/useDataEvents'

const items = ref<WatchLaterItem[]>([])
const loading = ref(false)
const error = ref('')
const predictKey = ref(0) // bumped after every list mutation to force PredictBanner remount
const query = ref('')
const sort = ref<'add_at' | 'pubdate' | 'duration' | 'progress' | 'custom'>('add_at')
const localOrder = useLocalOrder()
const dragging = ref<string | null>(null)
const dragOver = ref<string | null>(null)
// filter state per chip:  0 = off · 1 = include only · -1 = exclude (反选)
type TriFilter = 0 | 1 | -1
const filterShort = ref<TriFilter>(0)
const filterLong = ref<TriFilter>(0)
const filterWatched = ref<TriFilter>(0)
const filterMenuOpen = ref(false)

function nextTri(s: TriFilter): TriFilter {
  return (s === 0 ? 1 : s === 1 ? -1 : 0) as TriFilter
}
function chipClass(s: TriFilter) {
  return s === 1 ? 'btn-active' : s === -1 ? 'btn-invert' : ''
}

const activeFilterCount = computed(
  () => [filterShort, filterLong, filterWatched].filter((r) => r.value !== 0).length,
)
const selecting = ref(false)
const selected = ref<Set<string>>(new Set())
const summary = ref<{ bvid: string; title: string } | null>(null)
const viewMode = ref<'list' | 'wall'>(
  (localStorage.getItem('addtoview.watchlater_view') as 'list' | 'wall') || 'list',
)
function setView(m: 'list' | 'wall') {
  viewMode.value = m
  try {
    localStorage.setItem('addtoview.watchlater_view', m)
  } catch {
    /* ignore */
  }
}
const toast = useToast()

const filtered = computed(() => {
  const q = query.value.trim().toLowerCase()
  let arr = items.value.slice()
  if (q) {
    arr = arr.filter((i) => i.title.toLowerCase().includes(q) || i.owner_name.toLowerCase().includes(q))
  }
  // tri-state predicates: 1 = keep matching, -1 = drop matching
  const apply = (state: TriFilter, pred: (i: WatchLaterItem) => boolean) => {
    if (state === 1) arr = arr.filter(pred)
    else if (state === -1) arr = arr.filter((i) => !pred(i))
  }
  // bilibili sets progress < 0 (often -1) once a video is watched to the end
  const isWatched = (i: WatchLaterItem) =>
    i.progress != null && (i.progress < 0 || (i.duration > 0 && i.progress >= i.duration - 5))
  apply(filterWatched.value, isWatched)
  apply(filterShort.value, (i) => i.duration > 0 && i.duration < 300)
  apply(filterLong.value, (i) => i.duration > 900)
  if (sort.value === 'custom') {
    arr.sort((a, b) => localOrder.rank(a.bvid) - localOrder.rank(b.bvid))
  } else {
    arr.sort((a, b) => {
      const k = sort.value
      const av = Number((a as unknown as Record<string, unknown>)[k] ?? 0)
      const bv = Number((b as unknown as Record<string, unknown>)[k] ?? 0)
      return bv - av
    })
  }
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
    localOrder.ensureMembership(r.items.map((i) => i.bvid))
    predictKey.value++
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

function onDragStart(bvid: string, e: DragEvent) {
  dragging.value = bvid
  if (e.dataTransfer) {
    e.dataTransfer.effectAllowed = 'move'
    e.dataTransfer.setData('text/plain', bvid)
  }
}

function onDragOver(bvid: string, e: DragEvent) {
  if (sort.value !== 'custom' || !dragging.value) return
  e.preventDefault()
  if (e.dataTransfer) e.dataTransfer.dropEffect = 'move'
  if (dragOver.value !== bvid) dragOver.value = bvid
}

function onDrop(targetBvid: string) {
  if (!dragging.value || dragging.value === targetBvid) {
    dragging.value = null
    dragOver.value = null
    return
  }
  localOrder.reorder(dragging.value, targetBvid)
  dragging.value = null
  dragOver.value = null
  toast.info('已保存自定义顺序')
}

function onDragEnd() {
  dragging.value = null
  dragOver.value = null
}

async function removeOne(it: WatchLaterItem) {
  if (!it.aid) return
  try {
    await api.watchlaterRemoveByBvid(it.bvid, it.aid)
    items.value = items.value.filter((x) => x.bvid !== it.bvid)
    predictKey.value++
    toast.success(`已移除：${it.title}`)
  } catch (e) {
    toast.error((e as Error).message)
  }
}

async function removeViewed() {
  if (!confirm('移除所有已观看的视频？')) return
  try {
    await api.watchlaterRemoveViewed()
    // B 站后端有几秒传播延迟，立即过滤本地列表给用户即时反馈，
    // 然后再 await load() 让真实状态接管。
    const isWatched = (i: WatchLaterItem) =>
      i.progress != null && (i.progress < 0 || (i.duration > 0 && i.progress >= i.duration - 5))
    items.value = items.value.filter((i) => !isWatched(i))
    predictKey.value++
    toast.success('已移除已观看的视频')
    bumpWatchlater()
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
watch(watchlaterChangedAt, () => load())
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
        <option value="custom">自定义（拖拽）</option>
      </select>
      <div class="glass-soft text-xs flex overflow-hidden rounded-md">
        <button class="px-2.5 py-1 transition" :class="viewMode === 'list' ? 'nav-active' : 'opacity-70 hover:opacity-100'" @click="setView('list')" title="列表视图">列表</button>
        <button class="px-2.5 py-1 transition" :class="viewMode === 'wall' ? 'nav-active' : 'opacity-70 hover:opacity-100'" @click="setView('wall')" title="封面墙">封面</button>
      </div>
      <button class="btn" :disabled="loading" @click="load">{{ loading ? '加载中' : '刷新' }}</button>
    </div>

    <div class="flex flex-wrap items-center gap-2 mb-4">
      <!-- desktop / wide: chips inline. each chip cycles 关 → 仅显示 → 排除（反选） on click;
           red = 反选 = exclude matching items. -->
      <div class="hidden md:flex items-center gap-2">
        <button class="btn text-xs" :class="chipClass(filterWatched)" title="点击循环：关 → 仅显示已看完 → 排除已看完（反选 = 仅未看完）" @click="filterWatched = nextTri(filterWatched)">已看完</button>
        <button class="btn text-xs" :class="chipClass(filterShort)" title="点击循环：关 → 仅显示 → 排除（反选）" @click="filterShort = nextTri(filterShort)">短于 5 分钟</button>
        <button class="btn text-xs" :class="chipClass(filterLong)" title="点击循环：关 → 仅显示 → 排除（反选）" @click="filterLong = nextTri(filterLong)">长于 15 分钟</button>
      </div>

      <!-- narrow / mobile: collapsed dropdown -->
      <div class="md:hidden relative">
        <button
          class="btn text-xs"
          :class="{ 'btn-active': activeFilterCount > 0 || filterMenuOpen }"
          @click="filterMenuOpen = !filterMenuOpen"
        >
          过滤器<span v-if="activeFilterCount > 0" class="ml-1 opacity-80">({{ activeFilterCount }})</span>
        </button>
        <Teleport to="body">
          <div
            v-if="filterMenuOpen"
            class="fixed inset-0 z-30"
            @click="filterMenuOpen = false"
          ></div>
        </Teleport>
        <div
          v-if="filterMenuOpen"
          class="absolute left-0 top-full mt-1 z-40 glass-strong p-2 flex flex-col gap-1 min-w-[10rem]"
        >
          <button class="btn text-xs justify-start" :class="chipClass(filterWatched)" @click="filterWatched = nextTri(filterWatched)">已看完</button>
          <button class="btn text-xs justify-start" :class="chipClass(filterShort)" @click="filterShort = nextTri(filterShort)">短于 5 分钟</button>
          <button class="btn text-xs justify-start" :class="chipClass(filterLong)" @click="filterLong = nextTri(filterLong)">长于 15 分钟</button>
        </div>
      </div>

      <span class="flex-1"></span>
      <button v-if="!selecting" class="btn text-xs" @click="selecting = true">批量选择</button>
      <template v-else>
        <span class="text-xs text-soft">{{ selected.size }} 个已选</span>
        <button class="btn-danger text-xs" @click="bulkRemove" :disabled="selected.size === 0">移除选中</button>
        <button class="btn-ghost text-xs" @click="clearSelection">退出选择</button>
      </template>
      <button class="btn-danger text-xs" @click="removeViewed">移除已观看</button>
    </div>

    <PredictBanner v-if="!error && items.length > 0" :key="predictKey" />

    <EmptyState v-if="error" tone="err" title="加载失败" :hint="error">
      <button class="btn-primary mt-3" @click="load">重试</button>
    </EmptyState>

    <EmptyState v-else-if="!loading && items.length === 0" title="稍后再看是空的" hint="点击右上角的“同步 N 天”开始拉取关注的 UP 主新视频。" />

    <p v-if="sort === 'custom' && viewMode === 'list'" class="text-xs text-soft mb-2">提示：拖拽行到目标位置即可重新排序，顺序会保存在本浏览器。</p>

    <CoverWall v-if="!error && items.length > 0 && viewMode === 'wall'" :items="filtered" />

    <div v-else-if="!error && items.length > 0" class="flex flex-col gap-2">
      <div
        v-for="it in filtered"
        :key="it.bvid"
        class="relative flex items-stretch gap-2 min-w-0 transition"
        :class="{
          'opacity-40': dragging === it.bvid,
          'ring-2 ring-offset-2 ring-offset-transparent rounded-xl': dragOver === it.bvid && dragging !== it.bvid,
        }"
        :style="dragOver === it.bvid && dragging !== it.bvid ? { '--tw-ring-color': 'rgb(var(--accent))' } : {}"
        :draggable="sort === 'custom' && !selecting"
        @dragstart="onDragStart(it.bvid, $event)"
        @dragover="onDragOver(it.bvid, $event)"
        @dragleave="dragOver === it.bvid ? (dragOver = null) : null"
        @drop.prevent="onDrop(it.bvid)"
        @dragend="onDragEnd"
      >
        <input
          v-if="selecting"
          type="checkbox"
          class="self-center w-5 h-5 rounded flex-shrink-0"
          style="accent-color: rgb(var(--accent))"
          :checked="selected.has(it.bvid)"
          @change="toggleSelected(it.bvid)"
        />
        <span
          v-if="sort === 'custom' && !selecting"
          class="self-center cursor-grab active:cursor-grabbing select-none text-soft text-base px-1"
          title="按住拖拽"
        >⋮⋮</span>
        <VideoListItem
          class="flex-1"
          :bvid="it.bvid"
          :title="it.title"
          :cover="it.cover"
          :duration="it.duration"
          :pubdate="it.pubdate"
          :desc="it.desc"
          :owner-mid="it.owner_mid"
          :owner-name="it.owner_name"
          :progress="it.progress"
          :stat-play="it.stat_play"
          :stat-like="it.stat_like"
          :stat-coin="it.stat_coin"
          :stat-favorite="it.stat_favorite"
          :stat-share="it.stat_share"
          removable
          ai-summary
          @remove="removeOne(it)"
          @summarize="summary = { bvid: it.bvid, title: it.title }"
        />
      </div>
    </div>

    <SummaryModal
      v-if="summary"
      :bvid="summary.bvid"
      :title="summary.title"
      @close="summary = null"
    />
  </section>
</template>
