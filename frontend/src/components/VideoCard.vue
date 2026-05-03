<script setup lang="ts">
import { computed } from 'vue'
import { biliSpaceUrl, biliVideoUrl, fmtDuration, fmtRelativeTime } from '../api'

interface Props {
  bvid: string
  title: string
  cover: string
  duration: number
  pubdate?: number
  ownerMid?: number | null
  ownerName?: string
  partitionName?: string
  reason?: string
  progress?: number  // 0..duration; -1 means watched
  removable?: boolean
}
const props = withDefaults(defineProps<Props>(), { removable: false })
const emit = defineEmits<{ (e: 'remove'): void }>()

// Bilibili covers are http but pages may be https — proxy with @ to keep them loading
const coverSrc = computed(() => {
  if (!props.cover) return ''
  return props.cover.startsWith('http') ? props.cover.replace(/^http:/, 'https:') : props.cover
})

const progressPct = computed(() => {
  if (!props.duration || props.progress == null) return 0
  if (props.progress < 0) return 100
  return Math.min(100, Math.round((props.progress / props.duration) * 100))
})
</script>

<template>
  <article class="glass overflow-hidden flex flex-col group transition hover:-translate-y-0.5 hover:shadow-xl">
    <a :href="biliVideoUrl(bvid)" target="_blank" rel="noopener" class="relative block aspect-video bg-black/10">
      <img v-if="coverSrc" :src="coverSrc" :alt="title" loading="lazy" referrerpolicy="no-referrer" class="w-full h-full object-cover" />
      <span class="absolute right-2 bottom-2 text-[11px] px-1.5 py-0.5 rounded bg-black/65 text-white font-mono">
        {{ fmtDuration(duration) }}
      </span>
      <span v-if="progress != null && progress > 0" class="absolute left-0 right-0 bottom-0 h-1 bg-black/30">
        <span class="block h-full bg-[#fb7299]" :style="{ width: progressPct + '%' }"></span>
      </span>
    </a>
    <div class="p-3 flex flex-col gap-1.5 flex-1">
      <a :href="biliVideoUrl(bvid)" target="_blank" rel="noopener" class="font-medium text-sm leading-snug line-clamp-2 hover:underline">
        {{ title }}
      </a>
      <div class="flex items-center justify-between text-xs text-soft">
        <a v-if="ownerName" :href="biliSpaceUrl(ownerMid ?? null)" target="_blank" rel="noopener" class="hover:underline truncate max-w-[60%]">
          {{ ownerName }}
        </a>
        <span v-if="pubdate">{{ fmtRelativeTime(pubdate) }}</span>
      </div>
      <div v-if="partitionName || reason" class="flex flex-wrap gap-1.5 text-[10px]">
        <span v-if="partitionName" class="px-1.5 py-0.5 rounded glass-soft">{{ partitionName }}</span>
        <span v-if="reason" class="px-1.5 py-0.5 rounded bg-rose-500/15 text-rose-700 dark:text-rose-300">{{ reason }}</span>
      </div>
      <slot name="actions">
        <button v-if="props.removable" class="btn mt-1.5" @click="emit('remove')">移除</button>
      </slot>
    </div>
  </article>
</template>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
