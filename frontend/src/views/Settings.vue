<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, type StatusInfo } from '../api'
import LoginModal from '../components/LoginModal.vue'
import { useToast } from '../composables/useToast'

const status = ref<StatusInfo | null>(null)
const health = ref<{ ok: boolean; version: string } | null>(null)
const loading = ref(false)
const showLogin = ref(false)
const defaultDays = ref('7')
const statsWindow = ref('30')
const saving = ref(false)
const toast = useToast()

async function refresh() {
  loading.value = true
  try {
    const [s, h, ss] = await Promise.all([api.status(), api.health(), api.settingsAll()])
    status.value = s
    health.value = h
    defaultDays.value = ss.items.default_sync_days || '7'
    statsWindow.value = ss.items.stats_window_days || '30'
  } finally {
    loading.value = false
  }
}

async function saveDefaults() {
  saving.value = true
  try {
    await Promise.all([
      api.settingsPut('default_sync_days', defaultDays.value.trim()),
      api.settingsPut('stats_window_days', statsWindow.value.trim()),
    ])
    toast.success('设置已保存')
  } catch (e) {
    toast.error((e as Error).message)
  } finally {
    saving.value = false
  }
}

async function doLogout() {
  if (!confirm('确认退出登录？(将停用当前 cookie)')) return
  try {
    await api.logout()
    toast.success('已退出登录')
    await refresh()
  } catch (e) {
    toast.error((e as Error).message)
  }
}

function onLoginSuccess() {
  toast.success('登录成功')
  refresh()
}

onMounted(refresh)
</script>

<template>
  <section class="max-w-3xl mx-auto">
    <h1 class="text-xl font-semibold mb-4">设置</h1>

    <div class="glass p-5 mb-4">
      <h2 class="font-medium mb-2">登录状态</h2>
      <div v-if="status" class="text-sm text-soft space-y-1">
        <p>
          <span class="dot" :class="status.logged_in ? 'dot-ok' : status.cookie_present ? 'dot-warn' : 'dot-err'"></span>
          <span v-if="status.logged_in">已登录为 <strong class="text-current">{{ status.uname }}</strong>（UID {{ status.mid }}）</span>
          <span v-else-if="status.cookie_present">cookie 已加载但失效，需要重新登录</span>
          <span v-else>未检测到 cookie，请扫码登录</span>
        </p>
        <p v-if="status.cookie_present">大会员状态：{{ status.vip_status === 1 ? '是' : '否' }}</p>
      </div>
      <div class="flex gap-2 mt-4">
        <button class="btn-primary" @click="showLogin = true">{{ status?.logged_in ? '换号' : '扫码登录' }}</button>
        <button v-if="status?.logged_in" class="btn" @click="doLogout">退出登录</button>
      </div>
    </div>

    <div class="glass p-5 mb-4">
      <h2 class="font-medium mb-3">默认参数</h2>
      <div class="flex flex-wrap items-center gap-3 text-sm">
        <label class="flex items-center gap-2">
          <span class="text-soft">同步时回溯天数</span>
          <input v-model="defaultDays" type="number" min="1" max="60" class="glass-soft px-2 py-1 w-16 text-right outline-none" />
        </label>
        <label class="flex items-center gap-2">
          <span class="text-soft">统计页默认窗口</span>
          <input v-model="statsWindow" type="number" min="1" max="365" class="glass-soft px-2 py-1 w-16 text-right outline-none" />
          <span class="text-soft">天</span>
        </label>
        <button class="btn-primary" :disabled="saving" @click="saveDefaults">保存</button>
      </div>
    </div>

    <div class="glass p-5">
      <h2 class="font-medium mb-2">服务</h2>
      <div class="text-sm text-soft">
        <p v-if="health">后端版本: {{ health.version }}</p>
        <p v-else>后端: 未连接</p>
      </div>
      <button class="btn mt-3" :disabled="loading" @click="refresh">重新检查</button>
    </div>

    <LoginModal v-if="showLogin" @close="showLogin = false" @success="onLoginSuccess" />
  </section>
</template>
