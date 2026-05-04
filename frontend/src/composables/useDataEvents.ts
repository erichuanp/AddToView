// 简易事件总线：同步 / 一键添加后通知各页面刷新
// 用 ref 当 epoch 时间戳，watch 它就能拿到「数据变了」信号
import { ref } from 'vue'

export const pendingChangedAt = ref(0)
export const watchlaterChangedAt = ref(0)
// 视频摘要被深度刷新时 push 这条；卡片 watch 它同步自己的内联摘要文本
export const summaryUpdate = ref<{ bvid: string; text: string; ts: number } | null>(null)

export function bumpPending() {
  pendingChangedAt.value = Date.now()
}

export function bumpWatchlater() {
  watchlaterChangedAt.value = Date.now()
}

export function bumpSummary(bvid: string, text: string) {
  summaryUpdate.value = { bvid, text, ts: Date.now() }
}
