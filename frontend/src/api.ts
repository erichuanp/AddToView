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
  watchlaterRemove: (aid: number) =>
    fetch(`${base}/watchlater/remove?aid=${aid}`, { method: 'POST' }).then((r) =>
      jsonOrThrow<unknown>(r),
    ),
  watchlaterRemoveViewed: () =>
    fetch(`${base}/watchlater/remove?viewed=true`, { method: 'POST' }).then((r) =>
      jsonOrThrow<unknown>(r),
    ),
  watchlaterClear: () =>
    fetch(`${base}/watchlater/clear`, { method: 'POST' }).then((r) => jsonOrThrow<unknown>(r)),

  syncDynamic: (days = 7) =>
    fetch(`${base}/videos/sync?days=${days}`, { method: 'POST' }).then((r) =>
      jsonOrThrow<IngestSummary>(r),
    ),
  autoAdd: (days = 7) =>
    fetch(`${base}/videos/auto-add?days=${days}`, { method: 'POST' }).then((r) =>
      jsonOrThrow<{ added: string[]; skipped: unknown[]; errors: unknown[] }>(r),
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

  statsSummary: (days = 30) =>
    fetch(`${base}/stats/summary?days=${days}`).then((r) =>
      jsonOrThrow<StatsSummary>(r),
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
}

export interface StatsSummary {
  window_days: number
  total_videos_known: number
  by_kind: Record<string, number>
  daily: { date: string; ingested: number; filtered: number; added: number; removed: number; error: number }[]
  top_filtered_owners: { name: string; mid: number | null; count: number }[]
  top_active_rules: { id: number; kind: string; value: string; hits: number; enabled: boolean }[]
}

export function fmtDuration(secs: number): string {
  if (!secs) return '--:--'
  const h = Math.floor(secs / 3600)
  const m = Math.floor((secs % 3600) / 60)
  const s = secs % 60
  if (h > 0) return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
  return `${m}:${s.toString().padStart(2, '0')}`
}

export function fmtRelativeTime(ts: number): string {
  if (!ts) return ''
  const diffSec = Math.floor(Date.now() / 1000) - ts
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
