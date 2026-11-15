import type { Answer, Question, RequestStatus, RequestSummary } from '@/types/api'
import { statusTone } from '@/lib/format'

export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

export function clamp01(value: number): number {
  return clamp(value, 0, 1)
}

export function roundTo(value: number, digits = 2): number {
  const factor = 10 ** digits
  return Math.round((value + Number.EPSILON) * factor) / factor
}

export function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

export function isActiveStatus(status: RequestStatus | string | null | undefined): boolean {
  return status === 'queued' || status === 'assigned'
}

export function statusBadgeClass(status: string): string {
  const tone = statusTone(status)
  return tone === 'neutral' ? '' : `badge-${tone}`
}

export function questionTypeBadge(type: string): string {
  if (type === 'noul') return 'badge-blue'
  if (type === 'choice') return 'badge-lime'
  if (type === 'score') return 'badge-amber'
  return ''
}

export function questionTypeLabel(type: string): string {
  if (type === 'noul') return 'Noul'
  if (type === 'choice') return 'Choice'
  if (type === 'score') return 'Score'
  return type
}

export function protocolLabel(protocol: string | null | undefined): string {
  if (protocol === 'systemone') return 'System One'
  if (protocol === 'google') return 'Gemini Decisions'
  if (protocol === 'both') return 'Both protocols'
  return protocol || '—'
}

export function protocolShort(protocol: string | null | undefined): string {
  if (protocol === 'systemone') return 'System One'
  if (protocol === 'google') return 'Gemini'
  if (protocol === 'both') return 'Both'
  return String(protocol ?? '—')
}

export function shortId(id: string | null | undefined, length = 8): string {
  if (!id) return '—'
  return id.length <= length ? id : id.slice(-length)
}

export function formatClock(ms: number | null | undefined): string {
  if (ms === null || ms === undefined || !Number.isFinite(ms)) return '—'
  const total = Math.max(0, Math.ceil(ms / 1000))
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const seconds = total % 60
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
  }
  return `${minutes}:${String(seconds).padStart(2, '0')}`
}

export function formatAge(ms: number | null | undefined): string {
  if (ms === null || ms === undefined || !Number.isFinite(ms)) return '—'
  const total = Math.max(0, Math.floor(ms / 1000))
  if (total < 60) return `${total}s`
  const minutes = Math.floor(total / 60)
  if (minutes < 60) return `${minutes}m`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h`
  return `${Math.floor(hours / 24)}d`
}

export function toDisplayText(value: unknown): string {
  if (value === null || value === undefined) return ''
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean' || typeof value === 'bigint') return String(value)
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

export function rawJson(value: unknown): string {
  if (typeof value === 'string') return value
  try {
    return JSON.stringify(value, null, 2) ?? ''
  } catch {
    return String(value)
  }
}

export function instructionsOf(question: Question): string {
  const displayed = question.display?.instructions
  if (typeof displayed === 'string' && displayed.trim()) return displayed
  return toDisplayText(question.instructions)
}

export interface CriteriaOption {
  key: string
  label: string
  description: string
}

export function criteriaOf(question: Question): CriteriaOption[] {
  const displayed = question.display?.criteria
  if (Array.isArray(displayed) && displayed.length) {
    return displayed.map((item) => ({
      key: String(item.key),
      label: String(item.label ?? item.key),
      description: String(item.description ?? ''),
    }))
  }
  const raw = question.criteria
  if (question.type === 'choice' && isPlainObject(raw)) {
    return Object.entries(raw).map(([key, value]) => ({ key, label: key, description: toDisplayText(value) }))
  }
  if (question.type === 'score' && Array.isArray(raw)) {
    return raw.map((value, index) => ({ key: String(index), label: `Level ${index}`, description: toDisplayText(value) }))
  }
  if (question.type === 'noul' && isPlainObject(raw)) {
    return Object.entries(raw).map(([key, value]) => ({
      key,
      label: key === 'true' ? 'True' : key === 'false' ? 'False' : key,
      description: toDisplayText(value),
    }))
  }
  return []
}

export function optionLabel(question: Question, key: string): string {
  const option = criteriaOf(question).find((item) => item.key === key)
  if (!option) return key
  return option.description.trim() ? option.description : option.label
}

export function optionKeys(question: Question): string[] {
  return criteriaOf(question).map((item) => item.key)
}

export function probabilitySum(probabilities: Record<string, number> | null | undefined): number {
  if (!probabilities) return 0
  return Object.values(probabilities).reduce((total, value) => {
    const numeric = Number(value)
    return total + (Number.isFinite(numeric) ? numeric : 0)
  }, 0)
}

export function normalizedProbabilities(probabilities: Record<string, number> | null | undefined): Record<string, number> {
  if (!probabilities) return {}
  const keys = Object.keys(probabilities)
  if (!keys.length) return {}
  const clean: Record<string, number> = {}
  let total = 0
  for (const key of keys) {
    const raw = Number(probabilities[key])
    const safe = Number.isFinite(raw) ? clamp01(raw) : 0
    clean[key] = safe
    total += safe
  }
  if (total <= 0) {
    const equal = 1 / keys.length
    for (const key of keys) clean[key] = equal
    return clean
  }
  for (const key of keys) clean[key] = clean[key] / total
  return clean
}

export function maxProbabilityKey(probabilities: Record<string, number>): string {
  let winner = ''
  let max = -1
  for (const [key, value] of Object.entries(probabilities)) {
    if (value > max) {
      max = value
      winner = key
    }
  }
  return winner
}

export function expectedScore(probabilities: Record<string, number> | null | undefined): number {
  if (!probabilities) return 0
  const normalized = normalizedProbabilities(probabilities)
  let score = 0
  for (const [key, value] of Object.entries(normalized)) {
    const level = Number(key)
    if (Number.isFinite(level)) score += level * value
  }
  return score
}

export function answerConfidence(answer: Answer | null | undefined): number | null {
  if (!answer) return null
  if (answer.type === 'noul') {
    if (typeof answer.confidence === 'number' && Number.isFinite(answer.confidence)) return answer.confidence
    return Math.max(answer.noul, 1 - answer.noul)
  }
  if (typeof answer.confidence === 'number' && Number.isFinite(answer.confidence)) return answer.confidence
  const values = Object.values(answer.probabilities || {}).filter((value) => Number.isFinite(value))
  return values.length ? Math.max(...values) : null
}

export function answerProbabilityMap(question: Question, answer: Answer | null | undefined): Record<string, number> {
  if (!answer) return {}
  if (answer.type === 'noul') {
    return { true: answer.noul, false: 1 - answer.noul }
  }
  if (answer.type === 'choice') {
    return normalizedProbabilities(answer.probabilities)
  }
  const keys = optionKeys(question)
  const source = answer.probabilities || {}
  const result: Record<string, number> = {}
  for (const key of keys) result[key] = source[key] ?? 0
  return normalizedProbabilities(result)
}

export function answerHasValue(answer: Answer | null | undefined): boolean {
  if (!answer) return false
  if (answer.type === 'noul') return Number.isFinite(answer.noul)
  if (answer.type === 'choice') return typeof answer.choice === 'string'
  if (answer.type === 'score') return Number.isFinite(answer.score)
  return false
}

export function cloneAnswerMap<T>(value: T): T {
  try {
    return JSON.parse(JSON.stringify(value)) as T
  } catch {
    return value
  }
}

export function sortActiveRequests(requests: RequestSummary[]): RequestSummary[] {
  return requests
    .filter((request) => isActiveStatus(request.status))
    .slice()
    .sort((a, b) => a.created_at - b.created_at)
}

export function initials(name: string | null | undefined): string {
  if (!name) return '?'
  const words = name.trim().split(/\s+/).filter(Boolean)
  if (!words.length) return '?'
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase()
  return `${words[0][0]}${words[words.length - 1][0]}`.toUpperCase()
}

export function mediaUri(block: Record<string, unknown>): string | null {
  for (const key of ['uri', 'file_uri', 'url', 'data']) {
    const value = block[key]
    if (typeof value === 'string' && value.trim()) return value.trim()
  }
  return null
}

export function blockText(block: Record<string, unknown>): string | null {
  const text = block['text']
  return typeof text === 'string' ? text : null
}

export function isHttpOrDataUrl(value: string): boolean {
  return value.startsWith('http://') || value.startsWith('https://') || value.startsWith('data:')
}

export function blockMime(block: Record<string, unknown>): string {
  for (const key of ['mime_type', 'mimeType', 'mime']) {
    const value = block[key]
    if (typeof value === 'string' && value) return value
  }
  return ''
}

export function blockName(block: Record<string, unknown>): string {
  for (const key of ['name', 'filename', 'file_name', 'title']) {
    const value = block[key]
    if (typeof value === 'string' && value) return value
  }
  return ''
}

export function formatProbability(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—'
  return `${(value * 100).toFixed(digits)}%`
}

export function errorMessage(error: unknown, fallback = 'Something went wrong'): string {
  if (error instanceof Error && error.message) return error.message
  if (typeof error === 'string' && error) return error
  return fallback
}

export const DRAFT_LABELS: Record<string, string> = {
  clean: 'Autosave ready',
  dirty: 'Unsaved changes',
  saving: 'Saving…',
  saved: 'Saved',
  error: 'Save failed',
}
