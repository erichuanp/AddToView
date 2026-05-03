<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api, type BlacklistKind, type BlacklistRule, type DryRunHit } from '../api'
import EmptyState from '../components/EmptyState.vue'
import VideoListItem from '../components/VideoListItem.vue'
import { useToast } from '../composables/useToast'

const rules = ref<BlacklistRule[]>([])
const kinds = ref<BlacklistKind[]>([])
const loading = ref(false)
const error = ref('')

const form = ref({ kind: 'title_keyword', value: '', note: '' })

const dryRun = ref<{ tested: number; would_filter: number; items: DryRunHit[] } | null>(null)
const dryRunLoading = ref(false)
const dryRunDays = ref(7)

const aiSuggestions = ref<{ kind: string; value: string; reason: string }[] | null>(null)
const aiNote = ref('')
const aiLoading = ref(false)
const toast = useToast()

const currentHint = computed(() => kinds.value.find((k) => k.value === form.value.kind)?.hint ?? '')

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [r, k] = await Promise.all([api.blacklistList(), api.blacklistKinds()])
    rules.value = r.items
    kinds.value = k.kinds
    if (!kinds.value.find((x) => x.value === form.value.kind)) {
      form.value.kind = kinds.value[0]?.value ?? 'title_keyword'
    }
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

async function add() {
  if (!form.value.value.trim()) return
  try {
    await api.blacklistCreate(form.value.kind, form.value.value, form.value.note)
    form.value.value = ''
    form.value.note = ''
    await load()
  } catch (e) {
    alert((e as Error).message)
  }
}

async function toggle(r: BlacklistRule) {
  try {
    await api.blacklistPatch(r.id, { enabled: !r.enabled })
    r.enabled = !r.enabled
  } catch (e) {
    alert((e as Error).message)
  }
}

async function del(r: BlacklistRule) {
  if (!confirm(`删除规则: ${r.kind} = "${r.value}"？`)) return
  try {
    await api.blacklistDelete(r.id)
    rules.value = rules.value.filter((x) => x.id !== r.id)
  } catch (e) {
    alert((e as Error).message)
  }
}

async function runDry() {
  dryRunLoading.value = true
  try {
    dryRun.value = await api.blacklistDryRun(dryRunDays.value)
  } catch (e) {
    alert((e as Error).message)
  } finally {
    dryRunLoading.value = false
  }
}

async function runAiSuggest() {
  aiLoading.value = true
  aiNote.value = ''
  try {
    const r = await api.blacklistSuggest(30)
    aiSuggestions.value = r.suggestions
    if (r.note) aiNote.value = r.note
    if (r.error) toast.warn(r.error)
    if (r.suggestions.length === 0 && !r.note) toast.info('AI 暂时没有建议')
  } catch (e) {
    toast.error((e as Error).message)
  } finally {
    aiLoading.value = false
  }
}

async function acceptSuggestion(s: { kind: string; value: string; reason: string }) {
  try {
    await api.blacklistCreate(s.kind, s.value, `AI 建议：${s.reason}`)
    aiSuggestions.value = (aiSuggestions.value ?? []).filter((x) => x !== s)
    toast.success('已接受')
    await load()
  } catch (e) {
    toast.error((e as Error).message)
  }
}

function rejectSuggestion(s: { kind: string; value: string; reason: string }) {
  aiSuggestions.value = (aiSuggestions.value ?? []).filter((x) => x !== s)
}

const kindLabel = computed(() => {
  const m = new Map(kinds.value.map((k) => [k.value, k.label]))
  return (v: string) => m.get(v) ?? v
})

onMounted(load)
</script>

<template>
  <section class="max-w-5xl mx-auto">
    <div class="flex items-center gap-3 mb-4">
      <h1 class="text-xl font-semibold">黑名单</h1>
      <span class="text-soft text-sm">{{ rules.length }} 条规则</span>
    </div>

    <div class="glass p-4 mb-5">
      <h2 class="font-medium mb-3">新增规则</h2>
      <div class="flex flex-wrap gap-2">
        <select v-model="form.kind" class="glass-soft px-2 py-1.5 text-sm">
          <option v-for="k in kinds" :key="k.value" :value="k.value">{{ k.label }}</option>
        </select>
        <input v-model="form.value" :placeholder="currentHint || '规则值'" class="glass-soft px-3 py-1.5 text-sm outline-none flex-1 min-w-[14rem]" />
        <input v-model="form.note" placeholder="备注（可选）" class="glass-soft px-3 py-1.5 text-sm outline-none w-44" />
        <button class="btn-primary" @click="add">添加</button>
      </div>
      <p v-if="currentHint" class="text-xs text-soft mt-2">提示：{{ currentHint }}</p>
    </div>

    <EmptyState v-if="error" tone="err" title="加载失败" :hint="error" />

    <ul v-else-if="rules.length > 0" class="flex flex-col gap-2 mb-6">
      <li v-for="r in rules" :key="r.id" class="glass-soft p-3 flex items-center gap-3 flex-wrap">
        <button class="btn-ghost text-xs whitespace-nowrap" @click="toggle(r)">
          <span class="dot" :class="r.enabled ? 'dot-ok' : 'dot-err'"></span>
          {{ r.enabled ? '启用' : '停用' }}
        </button>
        <span class="text-xs px-2 py-0.5 rounded glass-soft min-w-[7rem] text-center whitespace-nowrap">{{ kindLabel(r.kind) }}</span>
        <code class="font-mono text-sm flex-1 break-all">{{ r.value }}</code>
        <span v-if="r.note" class="text-xs text-soft hidden md:inline truncate max-w-[10rem]">{{ r.note }}</span>
        <span class="text-xs text-soft tabular-nums whitespace-nowrap">命中 {{ r.hit_count }}</span>
        <button class="btn whitespace-nowrap" @click="del(r)">删除</button>
      </li>
    </ul>

    <EmptyState
      v-else
      title="还没有规则"
      hint="添加一条试试。规则在&quot;同步动态&quot;时生效，命中规则的视频会进入&quot;已过滤&quot;页面。"
    />

    <div class="glass p-4 mt-6">
      <div class="flex items-center gap-3 mb-3 flex-wrap">
        <h2 class="font-medium">AI 建议规则</h2>
        <span class="text-xs text-soft">基于你最近 30 天的过滤/移除信号自动提议</span>
        <button class="btn-primary ml-auto" :disabled="aiLoading" @click="runAiSuggest">{{ aiLoading ? '思考中…' : '让 AI 看看' }}</button>
      </div>
      <p v-if="aiNote" class="text-soft text-sm">{{ aiNote }}</p>
      <ul v-if="aiSuggestions && aiSuggestions.length > 0" class="flex flex-col gap-2">
        <li
          v-for="s in aiSuggestions"
          :key="s.kind + ':' + s.value"
          class="glass-soft p-3 flex items-center gap-3 flex-wrap"
        >
          <span class="text-xs px-2 py-0.5 rounded glass-soft min-w-[7rem] text-center whitespace-nowrap">{{ kindLabel(s.kind) }}</span>
          <code class="font-mono text-sm">{{ s.value }}</code>
          <span class="text-xs text-soft flex-1 truncate">{{ s.reason }}</span>
          <button class="btn text-xs whitespace-nowrap" @click="rejectSuggestion(s)">忽略</button>
          <button class="btn-primary text-xs whitespace-nowrap" @click="acceptSuggestion(s)">接受</button>
        </li>
      </ul>
    </div>

    <div class="glass p-4 mt-6">
      <div class="flex items-center gap-3 mb-3 flex-wrap">
        <h2 class="font-medium">试运行 (Dry Run)</h2>
        <span class="text-xs text-soft">不修改数据，只显示当前规则会过滤掉哪些视频</span>
        <select v-model="dryRunDays" class="glass-soft px-2 py-1 text-sm ml-auto">
          <option :value="7">最近 7 天</option>
          <option :value="14">最近 14 天</option>
          <option :value="30">最近 30 天</option>
        </select>
        <button class="btn-primary" :disabled="dryRunLoading" @click="runDry">{{ dryRunLoading ? '运行中…' : '运行' }}</button>
      </div>
      <div v-if="dryRun" class="text-sm text-soft mb-3">
        共 {{ dryRun.tested }} 个视频，其中 <strong class="text-current">{{ dryRun.would_filter }}</strong> 个会被过滤
      </div>
      <div v-if="dryRun && dryRun.items.length > 0" class="flex flex-col gap-2">
        <VideoListItem
          v-for="hit in dryRun.items"
          :key="hit.bvid"
          :bvid="hit.bvid"
          :title="hit.title"
          :cover="hit.cover"
          :duration="hit.duration"
          :pubdate="hit.pubdate"
          :owner-mid="hit.owner_mid"
          :owner-name="hit.owner_name"
          :reason="`${kindLabel(hit.matched_rule.kind)}: ${hit.matched_rule.value}`"
        />
      </div>
    </div>
  </section>
</template>
