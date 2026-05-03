<script setup lang="ts">
defineProps<{ title: string; hint?: string; tone?: 'info' | 'warn' | 'err' }>()
</script>

<template>
  <div class="glass-soft p-10 text-center my-10 mx-auto max-w-lg">
    <div class="text-3xl mb-2 select-none">
      <span v-if="tone === 'err'">!</span>
      <span v-else-if="tone === 'warn'">~</span>
      <span v-else>·</span>
    </div>
    <h3 class="font-semibold text-lg">{{ title }}</h3>
    <p v-if="hint" class="text-soft text-sm mt-1.5 leading-relaxed whitespace-pre-line">{{ hint }}</p>
    <slot />
  </div>
</template>
