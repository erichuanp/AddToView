<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, fmtRelativeTime, type StatusInfo } from '../api'
import LoginModal from '../components/LoginModal.vue'
import { useToast } from '../composables/useToast'
import { useTheme, type ThemeChoice } from '../composables/useTheme'

const theme = useTheme()
const themeOptions: { value: ThemeChoice; label: string }[] = [
  { value: 'light', label: '浅色' },
  { value: 'dark', label: '暗色' },
  { value: 'auto', label: '跟随系统' },
]

interface BlacklistExport {
  version: number
  kind: 'blacklist'
  rules: { kind: string; value: string; note: string; enabled: boolean; hit_count: number }[]
}

const status = ref<StatusInfo | null>(null)
const health = ref<{ ok: boolean; version: string } | null>(null)
const loading = ref(false)
const showLogin = ref(false)
const lastSyncAt = ref<number | null>(null)
const toast = useToast()

async function refresh() {
  loading.value = true
  try {
    const [s, h, sync] = await Promise.all([
      api.status(),
      api.health(),
      api.syncStatus(),
    ])
    status.value = s
    health.value = h
    lastSyncAt.value = sync.last_sync_at
  } finally {
    loading.value = false
  }
}

async function resetLastSync() {
  if (!confirm('清除上次同步时间？下次同步会再次询问回溯天数。')) return
  try {
    await api.settingsPut('last_sync_at', '')
    lastSyncAt.value = null
    toast.success('已清除')
  } catch (e) {
    toast.error((e as Error).message)
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

async function exportBlacklist() {
  try {
    const r = await fetch('/api/export/blacklist.json')
    if (!r.ok) throw new Error(await r.text())
    const data = (await r.json()) as BlacklistExport
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    const stamp = new Date().toISOString().slice(0, 10)
    a.download = `addtoview-blacklist-${stamp}.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    toast.success(`已导出 ${data.rules.length} 条规则`)
  } catch (e) {
    toast.error((e as Error).message)
  }
}

async function importBlacklist(ev: Event, mode: 'merge' | 'replace') {
  const target = ev.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return
  try {
    const text = await file.text()
    const json = JSON.parse(text)
    const rules = (json.rules ?? []) as { kind: string; value: string; note?: string; enabled?: boolean }[]
    if (mode === 'replace' && !confirm(`确认用导入的 ${rules.length} 条规则替换现有所有规则？此操作不可撤销。`)) {
      target.value = ''
      return
    }
    const r = await fetch('/api/export/blacklist/import', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ rules, mode }),
    })
    if (!r.ok) throw new Error(await r.text())
    const data = await r.json()
    toast.success(`导入完成：新增 ${data.inserted}，跳过 ${data.skipped}`)
  } catch (e) {
    toast.error(`导入失败：${(e as Error).message}`)
  } finally {
    target.value = ''
  }
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
      <h2 class="font-medium mb-3">同步状态</h2>
      <p class="text-sm text-soft mb-3">
        每次"同步"或"一键添加"会从上次同步时刻向后抓取，无需手动指定天数。
      </p>
      <div class="text-sm flex flex-wrap items-center gap-3">
        <span class="text-soft">上次同步：</span>
        <strong v-if="lastSyncAt" :title="new Date(lastSyncAt * 1000).toLocaleString('zh-CN')">{{ fmtRelativeTime(lastSyncAt) }}</strong>
        <em v-else class="text-soft">尚无（下次同步会询问回溯天数）</em>
        <button v-if="lastSyncAt" class="btn text-xs ml-auto" @click="resetLastSync">清除并重新询问</button>
      </div>
    </div>

    <div class="glass p-5 mb-4">
      <h2 class="font-medium mb-3">外观</h2>
      <div class="flex items-center gap-2 text-sm">
        <span class="text-soft">主题</span>
        <div class="glass-soft flex overflow-hidden rounded-full ml-2">
          <button
            v-for="opt in themeOptions"
            :key="opt.value"
            class="px-3 py-1 transition"
            :class="theme.choice.value === opt.value ? 'nav-active font-medium' : 'opacity-70 hover:opacity-100'"
            @click="theme.setChoice(opt.value)"
          >
            {{ opt.label }}
          </button>
        </div>
        <span v-if="theme.choice.value === 'auto'" class="text-xs text-soft ml-2">
          当前 ({{ theme.systemDark.value ? '暗色' : '浅色' }})
        </span>
      </div>
    </div>

    <div class="glass p-5 mb-4">
      <h2 class="font-medium mb-2">导入 / 导出</h2>
      <p class="text-soft text-sm mb-3">把黑名单规则备份成 JSON，或在新机器/新账号上恢复。</p>
      <div class="flex flex-wrap gap-2 items-center">
        <button class="btn-primary" @click="exportBlacklist">导出黑名单</button>
        <label class="btn cursor-pointer">
          合并导入
          <input type="file" accept="application/json" class="hidden" @change="importBlacklist($event, 'merge')" />
        </label>
        <label class="btn cursor-pointer">
          替换导入
          <input type="file" accept="application/json" class="hidden" @change="importBlacklist($event, 'replace')" />
        </label>
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
