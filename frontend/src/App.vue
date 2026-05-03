<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink, RouterView } from 'vue-router'
import { api, fmtRelativeTime, type StatusInfo } from './api'
import LoginModal from './components/LoginModal.vue'
import ToastHost from './components/ToastHost.vue'
import { useNow } from './composables/useNow'
import { useToast } from './composables/useToast'

const status = ref<StatusInfo | null>(null)
const loading = ref(false)
const showLogin = ref(false)
const lastSyncAt = ref<number | null>(null)
const now = useNow()
const toast = useToast()

async function refreshStatus() {
  try {
    status.value = await api.status()
  } catch {
    status.value = { logged_in: false, mid: null, uname: '', vip_status: 0, cookie_present: false }
  }
}

async function refreshSyncStatus() {
  try {
    const r = await api.syncStatus()
    lastSyncAt.value = r.last_sync_at
  } catch {
    /* ignore */
  }
}

/** Try a sync action; on first_sync error, prompt user for days then retry once. */
async function callWithFirstSyncFallback<T>(
  callOnce: (days?: number) => Promise<T>,
): Promise<T | null> {
  try {
    return await callOnce()
  } catch (e) {
    const msg = (e as Error).message ?? ''
    if (!msg.includes('first_sync') && !msg.includes('首次同步')) {
      throw e
    }
    const input = window.prompt(
      '这是第一次同步，需要回溯多少天的视频？（之后再同步会自动从上次同步时间继续）',
      '3',
    )
    if (input == null) return null
    const days = Math.max(1, Math.min(60, parseInt(input, 10) || 3))
    return await callOnce(days)
  }
}

async function doSync() {
  if (loading.value) return
  loading.value = true
  try {
    const r = await callWithFirstSyncFallback((days) => api.syncDynamic(days))
    if (r) {
      toast.success(`同步完成：抓 ${r.fetched} / 新 ${r.new} / 命中黑名单 ${r.filtered}`)
      await refreshSyncStatus()
    }
  } catch (e) {
    toast.error(`同步失败：${(e as Error).message}`)
  } finally {
    loading.value = false
  }
}

async function doAutoAdd() {
  if (loading.value) return
  loading.value = true
  try {
    const r = await callWithFirstSyncFallback((days) => api.autoAdd(days))
    if (r) {
      const filteredCount = r.sync.filtered ?? 0
      toast.success(
        `一键添加完成：加入 ${r.add.added.length} · 跳过 ${r.add.skipped.length} · 错误 ${r.add.errors.length}` +
          (filteredCount ? ` · 过滤 ${filteredCount}` : ''),
      )
      await refreshSyncStatus()
    }
  } catch (e) {
    toast.error(`一键添加失败：${(e as Error).message}`)
  } finally {
    loading.value = false
  }
}

function openLogin() {
  showLogin.value = true
}

function onLoginSuccess() {
  toast.success('登录成功')
  refreshStatus()
}

onMounted(async () => {
  await Promise.all([refreshStatus(), refreshSyncStatus()])
})
</script>

<template>
  <div class="min-h-screen flex flex-col">
    <header class="sticky top-3 z-30 mx-3 md:mx-6 mt-3">
      <div class="glass-strong px-4 py-2.5 flex items-center gap-3">
        <span class="wordmark text-base font-semibold tracking-tight">AddToView</span>
        <nav class="flex gap-0.5 ml-2">
          <RouterLink class="btn-ghost" active-class="nav-active" :to="{ name: 'watchlater' }">稍后再看</RouterLink>
          <RouterLink class="btn-ghost" active-class="nav-active" :to="{ name: 'queue' }">待选视频</RouterLink>
          <RouterLink class="btn-ghost" active-class="nav-active" :to="{ name: 'blacklist' }">黑名单</RouterLink>
          <RouterLink class="btn-ghost" active-class="nav-active" :to="{ name: 'settings' }">设置</RouterLink>
        </nav>
        <div class="flex-1"></div>
        <span v-if="lastSyncAt" class="text-xs text-soft" :title="new Date(lastSyncAt * 1000).toLocaleString('zh-CN')">
          上次同步 {{ fmtRelativeTime(lastSyncAt, now) }}
        </span>
        <template v-if="status?.logged_in">
          <button class="btn" :disabled="loading" @click="doSync" title="抓取自上次同步以来关注 UP 主的新视频（首次会询问天数）">
            {{ loading ? '处理中…' : '同步' }}
          </button>
          <button class="btn-primary" :disabled="loading" @click="doAutoAdd" title="同步 + 把待添加视频推入稍后再看">
            {{ loading ? '…' : '一键添加' }}
          </button>
        </template>
        <button v-else class="btn-primary" @click="openLogin">登录</button>
        <span class="flex items-center text-xs text-soft pl-3 ml-1 border-l border-[rgb(var(--border))]">
          <template v-if="status?.logged_in">
            <span class="dot dot-ok"></span>{{ status.uname || '已登录' }}
          </template>
          <template v-else-if="status?.cookie_present">
            <span class="dot dot-warn"></span>cookie 已失效
          </template>
          <template v-else>
            <span class="dot dot-err"></span>未登录
          </template>
        </span>
      </div>
    </header>

    <main class="flex-1 px-3 md:px-6 py-4">
      <RouterView v-slot="{ Component }">
        <Transition name="fade" mode="out-in">
          <component :is="Component" />
        </Transition>
      </RouterView>
    </main>

    <footer class="px-6 py-4 text-center text-xs text-soft">
      AddToView
    </footer>

    <LoginModal v-if="showLogin" @close="showLogin = false" @success="onLoginSuccess" />
    <ToastHost />
  </div>
</template>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 180ms ease, transform 180ms ease; }
.fade-enter-from { opacity: 0; transform: translateY(4px); }
.fade-leave-to { opacity: 0; transform: translateY(-4px); }
</style>
