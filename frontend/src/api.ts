export interface Health {
  ok: boolean
  version: string
}

export interface StatusInfo {
  logged_in: boolean
  mid: number | null
  uname: string
  vip_status: number
  cookie_present: boolean
}

export interface VideoLite {
  bvid: string
  aid: number | null
  title: string
  cover: string
  duration: number
  pubdate: number
  owner_mid: number | null
  owner_name: string
  partition_name?: string
  desc?: string
}

export interface WatchLaterItem extends VideoLite {
  progress: number
  add_at: number
  stat_play?: number
  stat_like?: number
  stat_coin?: number
  stat_favorite?: number
  stat_share?: number
  stat_danmaku?: number
  stat_reply?: number
}

export interface FilteredItem extends VideoLite {
  reason: string
  filtered_at: string
}

export interface IngestSummary {
  fetched: number
  new: number
  filtered: number
  pages: number
  cutoff_pubdate: number
}

export interface BlacklistRule {
  id: number
  kind: string
  value: string
  note: string
  enabled: boolean
  hit_count: number
  created_at: string | null
}

export interface BlacklistKind {
  value: string
  label: string
  hint?: string
}

export interface DryRunHit {
  bvid: string
  title: string
  cover: string
  duration: number
  pubdate: number
  owner_mid: number | null
  owner_name: string
  matched_rule: { id: number; kind: string; value: string; reason: string }
}

const base = '/api'

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail: unknown = res.statusText
    try {
      detail = (await res.json()).detail ?? detail
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  return res.json() as Promise<T>
}

export const api = {
  health: () => fetch(`${base}/health`).then((r) => jsonOrThrow<Health>(r)),
  status: () => fetch(`${base}/status`).then((r) => jsonOrThrow<StatusInfo>(r)),

  watchlater: () =>
    fetch(`${base}/watchlater`).then((r) =>
      jsonOrThrow<{ count: number; items: WatchLaterItem[] }>(r),
    ),
  watchlaterAdd: (bvid: string) =>
    fetch(`${base}/watchlater/add?bvid=${encodeURIComponent(bvid)}`, { method: 'POST' }).then((r) =>
      jsonOrThrow<{ code: number; message?: string }>(r),
    ),
  watchlaterRemove: (aid: number) =>
    fetch(`${base}/watchlater/remove?aid=${aid}`, { method: 'POST' }).then((r) =>
      jsonOrThrow<unknown>(r),
    ),
  pendingSkip: (bvid: string) =>
    fetch(`${base}/videos/pending/${encodeURIComponent(bvid)}/skip`, { method: 'POST' }).then((r) =>
      jsonOrThrow<{ ok: boolean }>(r),
    ),
  watchlaterRemoveViewed: () =>
    fetch(`${base}/watchlater/remove?viewed=true`, { method: 'POST' }).then((r) =>
      jsonOrThrow<unknown>(r),
    ),
  watchlaterClear: () =>
    fetch(`${base}/watchlater/clear`, { method: 'POST' }).then((r) => jsonOrThrow<unknown>(r)),

  syncStatus: () =>
    fetch(`${base}/videos/sync-status`).then((r) =>
      jsonOrThrow<{ has_last_sync: boolean; last_sync_at: number | null }>(r),
    ),
  syncDynamic: (days?: number) =>
    fetch(`${base}/videos/sync${days ? `?days=${days}` : ''}`, { method: 'POST' }).then((r) =>
      jsonOrThrow<IngestSummary>(r),
    ),
  autoAdd: (days?: number) =>
    fetch(`${base}/videos/auto-add${days ? `?days=${days}` : ''}`, { method: 'POST' }).then((r) =>
      jsonOrThrow<{
        sync: IngestSummary
        add: { added: string[]; skipped: unknown[]; errors: unknown[] }
      }>(r),
    ),
  pending: (days = 30) =>
    fetch(`${base}/videos/pending?days=${days}`).then((r) =>
      jsonOrThrow<{ count: number; items: VideoLite[] }>(r),
    ),
  recent: (days = 7) =>
    fetch(`${base}/videos/recent?days=${days}`).then((r) =>
      jsonOrThrow<{ count: number; items: VideoLite[] }>(r),
    ),
  filtered: (days = 30) =>
    fetch(`${base}/videos/filtered?days=${days}`).then((r) =>
      jsonOrThrow<{ count: number; items: FilteredItem[] }>(r),
    ),

  blacklistList: () =>
    fetch(`${base}/blacklist`).then((r) =>
      jsonOrThrow<{ count: number; items: BlacklistRule[] }>(r),
    ),
  blacklistKinds: () =>
    fetch(`${base}/blacklist/kinds`).then((r) =>
      jsonOrThrow<{ kinds: BlacklistKind[] }>(r),
    ),
  blacklistCreate: (kind: string, value: string, note = '') =>
    fetch(`${base}/blacklist`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ kind, value, note, enabled: true }),
    }).then((r) => jsonOrThrow<BlacklistRule>(r)),
  blacklistPatch: (id: number, patch: Partial<BlacklistRule>) =>
    fetch(`${base}/blacklist/${id}`, {
      method: 'PATCH',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(patch),
    }).then((r) => jsonOrThrow<BlacklistRule>(r)),
  blacklistDelete: (id: number) =>
    fetch(`${base}/blacklist/${id}`, { method: 'DELETE' }).then((r) =>
      jsonOrThrow<unknown>(r),
    ),
  blacklistDryRun: (days = 7) =>
    fetch(`${base}/blacklist/dry-run?days=${days}`, { method: 'POST' }).then((r) =>
      jsonOrThrow<{ tested: number; would_filter: number; items: DryRunHit[] }>(r),
    ),

  loginStart: () =>
    fetch(`${base}/login/qrcode/start`, { method: 'POST' }).then((r) =>
      jsonOrThrow<{ qrcode_key: string; qr_data_uri: string; expires_in: number }>(r),
    ),
  loginPoll: (qrcode_key: string) =>
    fetch(`${base}/login/qrcode/poll?qrcode_key=${encodeURIComponent(qrcode_key)}`).then((r) =>
      jsonOrThrow<{
        status: 'pending' | 'scanned' | 'expired' | 'ok' | 'error'
        message: string
        uname?: string
        mid?: string
      }>(r),
    ),
  logout: () =>
    fetch(`${base}/login/logout`, { method: 'POST' }).then((r) =>
      jsonOrThrow<{ ok: boolean; deactivated: number }>(r),
    ),

  settingsAll: () =>
    fetch(`${base}/settings/all`).then((r) =>
      jsonOrThrow<{ items: Record<string, string> }>(r),
    ),
  settingsPut: (key: string, value: string) =>
    fetch(`${base}/settings/${encodeURIComponent(key)}`, {
      method: 'PUT',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ value }),
    }).then((r) => jsonOrThrow<{ key: string; value: string }>(r)),

  watchlaterRemoveByBvid: (bvid: string, aid: number) =>
    fetch(`${base}/watchlater/remove?aid=${aid}&bvid=${encodeURIComponent(bvid)}`, {
      method: 'POST',
    }).then((r) => jsonOrThrow<unknown>(r)),

  predictWatchlater: () =>
    fetch(`${base}/predict/watchlater`).then((r) => jsonOrThrow<PredictWatchlater>(r)),

  aiSummary: (bvid: string, refresh = false) =>
    fetch(`${base}/ai/summary/${encodeURIComponent(bvid)}${refresh ? '?refresh=true' : ''}`).then((r) =>
      jsonOrThrow<{
        source: 'bilibili' | 'llm' | 'cache'
        summary: string
        outline: { title?: string; timestamp?: number }[]
        title: string
        cached_at?: number
      }>(r),
    ),
  blacklistSuggest: (days = 30) =>
    fetch(`${base}/ai/blacklist/suggest?days=${days}`, { method: 'POST' }).then((r) =>
      jsonOrThrow<{
        suggestions: { kind: string; value: string; reason: string }[]
        note?: string
        error?: string
        raw?: string
      }>(r),
    ),

  llmStatus: () =>
    fetch(`${base}/ai/llm/status`).then((r) =>
      jsonOrThrow<{
        configured: boolean
        active_slot: number
        slots: { base_url: string; model_id: string; api_key: string; api_key_set: boolean }[]
      }>(r),
    ),
  llmTest: (cfg: { base_url: string; model_id: string; api_key: string }) =>
    fetch(`${base}/ai/llm/test`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(cfg),
    }).then((r) =>
      jsonOrThrow<{ ok: boolean; reply?: string; error?: string; normalized_base_url?: string }>(r),
    ),
  llmActivateSlot: (idx: number) =>
    fetch(`${base}/ai/llm/slots/${idx}/activate`, { method: 'POST' }).then((r) =>
      jsonOrThrow<{ active_slot: number; configured: boolean }>(r),
    ),
  llmSaveSlot: (
    idx: number,
    payload: { base_url: string; model_id: string; api_key: string | null },
  ) =>
    fetch(`${base}/ai/llm/slots/${idx}`, {
      method: 'PUT',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(payload),
    }).then((r) =>
      jsonOrThrow<{
        active_slot: number
        slot: { base_url: string; model_id: string; api_key: string; api_key_set: boolean }
      }>(r),
    ),
}

export interface PredictWatchlater {
  count: number
  raw_total_seconds: number
  remaining_total_seconds: number
  raw_total_pretty: string
  remaining_total_pretty: string
  short_videos: number
  long_videos: number
  top_owners_by_time: { name: string; seconds: number; pretty: string }[]
}

export function fmtDuration(secs: number): string {
  if (!secs) return '--:--'
  const h = Math.floor(secs / 3600)
  const m = Math.floor((secs % 3600) / 60)
  const s = secs % 60
  if (h > 0) return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
  return `${m}:${s.toString().padStart(2, '0')}`
}

export function fmtCount(n: number | undefined | null): string {
  const v = Math.max(0, Math.floor(n ?? 0))
  if (v < 10000) return v.toString()
  if (v < 100_000_000) {
    const k = v / 10000
    return k >= 100 ? `${Math.round(k)}万` : `${k.toFixed(1).replace(/\.0$/, '')}万`
  }
  const y = v / 100_000_000
  return `${y.toFixed(2).replace(/\.0+$/, '')}亿`
}

export function fmtRelativeTime(ts: number, nowMs?: number): string {
  if (!ts) return ''
  const reference = nowMs ?? Date.now()
  const diffSec = Math.floor(reference / 1000) - ts
  if (diffSec < 60) return '刚刚'
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)} 分钟前`
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)} 小时前`
  if (diffSec < 86400 * 7) return `${Math.floor(diffSec / 86400)} 天前`
  return new Date(ts * 1000).toLocaleDateString('zh-CN')
}

export function biliVideoUrl(bvid: string): string {
  return `https://www.bilibili.com/video/${bvid}/`
}

export function biliSpaceUrl(mid: number | null): string {
  return mid ? `https://space.bilibili.com/${mid}/` : '#'
}

const isMobile = () => /Mobile|Android|iP(hone|od|ad)/.test(navigator.userAgent)

// 移动端：先试 bilibili:// scheme 跳 App，1.2s 内没离开就 fallback 到网页
// 桌面端：不拦截，让 <a target="_blank"> 默认行为开新 tab
export function handleVideoClick(bvid: string, e: MouseEvent): void {
  // 修饰键（cmd/ctrl/shift/alt）或中键 → 走默认（新标签页等）
  if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return
  if (!isMobile()) return
  e.preventDefault()
  const web = biliVideoUrl(bvid)
  const app = `bilibili://video/${bvid}`
  const t = window.setTimeout(() => { window.location.href = web }, 1200)
  window.addEventListener('pagehide', () => clearTimeout(t), { once: true })
  window.location.href = app
}
