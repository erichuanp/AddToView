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
          class="glass-strong px-4 py-2.5 text-sm pointer-events-auto cursor-pointer max-w-sm"
          :class="{
            'toast-error': t.tone === 'error',
            'toast-warn': t.tone === 'warn',
            'toast-success': t.tone === 'success',
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
.toast-error { border-color: rgba(var(--rose), 0.45); }
.toast-warn { border-color: rgba(var(--amber), 0.45); }
.toast-success { border-color: rgba(var(--emerald), 0.45); }
</style>
