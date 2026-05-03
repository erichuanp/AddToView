<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, type PredictWatchlater } from '../api'

const data = ref<PredictWatchlater | null>(null)
const loading = ref(false)
const error = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await api.predictWatchlater()
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div v-if="data && data.count > 0" class="glass p-4 mb-4">
    <div class="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
      <div>
        <span class="text-soft text-xs mr-1">剩余总时长</span>
        <strong class="text-lg tabular-nums">{{ data.remaining_total_pretty }}</strong>
      </div>
      <div class="flex items-center gap-3 text-soft">
        <span title="1.0x · 每天 30 分钟">
          1x@30min/d ≈ <strong class="text-current tabular-nums">{{ data.estimates['1x_30min_a_day'].days_at }} 天</strong>
        </span>
        <span title="1.5x · 每天 30 分钟">
          1.5x@30min/d ≈ <strong class="text-current tabular-nums">{{ data.estimates['1.5x_30min_a_day'].days_at }} 天</strong>
        </span>
        <span title="2.0x · 每天 60 分钟">
          2x@60min/d ≈ <strong class="text-current tabular-nums">{{ data.estimates['2x_60min_a_day'].days_at }} 天</strong>
        </span>
      </div>
      <div class="flex-1"></div>
      <div v-if="data.top_owners_by_time.length > 0" class="text-xs text-soft">
        最耗时 UP：
        <span v-for="(o, i) in data.top_owners_by_time.slice(0, 3)" :key="o.name">
          <span v-if="i > 0" class="opacity-50"> · </span>{{ o.name }}<span class="opacity-70">({{ o.pretty }})</span>
        </span>
      </div>
    </div>
  </div>
  <div v-else-if="error" class="text-xs text-rose-500 mb-3">预测失败：{{ error }}</div>
</template>
