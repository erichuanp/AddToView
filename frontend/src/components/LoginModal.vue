<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { api } from '../api'

const emit = defineEmits<{ (e: 'close'): void; (e: 'success'): void }>()

const qrUri = ref('')
const qrKey = ref('')
const status = ref<'pending' | 'scanned' | 'expired' | 'ok' | 'error' | 'starting'>('starting')
const message = ref('正在生成二维码…')
const expiresIn = ref(180)
const consecutiveErrors = ref(0)

let pollTimer: ReturnType<typeof setTimeout> | null = null
let countdownTimer: ReturnType<typeof setInterval> | null = null

async function start() {
  clear()
  status.value = 'starting'
  message.value = '正在生成二维码…'
  try {
    const r = await api.loginStart()
    qrUri.value = r.qr_data_uri
    qrKey.value = r.qrcode_key
    expiresIn.value = r.expires_in
    status.value = 'pending'
    message.value = '等待扫码…'
    countdownTimer = setInterval(() => {
      expiresIn.value -= 1
      if (expiresIn.value <= 0 && countdownTimer) {
        clearInterval(countdownTimer)
        countdownTimer = null
        if (status.value !== 'ok') {
          status.value = 'expired'
          message.value = '二维码已失效'
        }
      }
    }, 1000)
    schedulePoll()
  } catch (e) {
    status.value = 'error'
    message.value = (e as Error).message
  }
}

function schedulePoll(delay = 1500) {
  pollTimer = setTimeout(doPoll, delay)
}

async function doPoll() {
  if (status.value === 'expired' || status.value === 'ok') return
  try {
    const r = await api.loginPoll(qrKey.value)
    consecutiveErrors.value = 0
    status.value = r.status
    message.value = r.message
    if (r.status === 'ok') {
      cleanup()
      emit('success')
      setTimeout(() => emit('close'), 800)
      return
    }
    if (r.status === 'expired') {
      cleanup()
      return
    }
    schedulePoll()
  } catch {
    consecutiveErrors.value += 1
    if (consecutiveErrors.value >= 3) {
      status.value = 'error'
      message.value = '与服务器失联，请重试'
      cleanup()
      return
    }
    schedulePoll(2500)
  }
}

function cleanup() {
  if (pollTimer) {
    clearTimeout(pollTimer)
    pollTimer = null
  }
  if (countdownTimer) {
    clearInterval(countdownTimer)
    countdownTimer = null
  }
}

function clear() {
  cleanup()
  qrUri.value = ''
  qrKey.value = ''
  expiresIn.value = 180
  consecutiveErrors.value = 0
}

onMounted(start)
onBeforeUnmount(cleanup)
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-50 grid place-items-center p-4 bg-black/30 backdrop-blur-sm" @click.self="emit('close')">
      <div class="glass-strong p-7 max-w-sm w-full text-center">
        <h2 class="text-lg font-semibold mb-1">扫码登录哔哩哔哩</h2>
        <p class="text-soft text-xs mb-4">使用 B 站手机客户端扫描二维码</p>

        <div class="relative mx-auto w-56 h-56 grid place-items-center rounded-2xl glass-soft overflow-hidden">
          <img v-if="qrUri" :src="qrUri" class="w-full h-full object-contain p-2" alt="QR" />
          <div v-else class="text-soft text-sm">加载中…</div>

          <div
            v-if="status === 'scanned' || status === 'expired'"
            class="absolute inset-0 grid place-items-center bg-black/60 text-white text-sm font-medium"
          >
            <span v-if="status === 'scanned'">已扫码<br/>请在手机上确认</span>
            <span v-if="status === 'expired'">已失效</span>
          </div>
        </div>

        <p class="mt-4 text-sm" :class="{
          'text-rose-500': status === 'expired' || status === 'error',
          'text-emerald-500': status === 'ok',
        }">{{ message }}</p>

        <p v-if="status === 'pending' && expiresIn > 0" class="text-xs text-soft mt-1">
          剩余 {{ expiresIn }} 秒
        </p>

        <div class="flex gap-2 justify-center mt-5">
          <button v-if="status === 'expired' || status === 'error'" class="btn-primary" @click="start">刷新二维码</button>
          <button class="btn" @click="emit('close')">关闭</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
