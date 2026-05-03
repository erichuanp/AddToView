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
  <div v-if="data && data.count > 0" class="glass px-3 py-1.5 mb-3 flex items-center gap-x-4 text-xs">
    <div class="flex-shrink-0">
      <span class="text-soft mr-1">剩余总时长</span>
      <strong class="tabular-nums text-sm">{{ data.remaining_total_pretty }}</strong>
    </div>
    <!-- show '最耗时 UP' only when there's enough room (lg+); otherwise drop entirely -->
    <div
      v-if="data.top_owners_by_time.length > 0"
      class="hidden lg:block text-soft ml-auto truncate max-w-[60%]"
    >
      最耗时 UP：<span v-for="(o, i) in data.top_owners_by_time.slice(0, 3)" :key="o.name"><span v-if="i > 0" class="opacity-50"> · </span>{{ o.name }}<span class="opacity-70">({{ o.pretty }})</span></span>
    </div>
  </div>
  <div v-else-if="error" class="text-xs mb-2" style="color: rgb(var(--rose))">预测失败：{{ error }}</div>
</template>
