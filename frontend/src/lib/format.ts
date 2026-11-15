export function formatNumber(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return new Intl.NumberFormat('en-US', { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(value)
}

export function formatCompact(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 }).format(value)
}

export function formatDate(ms: number | null | undefined, withTime = true): string {
  if (!ms) return '—'
  const d = new Date(ms)
  const date = d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
  if (!withTime) return date
  return `${date} · ${d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' })}`
}

export function timeAgo(ms: number | null | undefined): string {
  if (!ms) return 'never'
  const delta = Math.max(0, Date.now() - ms)
  if (delta < 1000) return 'just now'
  const s = Math.floor(delta / 1000)
  if (s < 60) return `${s}s ago`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  const d = Math.floor(h / 24)
  if (d < 30) return `${d}d ago`
  return formatDate(ms, false)
}

export function formatDuration(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return '—'
  if (ms < 1000) return `${Math.round(ms)} ms`
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)} s`
  const m = Math.floor(ms / 60_000)
  const s = Math.round((ms % 60_000) / 1000)
  return `${m}m ${s}s`
}

export function formatCountdown(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return '—'
  const total = Math.max(0, Math.ceil(ms / 1000))
  const m = Math.floor(total / 60)
  const s = total % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

export function formatPercent(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined) return '—'
  return `${(value * 100).toFixed(digits)}%`
}

export function formatTokenWindow(value: number): string {
  if (!value) return '—'
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(value % 1_000_000 ? 1 : 0)}M`
  if (value >= 1_000) return `${Math.round(value / 1_000)}K`
  return String(value)
}

export function truncate(text: string, max = 140): string {
  const cleaned = text.replace(/\s+/g, ' ').trim()
  return cleaned.length > max ? `${cleaned.slice(0, max - 1)}…` : cleaned
}

export function statusLabel(status: string): string {
  return (
    {
      queued: 'Queued',
      assigned: 'Assigned',
      answered: 'Answered',
      timed_out: 'Timed out',
      cancelled: 'Cancelled',
    } as Record<string, string>
  )[status] ?? status
}

export function statusTone(status: string): 'neutral' | 'blue' | 'green' | 'amber' | 'red' {
  if (status === 'answered') return 'green'
  if (status === 'assigned') return 'blue'
  if (status === 'queued') return 'amber'
  if (status === 'timed_out') return 'red'
  return 'neutral'
}

export function truncateId(id: string, length = 10): string {
  if (!id) return '—'
  return id.length > length ? `${id.slice(0, length)}…` : id
}
