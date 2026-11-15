import { reactive } from 'vue'

export type ToastTone = 'info' | 'success' | 'warning' | 'error'

export interface ToastItem {
  id: number
  message: string
  tone: ToastTone
  detail?: string
}

let nextId = 1
export const toastState = reactive<{ items: ToastItem[] }>({ items: [] })

export function toast(message: string, tone: ToastTone = 'info', options: { timeout?: number; detail?: string } = {}) {
  const item: ToastItem = { id: nextId++, message, tone, detail: options.detail }
  toastState.items.push(item)
  const timeout = options.timeout ?? (tone === 'error' ? 6200 : 3600)
  window.setTimeout(() => dismissToast(item.id), timeout)
  return item.id
}

export function dismissToast(id: number) {
  const index = toastState.items.findIndex((item) => item.id === id)
  if (index >= 0) toastState.items.splice(index, 1)
}
