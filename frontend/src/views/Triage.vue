<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api, type WatchLaterItem } from '../api'
import VideoListItem from '../components/VideoListItem.vue'
import EmptyState from '../components/EmptyState.vue'
import { useToast } from '../composables/useToast'

const items = ref<WatchLaterItem[]>([])
const buckets = ref<{ must_watch: string[]; maybe: string[]; skip: string[] }>({
  must_watch: [],
  maybe: [],
  skip: [],
})
const loading = ref(false)
const error = ref('')
const toast = useToast()

async function loadList() {
  try {
    const r = await api.watchlater()
    items.value = r.items
  } catch (e) {
    error.value = (e as Error).message
  }
}

async function runTriage() {
  loading.value = true
  error.value = ''
  try {
    const r = await api.aiTriage()
    if (r.error) {
      error.value = r.error
      toast.error(r.error)
      return
    }
    buckets.value = {
      must_watch: r.buckets?.must_watch ?? [],
      maybe: r.buckets?.maybe ?? [],
      skip: r.buckets?.skip ?? [],
    }
    toast.success(
      `推荐 ${buckets.value.must_watch.length} · 待看 ${buckets.value.maybe.length} · 跳过 ${buckets.value.skip.length}`,
    )
  } catch (e) {
    error.value = (e as Error).message
    toast.error(error.value)
  } finally {
    loading.value = false
  }
}

const byBvid = computed(() => new Map(items.value.map((i) => [i.bvid, i])))

function group(bvids: string[]): WatchLaterItem[] {
  return bvids.map((b) => byBvid.value.get(b)).filter(Boolean) as WatchLaterItem[]
}

async function bulkRemove(bvids: string[]) {
  if (bvids.length === 0) return
  if (!confirm(`从稍后再看移除 ${bvids.length} 个视频？`)) return
  let ok = 0
  let bad = 0
  for (const b of bvids) {
    const v = byBvid.value.get(b)
    if (!v?.aid) continue
    try {
      await api.watchlaterRemoveByBvid(v.bvid, v.aid)
      ok++
    } catch {
      bad++
    }
  }
  toast.success(`已移除 ${ok} 个${bad ? `（${bad} 失败）` : ''}`)
  buckets.value.skip = []
  await loadList()
}

onMounted(loadList)
</script>

<template>
  <section>
    <div class="flex flex-wrap items-center gap-3 mb-4">
      <h1 class="text-xl font-semibold">AI 智选</h1>
      <span class="text-soft text-sm">让 AI 把你的稍后再看分桶，你来决定</span>
      <button class="btn-primary ml-auto" :disabled="loading" @click="runTriage">
        {{ loading ? '思考中…' : '运行 AI 智选' }}
      </button>
    </div>

    <EmptyState v-if="error" tone="err" title="出错" :hint="error" />

    <template v-else>
      <section class="mb-6">
        <h2 class="font-medium mb-2">
          强烈推荐 <span class="text-soft text-sm">{{ buckets.must_watch.length }}</span>
        </h2>
        <div v-if="group(buckets.must_watch).length === 0" class="text-soft text-sm">空</div>
        <div v-else class="flex flex-col gap-2">
          <VideoListItem
            v-for="it in group(buckets.must_watch)"
            :key="it.bvid"
            :bvid="it.bvid"
            :title="it.title"
            :cover="it.cover"
            :duration="it.duration"
            :pubdate="it.pubdate"
            :desc="it.desc"
            :owner-mid="it.owner_mid"
            :owner-name="it.owner_name"
            :stat-play="it.stat_play"
            :stat-like="it.stat_like"
            :stat-coin="it.stat_coin"
            :stat-favorite="it.stat_favorite"
            :stat-share="it.stat_share"
          />
        </div>
      </section>

      <section class="mb-6">
        <h2 class="font-medium mb-2">看心情 <span class="text-soft text-sm">{{ buckets.maybe.length }}</span></h2>
        <div v-if="group(buckets.maybe).length === 0" class="text-soft text-sm">空</div>
        <div v-else class="flex flex-col gap-2">
          <VideoListItem
            v-for="it in group(buckets.maybe)"
            :key="it.bvid"
            :bvid="it.bvid"
            :title="it.title"
            :cover="it.cover"
            :duration="it.duration"
            :pubdate="it.pubdate"
            :desc="it.desc"
            :owner-mid="it.owner_mid"
            :owner-name="it.owner_name"
            :stat-play="it.stat_play"
            :stat-like="it.stat_like"
            :stat-coin="it.stat_coin"
            :stat-favorite="it.stat_favorite"
            :stat-share="it.stat_share"
          />
        </div>
      </section>

      <section class="mb-6">
        <div class="flex items-center justify-between mb-2">
          <h2 class="font-medium">建议跳过 <span class="text-soft text-sm">{{ buckets.skip.length }}</span></h2>
          <button v-if="buckets.skip.length > 0" class="btn text-xs" @click="bulkRemove(buckets.skip)">
            一键移除全部
          </button>
        </div>
        <div v-if="group(buckets.skip).length === 0" class="text-soft text-sm">空</div>
        <div v-else class="flex flex-col gap-2">
          <VideoListItem
            v-for="it in group(buckets.skip)"
            :key="it.bvid"
            :bvid="it.bvid"
            :title="it.title"
            :cover="it.cover"
            :duration="it.duration"
            :pubdate="it.pubdate"
            :desc="it.desc"
            :owner-mid="it.owner_mid"
            :owner-name="it.owner_name"
            :stat-play="it.stat_play"
            :stat-like="it.stat_like"
            :stat-coin="it.stat_coin"
            :stat-favorite="it.stat_favorite"
            :stat-share="it.stat_share"
          />
        </div>
      </section>
    </template>
  </section>
</template>
