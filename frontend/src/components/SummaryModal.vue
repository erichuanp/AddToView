<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'

const props = defineProps<{ bvid: string; title: string }>()
const emit = defineEmits<{ (e: 'close'): void }>()

const loading = ref(true)
const error = ref('')
const source = ref<'bilibili' | 'doubao' | ''>('')
const text = ref('')
const outline = ref<{ title?: string; timestamp?: number }[]>([])

onMounted(async () => {
  try {
    const r = await api.aiSummary(props.bvid)
    text.value = r.summary
    outline.value = r.outline ?? []
    source.value = r.source
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-50 grid place-items-center p-4 bg-black/30 backdrop-blur-sm" @click.self="emit('close')">
      <div class="glass-strong p-6 max-w-lg w-full">
        <div class="flex items-center gap-2 mb-3">
          <span class="text-base font-semibold flex-1 truncate">{{ title }}</span>
          <button class="btn-ghost text-xs" @click="emit('close')">✕</button>
        </div>

        <div v-if="loading" class="text-sm text-soft">正在分析…</div>
        <div v-else-if="error" class="text-sm text-rose-500">出错：{{ error }}</div>
        <template v-else>
          <p class="text-sm leading-relaxed whitespace-pre-line">{{ text }}</p>
          <ul v-if="outline.length > 0" class="mt-4 flex flex-col gap-1 text-xs text-soft">
            <li v-for="(o, i) in outline" :key="i">
              <span v-if="o.timestamp" class="font-mono mr-2">{{ Math.floor((o.timestamp ?? 0)/60) }}:{{ String((o.timestamp ?? 0)%60).padStart(2,'0') }}</span>
              <span>{{ o.title }}</span>
            </li>
          </ul>
          <p class="text-[10px] text-soft mt-3 text-right">
            来源：<span v-if="source === 'bilibili'">B 站官方</span><span v-else-if="source === 'doubao'">豆包 AI</span>
          </p>
        </template>
      </div>
    </div>
  </Teleport>
</template>
