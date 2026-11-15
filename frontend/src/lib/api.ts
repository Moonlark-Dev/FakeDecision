export class ApiError extends Error {
  status: number
  code?: string
  payload: unknown

  constructor(message: string, status: number, payload: unknown, code?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.payload = payload
    this.code = code
  }
}

function detailMessage(payload: unknown): string {
  if (!payload || typeof payload !== 'object') return '请求失败'
  const body = payload as { detail?: unknown; message?: unknown; error?: unknown; code?: unknown }
  if (typeof body.detail === 'string') return body.detail
  if (Array.isArray(body.detail)) {
    const messages = body.detail
      .map((entry) => {
        if (entry && typeof entry === 'object' && 'msg' in entry) return String((entry as { msg: unknown }).msg)
        return null
      })
      .filter(Boolean)
    if (messages.length) return messages.join('; ')
  }
  if (typeof body.message === 'string') return body.message
  if (body.error && typeof body.error === 'object' && 'message' in body.error) {
    return String((body.error as { message: unknown }).message)
  }
  if (typeof body.error === 'string') return body.error
  return '请求失败'
}

interface ApiOptions extends Omit<RequestInit, 'body'> {
  body?: unknown
  raw?: boolean
}

export async function api<T>(path: string, options: ApiOptions = {}): Promise<T> {
  const headers = new Headers(options.headers || {})
  headers.set('Accept', 'application/json')
  let body: BodyInit | undefined
  if (options.body !== undefined) {
    if (options.body instanceof FormData || options.body instanceof Blob) {
      body = options.body
    } else {
      headers.set('Content-Type', 'application/json')
      body = JSON.stringify(options.body)
    }
  }
  const response = await fetch(path, {
    ...options,
    headers,
    body,
    credentials: 'include',
  })
  if (!response.ok) {
    let payload: unknown = null
    try {
      payload = await response.json()
    } catch {
      payload = null
    }
    const code =
      payload && typeof payload === 'object' && 'code' in payload && typeof (payload as { code: unknown }).code === 'string'
        ? (payload as { code: string }).code
        : undefined
    throw new ApiError(detailMessage(payload), response.status, payload, code)
  }
  if (response.status === 204) return undefined as T
  if (options.raw) return (await response.text()) as T
  return (await response.json()) as T
}

export const get = <T>(path: string) => api<T>(path)
export const post = <T>(path: string, body?: unknown) => api<T>(path, { method: 'POST', body })
export const put = <T>(path: string, body?: unknown) => api<T>(path, { method: 'PUT', body })
export const patch = <T>(path: string, body?: unknown) => api<T>(path, { method: 'PATCH', body })
export const del = <T>(path: string) => api<T>(path, { method: 'DELETE' })

export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    try {
      const node = document.createElement('textarea')
      node.value = text
      node.style.position = 'fixed'
      node.style.opacity = '0'
      document.body.appendChild(node)
      node.select()
      const ok = document.execCommand('copy')
      document.body.removeChild(node)
      return ok
    } catch {
      return false
    }
  }
}
