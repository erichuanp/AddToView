import { ref } from 'vue'

// 全局浮动日志面板的开关。挂在 App.vue 顶层，所以无论用户在哪个页面，
// 都能开着窗口看实时日志，同时不挡顶部栏的 同步 / 一键添加。
export const logsPanelVisible = ref(false)

export function openLogsPanel(): void {
  logsPanelVisible.value = true
}

export function closeLogsPanel(): void {
  logsPanelVisible.value = false
}
