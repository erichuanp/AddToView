<script setup lang="ts">
import { useToast } from '../composables/useToast'

const toast = useToast()
</script>

<template>
  <Teleport to="body">
    <div class="fixed top-3 right-3 z-[60] flex flex-col gap-2 items-end pointer-events-none">
      <TransitionGroup name="toast">
        <div
          v-for="t in toast.state.items"
          :key="t.id"
          class="glass-strong px-4 py-2.5 text-sm shadow-lg pointer-events-auto cursor-pointer max-w-sm"
          :class="{
            'border-rose-500/40': t.tone === 'error',
            'border-amber-400/40': t.tone === 'warn',
            'border-emerald-400/40': t.tone === 'success',
          }"
          @click="toast.dismiss(t.id)"
        >
          <span class="dot" :class="{
            'dot-ok': t.tone === 'success',
            'dot-err': t.tone === 'error',
            'dot-warn': t.tone === 'warn',
          }"></span>
          {{ t.text }}
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<style scoped>
.toast-enter-active, .toast-leave-active { transition: all 220ms ease; }
.toast-enter-from { opacity: 0; transform: translateX(20px) scale(0.95); }
.toast-leave-to { opacity: 0; transform: translateX(20px) scale(0.95); }
</style>
