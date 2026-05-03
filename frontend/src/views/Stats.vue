<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api, type StatsSummary } from '../api'
import EmptyState from '../components/EmptyState.vue'
import { useToast } from '../composables/useToast'

const toast = useToast()
const data = ref<StatsSummary | null>(null)
const loading = ref(false)
const error = ref('')
const days = ref(30)

async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await api.statsSummary(days.value)
  } catch (e) {
    error.value = (e as Error).message
    toast.error(error.value)
  } finally {
    loading.value = false
  }
}

const counters = computed(() => {
  if (!data.value) return [] as { label: string; value: number; tone: string }[]
  const k = data.value.by_kind
  return [
    { label: '收录', value: k.ingested ?? 0, tone: 'sky' },
    { label: '加入稍后再看', value: k.added ?? 0, tone: 'emerald' },
    { label: '已过滤', value: k.filtered ?? 0, tone: 'rose' },
    { label: '错误', value: k.error ?? 0, tone: 'amber' },
  ]
})

const chartMax = computed(() => {
  if (!data.value) return 1
  let m = 0
  for (const d of data.value.daily) {
    m = Math.max(m, d.ingested + d.filtered + d.added)
  }
  return Math.max(1, m)
})

function bar(value: number) {
  return Math.max(0, Math.round((value / chartMax.value) * 100))
}

const visibleDailyDates = computed(() => {
  const list = data.value?.daily ?? []
  const ticks: number[] = []
  const step = Math.max(1, Math.floor(list.length / 6))
  for (let i = 0; i < list.length; i += step) ticks.push(i)
  return new Set(ticks)
})

onMounted(load)
</script>

<template>
  <section class="max-w-6xl mx-auto">
    <div class="flex flex-wrap items-center gap-3 mb-4">
      <h1 class="text-xl font-semibold">统计</h1>
      <select v-model="days" @change="load" class="glass-soft px-2 py-1 text-sm ml-auto">
        <option :value="7">最近 7 天</option>
        <option :value="14">最近 14 天</option>
        <option :value="30">最近 30 天</option>
        <option :value="60">最近 60 天</option>
        <option :value="90">最近 90 天</option>
      </select>
      <button class="btn" :disabled="loading" @click="load">{{ loading ? '加载中' : '刷新' }}</button>
    </div>

    <EmptyState v-if="error" tone="err" title="加载失败" :hint="error" />

    <template v-else-if="data">
      <!-- counter cards -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-5">
        <div v-for="c in counters" :key="c.label" class="glass p-4">
          <div class="text-xs text-soft mb-1">{{ c.label }}</div>
          <div class="text-3xl font-semibold tabular-nums">{{ c.value }}</div>
        </div>
      </div>

      <!-- daily chart -->
      <div class="glass p-4 mb-5">
        <div class="flex items-center justify-between mb-3">
          <h2 class="font-medium">每日动作</h2>
          <div class="flex items-center gap-3 text-xs text-soft">
            <span class="inline-flex items-center"><span class="w-2 h-2 rounded-sm bg-sky-400 mr-1"></span>收录</span>
            <span class="inline-flex items-center"><span class="w-2 h-2 rounded-sm bg-emerald-400 mr-1"></span>加入</span>
            <span class="inline-flex items-center"><span class="w-2 h-2 rounded-sm bg-rose-400 mr-1"></span>过滤</span>
          </div>
        </div>

        <div class="flex items-end gap-[3px] h-40 px-1">
          <div
            v-for="(d, i) in data.daily"
            :key="d.date"
            class="flex-1 flex flex-col-reverse min-w-[2px] group relative"
            :title="`${d.date}\n收录 ${d.ingested}\n加入 ${d.added}\n过滤 ${d.filtered}`"
          >
            <div class="bg-sky-400 rounded-sm" :style="{ height: bar(d.ingested) + '%' }"></div>
            <div class="bg-emerald-400 rounded-sm mb-[1px]" :style="{ height: bar(d.added) + '%' }"></div>
            <div class="bg-rose-400 rounded-sm mb-[1px]" :style="{ height: bar(d.filtered) + '%' }"></div>

            <span v-if="visibleDailyDates.has(i)" class="absolute -bottom-5 left-1/2 -translate-x-1/2 text-[10px] text-soft">{{ d.date.slice(5) }}</span>
          </div>
        </div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <!-- top filtered owners -->
        <div class="glass p-4">
          <h2 class="font-medium mb-3">最常被过滤的 UP 主</h2>
          <ol v-if="data.top_filtered_owners.length > 0" class="flex flex-col gap-1 text-sm">
            <li v-for="(o, i) in data.top_filtered_owners" :key="o.name + i" class="flex justify-between glass-soft px-3 py-1.5">
              <span class="truncate"><span class="text-soft text-xs mr-2">#{{ i + 1 }}</span>{{ o.name }}</span>
              <span class="tabular-nums text-soft">{{ o.count }} 次</span>
            </li>
          </ol>
          <div v-else class="text-soft text-sm">没有数据。</div>
        </div>

        <!-- top active rules -->
        <div class="glass p-4">
          <h2 class="font-medium mb-3">命中最多的规则</h2>
          <ol v-if="data.top_active_rules.length > 0" class="flex flex-col gap-1 text-sm">
            <li v-for="(r, i) in data.top_active_rules" :key="r.id" class="flex justify-between glass-soft px-3 py-1.5">
              <span class="truncate">
                <span class="text-soft text-xs mr-2">#{{ i + 1 }}</span>
                <span class="text-xs text-soft mr-2">{{ r.kind }}</span>
                <code class="font-mono">{{ r.value }}</code>
              </span>
              <span class="tabular-nums text-soft">{{ r.hits }} 次</span>
            </li>
          </ol>
          <div v-else class="text-soft text-sm">还没有规则命中过任何视频。先去同步一次动态吧。</div>
        </div>
      </div>

      <p class="text-soft text-xs mt-4">已知视频总数：{{ data.total_videos_known }}</p>
    </template>
  </section>
</template>
