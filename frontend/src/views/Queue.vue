<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { api, type FilteredItem, type VideoLite } from '../api'
import VideoListItem from '../components/VideoListItem.vue'
import EmptyState from '../components/EmptyState.vue'
import { useToast } from '../composables/useToast'
import { pendingChangedAt } from '../composables/useDataEvents'

type Tab = 'pending' | 'filtered'

const tab = ref<Tab>('pending')
const days = ref(30)
const loading = ref(false)
const error = ref('')
const pendingItems = ref<VideoLite[]>([])
const filteredItems = ref<FilteredItem[]>([])
const toast = useToast()

const counts = computed(() => ({
  pending: pendingItems.value.length,
  filtered: filteredItems.value.length,
}))

async function load() {
  loading.value = true
  error.value = ''
  try {
    // load both tabs in parallel so the inactive tab's count is accurate
    const [p, f] = await Promise.all([
      api.pending(days.value),
      api.filtered(days.value),
    ])
    pendingItems.value = p.items
    filteredItems.value = f.items
  } catch (e) {
    error.value = (e as Error).message
    toast.error(error.value)
  } finally {
    loading.value = false
  }
}

// only re-fetch when the time window changes (tab toggle is purely visual now)
watch(days, load)
watch(pendingChangedAt, () => load())
onMounted(load)

async function pendingAdd(it: VideoLite) {
  try {
    const res = await api.watchlaterAdd(it.bvid)
    if (res.code === 0 || res.code === 90002 || res.code === 90005) {
      toast.success(`已添加：${it.title}`)
      pendingItems.value = pendingItems.value.filter((x) => x.bvid !== it.bvid)
    } else {
      toast.error(`添加失败 (code ${res.code}) ${res.message ?? ''}`)
    }
  } catch (e) {
    toast.error((e as Error).message)
  }
}

async function pendingSkip(it: VideoLite) {
  try {
    await api.pendingSkip(it.bvid)
    toast.success(`已移除：${it.title}`)
    pendingItems.value = pendingItems.value.filter((x) => x.bvid !== it.bvid)
  } catch (e) {
    toast.error((e as Error).message)
  }
}
</script>

<template>
  <section>
    <div class="flex flex-wrap items-center gap-3 mb-4">
      <h1 class="text-xl font-semibold">待选视频</h1>

      <div class="glass-soft text-sm flex overflow-hidden rounded-full">
        <button
          class="px-3 py-1 transition"
          :class="tab === 'pending' ? 'nav-active font-medium' : 'opacity-70 hover:opacity-100'"
          @click="tab = 'pending'"
        >
          待添加 <span class="text-xs text-soft">{{ counts.pending }}</span>
        </button>
        <button
          class="px-3 py-1 transition"
          :class="tab === 'filtered' ? 'nav-active font-medium' : 'opacity-70 hover:opacity-100'"
          @click="tab = 'filtered'"
        >
          已过滤 <span class="text-xs text-soft">{{ counts.filtered }}</span>
        </button>
      </div>

      <span class="text-soft text-sm ml-2">最近</span>
      <select v-model="days" class="glass-soft px-2 py-1 text-sm">
        <option :value="7">7 天</option>
        <option :value="30">30 天</option>
        <option :value="90">90 天</option>
        <option :value="365">1 年</option>
      </select>
      <button class="btn ml-auto" :disabled="loading" @click="load">{{ loading ? '加载中' : '刷新' }}</button>
    </div>

    <p v-if="tab === 'pending'" class="text-soft text-xs mb-3">
      已同步入库但还没被加进稍后再看的视频。点右上角的 <strong>一键添加</strong> 会再同步一次然后把这里的视频推入稍后再看。
    </p>
    <p v-else class="text-soft text-xs mb-3">
      被黑名单规则命中的视频。在 <RouterLink to="/blacklist" class="underline hover:text-current">黑名单</RouterLink> 调整规则后，下次同步生效。
    </p>

    <EmptyState v-if="error" tone="err" title="加载失败" :hint="error" />

    <template v-else-if="tab === 'pending'">
      <EmptyState
        v-if="!loading && pendingItems.length === 0"
        title="待添加列表是空的"
        hint="点击右上角的“同步”或“一键添加”抓取关注 UP 主的新视频。"
      />
      <div v-else class="flex flex-col gap-2">
        <VideoListItem
          v-for="it in pendingItems"
          :key="it.bvid"
          :bvid="it.bvid"
          :title="it.title"
          :cover="it.cover"
          :duration="it.duration"
          :pubdate="it.pubdate"
          :desc="it.desc"
          :owner-mid="it.owner_mid"
          :owner-name="it.owner_name"
          addable
          removable
          @add="pendingAdd(it)"
          @remove="pendingSkip(it)"
        />
      </div>
    </template>

    <template v-else>
      <EmptyState
        v-if="!loading && filteredItems.length === 0"
        title="暂无过滤记录"
        hint="同步动态时命中黑名单规则的视频会出现在这里。"
      />
      <div v-else class="flex flex-col gap-2">
        <VideoListItem
          v-for="it in filteredItems"
          :key="it.bvid + it.filtered_at"
          :bvid="it.bvid"
          :title="it.title"
          :cover="it.cover"
          :duration="it.duration"
          :pubdate="it.pubdate"
          :desc="it.desc"
          :owner-mid="it.owner_mid"
          :owner-name="it.owner_name"
          :reason="it.reason"
        />
      </div>
    </template>
  </section>
</template>
