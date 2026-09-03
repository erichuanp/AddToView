// 「显示 AI 相关功能」开关：关掉之后前端所有 AI 入口（AI 摘要按钮、
// AI 建议规则、LLM API 配置）都不渲染。纯前端偏好，跟主题一样存 localStorage。
import { ref, watch } from 'vue'

const STORAGE_KEY = 'addtoview.ai_features'

function readVisible(): boolean {
  const v = typeof localStorage !== 'undefined' ? localStorage.getItem(STORAGE_KEY) : null
  // 没存过 = 默认显示
  return v === null ? true : v === '1'
}

const visible = ref(readVisible())

watch(visible, () => {
  try {
    localStorage.setItem(STORAGE_KEY, visible.value ? '1' : '0')
  } catch {
    /* localStorage may be disabled */
  }
})

export function useAiFeatures() {
  return {
    visible,
    setVisible(next: boolean) {
      visible.value = next
    },
  }
}
