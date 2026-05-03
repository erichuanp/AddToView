<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, type FilteredItem } from '../api'
import VideoCard from '../components/VideoCard.vue'
import EmptyState from '../components/EmptyState.vue'
import { useToast } from '../composables/useToast'

const items = ref<FilteredItem[]>([])
const loading = ref(false)
const error = ref('')
const days = ref(30)
const toast = useToast()

async function load() {
  loading.value = true
  error.value = ''
  try {
    const r = await api.filtered(days.value)
    items.value = r.items
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

async function blockUp(it: FilteredItem) {
  if (!it.owner_mid) {
    toast.warn('无法获取 UP 主 UID')
    return
  }
  if (!confirm(`屏蔽 UP 主 "${it.owner_name}"（UID ${it.owner_mid}）？\n之后此 UP 主的所有视频都会被自动过滤。`)) return
  try {
    await api.blacklistCreate('owner_mid', String(it.owner_mid), `从已过滤页面快捷添加：${it.owner_name}`)
    toast.success(`已屏蔽 UP：${it.owner_name}`)
  } catch (e) {
    const msg = (e as Error).message
    if (msg.includes('exists')) {
      toast.info('该 UP 已经在黑名单里')
    } else {
      toast.error(msg)
    }
  }
}

async function blockTitleKeyword(it: FilteredItem) {
  const kw = prompt(`从标题中输入要屏蔽的关键词：`, it.title.slice(0, 8))
  if (!kw || !kw.trim()) return
  try {
    await api.blacklistCreate('title_keyword', kw.trim(), `从已过滤页面快捷添加`)
    toast.success(`已添加关键词："${kw.trim()}"`)
  } catch (e) {
    const msg = (e as Error).message
    if (msg.includes('exists')) {
      toast.info('该关键词已在黑名单里')
    } else {
      toast.error(msg)
    }
  }
}

onMounted(load)
</script>

<template>
  <section>
    <div class="flex flex-wrap items-center gap-3 mb-4">
      <h1 class="text-xl font-semibold">已过滤的视频</h1>
      <span class="text-soft text-sm">最近</span>
      <select v-model="days" @change="load" class="glass-soft px-2 py-1 text-sm">
        <option :value="7">7 天</option>
        <option :value="30">30 天</option>
        <option :value="90">90 天</option>
        <option :value="365">1 年</option>
      </select>
      <button class="btn ml-auto" :disabled="loading" @click="load">{{ loading ? '加载中' : '刷新' }}</button>
    </div>

    <EmptyState v-if="error" tone="err" title="加载失败" :hint="error" />

    <EmptyState
      v-else-if="!loading && items.length === 0"
      title="暂无过滤记录"
      hint="同步动态时命中黑名单规则的视频会出现在这里。"
    />

    <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
      <div v-for="it in items" :key="it.bvid + it.filtered_at" class="flex flex-col">
        <VideoCard
          :bvid="it.bvid"
          :title="it.title"
          :cover="it.cover"
          :duration="it.duration"
          :pubdate="it.pubdate"
          :owner-mid="it.owner_mid"
          :owner-name="it.owner_name"
          :reason="it.reason"
        >
          <template #actions>
            <div class="flex gap-1.5 mt-1.5">
              <button class="btn text-xs flex-1" @click="blockUp(it)">屏蔽 UP</button>
              <button class="btn text-xs flex-1" @click="blockTitleKeyword(it)">屏蔽关键词</button>
            </div>
          </template>
        </VideoCard>
      </div>
    </div>
  </section>
</template>
