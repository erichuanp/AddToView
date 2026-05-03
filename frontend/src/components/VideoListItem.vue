<script setup lang="ts">
import { computed } from 'vue'
import { biliSpaceUrl, biliVideoUrl, fmtCount, fmtDuration, fmtRelativeTime } from '../api'

interface Props {
  bvid: string
  title: string
  cover: string
  duration: number
  pubdate?: number
  desc?: string
  ownerMid?: number | null
  ownerName?: string
  progress?: number
  statPlay?: number
  statLike?: number
  statCoin?: number
  statFavorite?: number
  statShare?: number
  removable?: boolean
  aiSummary?: boolean
  reason?: string
}
const props = withDefaults(defineProps<Props>(), { removable: false, aiSummary: false })
const emit = defineEmits<{ (e: 'remove'): void; (e: 'summarize'): void }>()

const coverSrc = computed(() => {
  if (!props.cover) return ''
  return props.cover.startsWith('http') ? props.cover.replace(/^http:/, 'https:') : props.cover
})

const progressPct = computed(() => {
  if (!props.duration || props.progress == null) return 0
  if (props.progress < 0) return 100
  return Math.min(100, Math.round((props.progress / props.duration) * 100))
})

// strip newlines from desc so the truncate works as expected
const descOneLine = computed(() => (props.desc || '').replace(/\s+/g, ' ').trim())

// hide the stats row entirely when all stats are zero (e.g. on the Filtered page)
const hasStats = computed(
  () =>
    (props.statPlay ?? 0) > 0 ||
    (props.statLike ?? 0) > 0 ||
    (props.statCoin ?? 0) > 0 ||
    (props.statFavorite ?? 0) > 0 ||
    (props.statShare ?? 0) > 0,
)
</script>

<template>
  <article class="glass flex items-stretch gap-3 p-2.5 group transition hover:shadow-lg min-w-0 overflow-hidden relative">
    <a
      :href="biliVideoUrl(bvid)"
      target="_blank"
      rel="noopener"
      class="relative flex-shrink-0 w-44 aspect-video rounded-lg overflow-hidden bg-black/10 block"
    >
      <img
        v-if="coverSrc"
        :src="coverSrc"
        :alt="title"
        loading="lazy"
        referrerpolicy="no-referrer"
        class="w-full h-full object-cover transition group-hover:scale-105"
      />
      <span class="absolute right-1.5 bottom-1.5 text-[10px] px-1.5 py-0.5 rounded bg-black/65 text-white font-mono">
        {{ fmtDuration(duration) }}
      </span>
      <span v-if="progress != null && progress > 0" class="absolute left-0 right-0 bottom-0 h-1 bg-black/30">
        <span class="block h-full" :style="{ width: progressPct + '%', background: 'rgb(var(--accent))' }"></span>
      </span>
    </a>

    <div class="flex-1 min-w-0 flex flex-col justify-between py-0.5" :class="reason ? 'pr-24' : ''">
      <!-- line 1: title + stats -->
      <div class="flex items-start gap-x-3 gap-y-1 min-w-0 flex-wrap">
        <a
          :href="biliVideoUrl(bvid)"
          target="_blank"
          rel="noopener"
          class="font-medium text-sm leading-snug truncate flex-1 min-w-0 basis-[12rem] hover:underline"
          :title="title"
        >
          {{ title }}
        </a>
        <div v-if="hasStats" class="flex items-center gap-2.5 text-[11px] text-soft tabular-nums whitespace-nowrap pt-0.5 flex-shrink-0">
          <span title="播放">▷ {{ fmtCount(statPlay) }}</span>
          <span title="点赞">♡ {{ fmtCount(statLike) }}</span>
          <span title="投币">● {{ fmtCount(statCoin) }}</span>
          <span title="收藏">★ {{ fmtCount(statFavorite) }}</span>
          <span title="转发">↗ {{ fmtCount(statShare) }}</span>
        </div>
      </div>

      <!-- line 2: pubdate · UP · desc · [reason] -->
      <div class="flex items-center gap-2 text-xs text-soft min-w-0 mt-1">
        <span v-if="pubdate" class="whitespace-nowrap flex-shrink-0 opacity-80">{{ fmtRelativeTime(pubdate) }}</span>
        <span v-if="pubdate && ownerName" class="opacity-50 flex-shrink-0">·</span>
        <a
          v-if="ownerName"
          :href="biliSpaceUrl(ownerMid ?? null)"
          target="_blank"
          rel="noopener"
          class="hover:underline truncate min-w-0 max-w-[40%]"
          :title="ownerName + (ownerMid ? ` · UID ${ownerMid}` : '')"
        >
          {{ ownerName }}<span v-if="ownerMid" class="opacity-60"> · UID {{ ownerMid }}</span>
        </a>
        <span v-if="descOneLine" class="opacity-50 flex-shrink-0">·</span>
        <span v-if="descOneLine" class="truncate flex-1 min-w-0" :title="descOneLine">{{ descOneLine }}</span>
      </div>
    </div>

    <span
      v-if="reason"
      class="absolute top-1.5 right-1.5 max-w-[22%] truncate text-[10px] leading-tight px-1.5 py-0.5 rounded whitespace-nowrap pointer-events-none reason-badge"
      :title="reason"
    >
      {{ reason }}
    </span>

    <div v-if="removable || aiSummary" class="flex-shrink-0 flex items-center gap-1.5 self-center">
      <button
        v-if="aiSummary"
        class="btn text-xs opacity-0 group-hover:opacity-100 transition"
        @click="emit('summarize')"
      >
        AI 摘要
      </button>
      <button
        v-if="removable"
        class="btn text-xs opacity-0 group-hover:opacity-100 transition"
        @click="emit('remove')"
      >
        移除
      </button>
    </div>
  </article>
</template>
