/**
 * Presentation helpers shared by the public site and the user console.
 *
 * The management API reports validation failures in the deployment's internal
 * language. The provider site is English-only, so known messages are mapped to
 * their public wording here and anything unknown falls back to a status-based
 * sentence. Nothing in this file is protocol logic.
 */
import { toast } from '@/lib/toast'

interface MappedMessage {
  match: string
  text: string
  prefix?: boolean
}

const KNOWN_MESSAGES: MappedMessage[] = [
  { match: '邮箱或密码不正确', text: 'Email or password is incorrect.' },
  { match: '登录尝试过于频繁', text: 'Too many sign-in attempts. Try again shortly.' },
  { match: '操作过于频繁', text: 'Too many requests. Try again shortly.' },
  { match: '当前未开放注册', text: 'Registration is currently closed.' },
  { match: '该邮箱已注册', text: 'An account with this email already exists.' },
  { match: '密码至少需要 10 个字符', text: 'Password must be at least 10 characters.' },
  { match: '密码过长', text: 'That password is too long.' },
  { match: '密码首尾不能包含空白字符', text: 'The password cannot start or end with a space.' },
  { match: '请输入有效的邮箱地址', text: 'Enter a valid email address.' },
  { match: '请输入名称', text: 'Enter a name.' },
  { match: '当前密码不正确', text: 'Current password is incorrect.' },
  { match: '模型不存在或不可用', text: 'That model is not available.', prefix: true },
  { match: '该模型不支持所选协议', text: 'That model does not support the selected protocol.' },
  { match: '该模型不支持当前接口协议', text: 'That model does not support the selected protocol.' },
  { match: '当前排队请求过多', text: 'Too many pending requests. Try again shortly.' },
  { match: '请求超时，未获得回答', text: 'The request timed out before an answer was returned.' },
  { match: '请求已被取消', text: 'The request was cancelled.' },
  { match: '请求不存在', text: 'That request no longer exists.' },
  { match: '最多保留 12 个有效 API Key', text: 'You can keep up to 12 active API keys.' },
  { match: 'API Key 不存在', text: 'That API key was not found.' },
  { match: '账号已被停用', text: 'This account is disabled.' },
  { match: '请求体过大', text: 'That request is too large.' },
  { match: '请求过于频繁', text: 'Too many requests. Try again shortly.' },
]

const STATUS_FALLBACKS: Record<number, string> = {
  400: 'The request was rejected. Check the payload and try again.',
  401: 'Your session has expired. Sign in again.',
  403: 'You do not have access to that.',
  404: 'That resource was not found.',
  409: 'That change conflicts with existing data.',
  413: 'That request is too large.',
  422: 'Some of the values are not valid.',
  429: 'Too many requests. Try again shortly.',
  500: 'The service hit an unexpected error.',
  502: 'The service is temporarily unreachable.',
  503: 'The service is temporarily unavailable.',
  504: 'The request timed out.',
}

function statusOf(error: unknown): number | null {
  if (error && typeof error === 'object' && 'status' in error) {
    const value = (error as { status: unknown }).status
    if (typeof value === 'number') return value
  }
  return null
}

function codeOf(error: unknown): string | undefined {
  if (error && typeof error === 'object' && 'code' in error) {
    const value = (error as { code: unknown }).code
    if (typeof value === 'string' && value.trim()) return value
  }
  return undefined
}

function rawMessage(error: unknown): string {
  if (error instanceof Error && error.message) return error.message
  if (typeof error === 'string') return error
  return ''
}

/** Public English wording for an API failure. */
export function errorMessage(error: unknown, fallback: string): string {
  const raw = rawMessage(error)
  if (raw) {
    for (const entry of KNOWN_MESSAGES) {
      const hit = entry.prefix ? raw.startsWith(entry.match) : raw === entry.match
      if (hit) return entry.text
    }
    // Server text that is already Latin (e.g. a protocol error) is safe to show.
    if (/^[\x20-\x7E]+$/.test(raw)) return raw
  }
  const status = statusOf(error)
  if (status && STATUS_FALLBACKS[status]) return STATUS_FALLBACKS[status]
  return fallback
}

/** Toast an API failure and return the message that was shown. */
export function reportError(error: unknown, fallback: string): string {
  const message = errorMessage(error, fallback)
  const code = codeOf(error)
  toast(message, 'error', code ? { detail: code } : {})
  return message
}

/**
 * Only same-origin absolute paths are acceptable redirect targets. Protocol
 * relative (`//host`) and path-traversal attempts fall back to the console.
 */
export function safeNextPath(value: unknown): string {
  if (typeof value !== 'string') return '/console'
  const raw = value.trim()
  if (!raw.startsWith('/')) return '/console'
  if (raw.startsWith('//') || raw.includes('\\')) return '/console'
  if (raw.startsWith('/admin')) return '/console'
  return raw
}

export function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

export function prettyJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2) ?? ''
  } catch {
    return String(value)
  }
}

const JSON_TOKEN =
  /("(?:\\u[a-fA-F0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(?:true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)/g

/**
 * Tokenise JSON into escaped HTML spans. The input is always our own
 * `JSON.stringify` output, and every fragment is escaped before it is wrapped,
 * so it is safe to inject with v-html.
 */
export function highlightJson(json: string): string {
  let out = ''
  let last = 0
  for (const match of json.matchAll(JSON_TOKEN)) {
    const index = match.index ?? 0
    const token = match[0]
    out += escapeHtml(json.slice(last, index))
    let cls = 'console-json-number'
    if (token.startsWith('"')) cls = match[2] ? 'console-json-key' : 'console-json-string'
    else if (token === 'true' || token === 'false') cls = 'console-json-boolean'
    else if (token === 'null') cls = 'console-json-null'
    out += `<span class="${cls}">${escapeHtml(token)}</span>`
    last = index + token.length
  }
  out += escapeHtml(json.slice(last))
  return out
}

/** Single-quote a shell argument, including embedded single quotes. */
export function shellQuote(value: string): string {
  return `'${value.split("'").join(`'\\''`)}'`
}

/**
 * Wrap JSON in a Python raw triple-quoted literal. Valid pretty-printed JSON
 * never contains three adjacent double quotes, so the literal stays closed,
 * while `\n` and `\"` sequences survive because the string is raw.
 */
export function pythonRaw(value: string): string {
  return `r"""${value}"""`
}

export function truncateId(id: string, length = 8): string {
  return id.length > length ? id.slice(0, length) : id
}
