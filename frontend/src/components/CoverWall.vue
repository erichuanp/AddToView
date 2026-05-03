<script setup lang="ts">
import type { WatchLaterItem } from '../api'
import { biliVideoUrl, fmtDuration } from '../api'

defineProps<{ items: WatchLaterItem[] }>()

function coverSrc(c: string): string {
  if (!c) return ''
  return c.startsWith('http') ? c.replace(/^http:/, 'https:') : c
}
</script>

<template>
  <div class="grid gap-2" style="grid-template-columns: repeat(auto-fill, minmax(180px, 1fr))">
    <a
      v-for="it in items"
      :key="it.bvid"
      :href="biliVideoUrl(it.bvid)"
      target="_blank"
      rel="noopener"
      class="group relative aspect-video rounded-lg overflow-hidden block bg-black/10 transition hover:-translate-y-0.5"
      style="border: 1px solid rgb(var(--border))"
    >
      <img
        v-if="it.cover"
        :src="coverSrc(it.cover)"
        :alt="it.title"
        loading="lazy"
        referrerpolicy="no-referrer"
        class="w-full h-full object-cover transition duration-300 group-hover:scale-110"
      />
      <span class="absolute right-2 bottom-2 text-[10px] px-1.5 py-0.5 rounded bg-black/65 text-white font-mono">
        {{ fmtDuration(it.duration) }}
      </span>
      <div
        class="absolute inset-0 bg-gradient-to-t from-black/85 via-black/30 to-transparent opacity-0 group-hover:opacity-100 transition flex flex-col justify-end p-2 text-white"
      >
        <p class="text-xs font-medium leading-snug line-clamp-2 mb-0.5">{{ it.title }}</p>
        <p class="text-[10px] opacity-80 truncate">{{ it.owner_name }}</p>
      </div>
      <span
        v-if="it.progress > 0"
        class="absolute left-0 right-0 bottom-0 h-1 bg-black/40"
      >
        <span class="block h-full" :style="{ width: Math.min(100, Math.round((it.progress / Math.max(1, it.duration)) * 100)) + '%', background: 'rgb(var(--accent))' }"></span>
      </span>
    </a>
  </div>
</template>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
