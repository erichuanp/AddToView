<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink, RouterView } from 'vue-router'
import { api, type StatusInfo } from './api'
import LoginModal from './components/LoginModal.vue'
import ToastHost from './components/ToastHost.vue'
import { useToast } from './composables/useToast'

const status = ref<StatusInfo | null>(null)
const loading = ref(false)
const showLogin = ref(false)
const defaultDays = ref(7)
const toast = useToast()

async function refreshStatus() {
  try {
    status.value = await api.status()
  } catch {
    status.value = { logged_in: false, mid: null, uname: '', vip_status: 0, cookie_present: false }
  }
}

async function loadDefaults() {
  try {
    const r = await api.settingsAll()
    const v = parseInt(r.items.default_sync_days, 10)
    if (Number.isFinite(v) && v > 0) defaultDays.value = v
  } catch {
    /* ignore */
  }
}

async function doSync() {
  loading.value = true
  try {
    const r = await api.syncDynamic(defaultDays.value)
    toast.success(`同步完成：抓 ${r.fetched} / 新 ${r.new} / 命中黑名单 ${r.filtered}`)
  } catch (e) {
    toast.error(`同步失败：${(e as Error).message}`)
  } finally {
    loading.value = false
  }
}

async function doAutoAdd() {
  loading.value = true
  try {
    const r = await api.syncDynamic(defaultDays.value)
    const a = await api.autoAdd(defaultDays.value)
    toast.success(
      `已加入 ${a.added.length} 个视频到稍后再看 · 跳过 ${a.skipped.length} · 错误 ${a.errors.length}` +
        (r.filtered ? ` · 过滤 ${r.filtered}` : ''),
    )
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
  await Promise.all([refreshStatus(), loadDefaults()])
})
</script>

<template>
  <div class="min-h-screen flex flex-col">
    <header class="sticky top-3 z-30 mx-3 md:mx-6 mt-3">
      <div class="glass-strong px-4 py-2.5 flex items-center gap-3">
        <span class="text-lg font-semibold tracking-tight bg-gradient-to-r from-[#00a1d6] to-[#fb7299] bg-clip-text text-transparent">AddToView</span>
        <nav class="flex gap-1 ml-2">
          <RouterLink class="btn-ghost" active-class="!bg-white/40 dark:!bg-white/10 !text-current" :to="{ name: 'watchlater' }">稍后再看</RouterLink>
          <RouterLink class="btn-ghost" active-class="!bg-white/40 dark:!bg-white/10 !text-current" :to="{ name: 'filtered' }">已过滤</RouterLink>
          <RouterLink class="btn-ghost" active-class="!bg-white/40 dark:!bg-white/10 !text-current" :to="{ name: 'blacklist' }">黑名单</RouterLink>
          <RouterLink class="btn-ghost" active-class="!bg-white/40 dark:!bg-white/10 !text-current" :to="{ name: 'stats' }">统计</RouterLink>
          <RouterLink class="btn-ghost" active-class="!bg-white/40 dark:!bg-white/10 !text-current" :to="{ name: 'settings' }">设置</RouterLink>
        </nav>
        <div class="flex-1"></div>
        <template v-if="status?.logged_in">
          <button class="btn" :disabled="loading" @click="doSync" :title="`抓取最近 ${defaultDays} 天的关注 UP 主新视频，仅入库不添加`">
            {{ loading ? '处理中…' : '同步' }}
          </button>
          <button class="btn-primary" :disabled="loading" @click="doAutoAdd" :title="`同步 + 自动加入稍后再看（按当前黑名单过滤）`">
            {{ loading ? '…' : `一键添加 ${defaultDays}天` }}
          </button>
        </template>
        <button v-else class="btn-primary" @click="openLogin">登录</button>
        <span class="flex items-center text-xs text-soft pl-2 border-l border-white/20">
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
      AddToView · 玻璃拟态 · 跟随系统主题
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
