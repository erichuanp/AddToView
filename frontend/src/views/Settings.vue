<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, fmtRelativeTime, type StatusInfo } from '../api'
import { openLogsPanel } from '../composables/useLogsPanel'
import LoginModal from '../components/LoginModal.vue'
import { useNow } from '../composables/useNow'
import { useToast } from '../composables/useToast'
import { useTheme, type ThemeChoice } from '../composables/useTheme'

const now = useNow()

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

interface LLMSlotView {
  base_url: string
  model_id: string
  api_key?: string         // new shape (backend on this version)
  api_key_tail?: string    // legacy shape (backend pre-restart)
  api_key_set: boolean
}

// Slots are 3 presets. `llmActive` = which one AI features actually use.
// `llmSelected` = which one the form is editing (UI-only). Click a tab →
// load that slot into the form without activating it.
const llmForm = ref({ base_url: '', model_id: '', api_key: '' })
const llmSlots = ref<LLMSlotView[]>([])
const llmActive = ref(0)
const llmSelected = ref(0)
const llmConfigured = ref(false)
const llmTesting = ref(false)
const llmSaving = ref(false)
const llmTestResult = ref<{ ok: boolean; message: string } | null>(null)
const llmKeyVisible = ref(false)

function loadFormFromSlot(idx: number) {
  const slot = llmSlots.value[idx]
  if (!slot) return
  llmForm.value = {
    base_url: slot.base_url ?? '',
    model_id: slot.model_id ?? '',
    api_key: slot.api_key ?? '', // backend on legacy shape only sends tail; treat as empty
  }
  llmKeyVisible.value = false
  llmTestResult.value = null
}

function selectSlot(idx: number) {
  // pure UI: just preview the slot's saved values in the form
  llmSelected.value = idx
  loadFormFromSlot(idx)
}

const lookbackDays = ref(3)
const lookbackSaving = ref(false)

async function refresh() {
  loading.value = true
  try {
    const [s, h, sync, llmStatus] = await Promise.all([
      api.status(),
      api.health(),
      api.syncStatus(),
      api.llmStatus(),
    ])
    status.value = s
    health.value = h
    lastSyncAt.value = sync.last_sync_at
    lookbackDays.value = sync.lookback_days
    llmSlots.value = llmStatus.slots
    llmActive.value = llmStatus.active_slot
    llmSelected.value = llmStatus.active_slot
    llmConfigured.value = llmStatus.configured
    loadFormFromSlot(llmSelected.value)
  } finally {
    loading.value = false
  }
}

async function saveLookback() {
  const v = Math.max(1, Math.min(60, Math.floor(lookbackDays.value || 3)))
  lookbackDays.value = v
  lookbackSaving.value = true
  try {
    await api.settingsPut('sync_lookback_days', String(v))
    toast.success(`已保存：每次同步回溯 ${v} 天`)
  } catch (e) {
    toast.error((e as Error).message)
  } finally {
    lookbackSaving.value = false
  }
}

async function testLlm() {
  llmTesting.value = true
  llmTestResult.value = null
  try {
    const r = await api.llmTest({
      base_url: llmForm.value.base_url.trim(),
      model_id: llmForm.value.model_id.trim(),
      api_key: llmForm.value.api_key.trim(), // may be empty for local LLMs
    })
    if (r.normalized_base_url) {
      llmForm.value.base_url = r.normalized_base_url
    }
    if (r.ok) {
      llmTestResult.value = { ok: true, message: `连接成功，AI 回复："${r.reply ?? ''}"` }
    } else {
      llmTestResult.value = { ok: false, message: r.error ?? '未知错误' }
    }
  } catch (e) {
    llmTestResult.value = { ok: false, message: (e as Error).message }
  } finally {
    llmTesting.value = false
  }
}

/** 保存：写入选中的栏位 + 把它设为 active（AI 摘要使用此配置）。 */
async function saveLlm() {
  llmSaving.value = true
  try {
    const r = await api.llmSaveSlot(llmSelected.value, {
      base_url: llmForm.value.base_url.trim(),
      model_id: llmForm.value.model_id.trim(),
      api_key: llmForm.value.api_key.trim(), // empty allowed for local LLMs
    })
    llmSlots.value[llmSelected.value] = r.slot
    await api.llmActivateSlot(llmSelected.value)
    llmActive.value = llmSelected.value
    const status = await api.llmStatus()
    llmConfigured.value = status.configured
    loadFormFromSlot(llmSelected.value)
    toast.success(`已保存并激活栏位 ${llmSelected.value + 1}`)
  } catch (e) {
    toast.error((e as Error).message)
  } finally {
    llmSaving.value = false
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
        每次"同步"或"一键添加"固定向回看 N 天的关注动态，重复抓取已处理过的视频是无害的（会自动跳过）。
      </p>
      <div class="text-sm flex flex-wrap items-center gap-3 mb-3">
        <span class="text-soft w-20 flex-shrink-0">回溯天数</span>
        <input
          v-model.number="lookbackDays"
          type="number"
          min="1"
          max="60"
          class="px-2 py-1 w-24 outline-none text-sm"
        />
        <button class="btn" :disabled="lookbackSaving" @click="saveLookback">
          {{ lookbackSaving ? '保存中…' : '保存' }}
        </button>
        <span class="text-xs text-soft">范围 1–60 天，默认 3</span>
      </div>
      <div class="text-sm flex flex-wrap items-center gap-3">
        <span class="text-soft w-20 flex-shrink-0">上次同步</span>
        <strong v-if="lastSyncAt" :title="new Date(lastSyncAt * 1000).toLocaleString('zh-CN')">{{ fmtRelativeTime(lastSyncAt, now) }}</strong>
        <em v-else class="text-soft">尚未同步过</em>
      </div>
    </div>

    <div class="glass p-5 mb-4">
      <h2 class="font-medium mb-3">外观</h2>
      <div class="flex items-center gap-2 text-sm flex-wrap">
        <span class="text-soft flex-shrink-0">主题</span>
        <div class="glass-soft flex overflow-hidden rounded-full ml-2 flex-shrink-0">
          <button
            v-for="opt in themeOptions"
            :key="opt.value"
            class="px-3 py-1 transition whitespace-nowrap"
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

    <div class="glass p-4 sm:p-5 mb-4">
      <div class="flex items-center gap-2 mb-3 flex-wrap">
        <h2 class="font-medium flex items-center gap-2">
          LLM API
          <span class="dot" :class="llmConfigured ? 'dot-ok' : 'dot-err'"></span>
          <span class="text-xs text-soft font-normal">{{ llmConfigured ? '已配置' : '未配置（AI 摘要不可用）' }}</span>
        </h2>
        <div class="ml-auto flex gap-1 flex-wrap">
          <button
            v-for="(s, i) in llmSlots"
            :key="i"
            class="px-2.5 py-1 text-xs rounded-md transition"
            :class="i === llmSelected ? 'nav-active font-medium' : 'glass-soft opacity-70 hover:opacity-100'"
            :title="i === llmActive ? 'AI 摘要正在用此栏位' : (s.base_url ? '已配置' : '空')"
            @click="selectSlot(i)"
          >
            栏位 {{ i + 1 }}<span v-if="i === llmActive" class="ml-1" :style="{ color: 'rgb(var(--emerald))' }">★</span><span v-else-if="s.base_url" class="ml-1 opacity-60">●</span>
          </button>
        </div>
      </div>
      <p class="text-soft text-xs mb-3">
        OpenAI 兼容接口（chat.completions）。例如豆包、Kimi、智谱、自部署的 LiteLLM/Ollama 等。可保存 3 套配置随时切换。
      </p>
      <!-- :key forces all 3 inputs to remount when the user clicks a different
           slot — prevents browser autofill / type=password caching from
           displaying the previous slot's value -->
      <div class="flex flex-col gap-2" :key="'slot-' + llmSelected">
        <label class="flex items-center gap-3 text-sm">
          <span class="text-soft w-20 flex-shrink-0">Base URL</span>
          <input v-model="llmForm.base_url" placeholder="https://api.example.com/v1/chat/completions" class="px-2 py-1 flex-1 outline-none text-sm" autocomplete="off" />
        </label>
        <label class="flex items-center gap-3 text-sm">
          <span class="text-soft w-20 flex-shrink-0">Model</span>
          <input v-model="llmForm.model_id" placeholder="模型名（如 gpt-4o-mini / kimi-k2 / 自定义）" class="px-2 py-1 flex-1 outline-none text-sm" autocomplete="off" />
        </label>
        <label class="flex items-center gap-3 text-sm">
          <span class="text-soft w-20 flex-shrink-0">API Key</span>
          <div class="flex-1 flex items-center gap-1.5 min-w-0">
            <input
              v-model="llmForm.api_key"
              :type="llmKeyVisible ? 'text' : 'password'"
              placeholder="可留空（本地模型不需要）"
              class="px-2 py-1 flex-1 outline-none text-sm font-mono min-w-0"
              autocomplete="new-password"
              spellcheck="false"
            />
            <button
              type="button"
              class="btn-ghost text-base px-2 py-1 flex-shrink-0"
              :title="llmKeyVisible ? '隐藏' : '显示'"
              @click="llmKeyVisible = !llmKeyVisible"
            >
              <span v-if="llmKeyVisible">🙈</span><span v-else>👁</span>
            </button>
          </div>
        </label>
        <div class="flex items-center gap-2 mt-1 flex-wrap">
          <button class="btn" :disabled="llmTesting" @click="testLlm">{{ llmTesting ? '测试中…' : '测试' }}</button>
          <button class="btn-primary" :disabled="llmSaving" @click="saveLlm" title="保存到此栏位并激活为 AI 配置">
            {{ llmSaving ? '保存中…' : '保存' }}
          </button>
          <p v-if="llmTestResult" class="text-xs ml-2 flex-1 truncate" :style="{ color: llmTestResult.ok ? 'rgb(var(--emerald))' : 'rgb(var(--rose))' }" :title="llmTestResult.message">
            {{ llmTestResult.message }}
          </p>
        </div>
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
      <div class="flex flex-wrap gap-2 mt-3">
        <button class="btn" :disabled="loading" @click="refresh">重新检查</button>
        <button class="btn" @click="openLogsPanel">查看日志</button>
      </div>
    </div>

    <LoginModal v-if="showLogin" @close="showLogin = false" @success="onLoginSuccess" />
  </section>
</template>
