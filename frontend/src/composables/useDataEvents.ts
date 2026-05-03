// 简易事件总线：同步 / 一键添加后通知各页面刷新
// 用 ref 当 epoch 时间戳，watch 它就能拿到「数据变了」信号
import { ref } from 'vue'

export const pendingChangedAt = ref(0)
export const watchlaterChangedAt = ref(0)

export function bumpPending() {
  pendingChangedAt.value = Date.now()
}

export function bumpWatchlater() {
  watchlaterChangedAt.value = Date.now()
}
