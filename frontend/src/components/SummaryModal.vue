<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
import { bumpSummary } from '../composables/useDataEvents'

const props = defineProps<{ bvid: string; title: string }>()
const emit = defineEmits<{ (e: 'close'): void }>()

const loading = ref(true)
const error = ref('')
const text = ref('')
const outline = ref<{ title?: string; timestamp?: number }[]>([])

// 深度摘要状态：deepDone=true 表示这次开 modal 期间已经跑过一次深度总结
const deepLoading = ref(false)
const deepDone = ref(false)
const deepError = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    const r = await api.aiSummary(props.bvid, false)
    text.value = r.summary
    outline.value = r.outline ?? []
    if (r.source === 'deep') deepDone.value = true
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

async function runDeep() {
  if (deepLoading.value) return
  deepLoading.value = true
  deepError.value = ''
  try {
    const r = await api.aiSummaryDeep(props.bvid)
    text.value = r.summary
    outline.value = r.outline ?? []
    deepDone.value = true
    // 通知卡片同步更新内联摘要
    bumpSummary(props.bvid, r.summary)
  } catch (e) {
    deepError.value = (e as Error).message
  } finally {
    deepLoading.value = false
  }
}

onMounted(load)
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-50 grid place-items-center p-3 sm:p-4 bg-black/30 backdrop-blur-sm" @click.self="emit('close')">
      <div class="glass-strong p-4 sm:p-6 max-w-lg w-full max-h-[85vh] overflow-y-auto">
        <div class="flex items-center gap-2 mb-3">
          <span class="text-base font-semibold flex-1 truncate">{{ title }}</span>
          <button class="btn-ghost text-xs" @click="emit('close')">✕</button>
        </div>

        <div v-if="loading" class="text-sm text-soft">正在加载…</div>
        <div v-else-if="error" class="text-sm" style="color: rgb(var(--rose))">出错：{{ error }}</div>
        <template v-else>
          <p class="text-sm leading-relaxed whitespace-pre-line">{{ text }}</p>
          <ul v-if="outline.length > 0" class="mt-4 flex flex-col gap-1 text-xs text-soft">
            <li v-for="(o, i) in outline" :key="i">
              <span v-if="o.timestamp" class="font-mono mr-2">{{ Math.floor((o.timestamp ?? 0)/60) }}:{{ String((o.timestamp ?? 0)%60).padStart(2,'0') }}</span>
              <span>{{ o.title }}</span>
            </li>
          </ul>

          <div class="mt-5 pt-4 border-t border-[rgb(var(--border))]">
            <button
              type="button"
              class="w-full px-4 py-2 rounded-md text-sm font-medium transition disabled:opacity-60 disabled:cursor-not-allowed"
              :class="deepDone ? 'bg-[rgb(var(--accent))] text-white hover:opacity-90' : 'bg-[rgb(var(--accent))] text-white hover:opacity-90'"
              :disabled="deepLoading"
              @click="runDeep"
            >
              <span v-if="deepLoading">深度总结中…（拉字幕 + 模型思考，请稍候）</span>
              <span v-else-if="deepDone">再次总结</span>
              <span v-else>深度总结</span>
            </button>
            <p class="text-xs text-soft mt-2 text-center">
              即将拉取视频字幕进行总结，可能要花几分钟的时间
            </p>
            <p v-if="deepError" class="text-xs mt-2 text-center" style="color: rgb(var(--rose))">{{ deepError }}</p>
          </div>
        </template>
      </div>
    </div>
  </Teleport>
</template>
