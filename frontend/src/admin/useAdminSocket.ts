import { reactive, ref } from 'vue'
import type { Ref } from 'vue'
import type { AdminUser, OperatorSummary, RequestSummary, WsEvent, WsHello } from '@/types/api'
import { toast } from '@/lib/toast'
import { truncate } from '@/lib/format'
import { isActiveStatus, sortActiveRequests } from './utils'

export type AudioState = 'idle' | 'running' | 'suspended' | 'unsupported'
export type SocketListener = (event: WsEvent) => void
type RequestEvent = Extract<
  WsEvent,
  { type: 'request.created' | 'request.assigned' | 'request.updated' | 'request.completed' }
>

const SOUND_KEY = 'fd-admin-sound'

interface AdminSocketState {
  connected: boolean
  connecting: boolean
  attempts: number
  lastError: string
  hello: WsHello | null
  helloAt: number
  admin: AdminUser | null
  pending: RequestSummary[]
  presence: OperatorSummary[]
  settings: WsHello['settings'] | null
  serverOffset: number
  lastEventAt: number
  eventSeq: number
}

const state = reactive<AdminSocketState>({
  connected: false,
  connecting: false,
  attempts: 0,
  lastError: '',
  hello: null,
  helloAt: 0,
  admin: null,
  pending: [],
  presence: [],
  settings: null,
  serverOffset: 0,
  lastEventAt: 0,
  eventSeq: 0,
})

let soundPreferenceStored = false

function readSoundPreference(): boolean {
  try {
    const stored = window.localStorage.getItem(SOUND_KEY)
    if (stored === '0' || stored === 'false') {
      soundPreferenceStored = true
      return false
    }
    if (stored === '1' || stored === 'true') {
      soundPreferenceStored = true
      return true
    }
  } catch {
    /* storage may be unavailable */
  }
  return true
}

function detectAudioSupport(): AudioState {
  if (typeof window === 'undefined') return 'unsupported'
  const has = 'AudioContext' in window || 'webkitAudioContext' in window
  return has ? 'idle' : 'unsupported'
}

const soundEnabled = ref(readSoundPreference())
const audioState = ref<AudioState>(detectAudioSupport())

let socket: WebSocket | null = null
let reconnectTimer: number | null = null
let reconnectAttempts = 0
let manualClose = false
let onlineInstalled = false
let gestureInstalled = false
let hasGesture = false
let audioContext: AudioContext | null = null
const listeners = new Set<SocketListener>()

function reportAudioState(context: AudioContext) {
  if (context.state === 'running') audioState.value = 'running'
  else if (context.state === 'suspended') audioState.value = 'suspended'
  else audioState.value = 'unsupported'
}

function ensureAudioContext(): AudioContext | null {
  if (audioContext) return audioContext
  if (typeof window === 'undefined') {
    audioState.value = 'unsupported'
    return null
  }
  const Ctor =
    window.AudioContext ||
    (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
  if (!Ctor) {
    audioState.value = 'unsupported'
    return null
  }
  try {
    audioContext = new Ctor()
    reportAudioState(audioContext)
    return audioContext
  } catch {
    audioState.value = 'unsupported'
    return null
  }
}

export async function unlockAudio(): Promise<boolean> {
  hasGesture = true
  const context = ensureAudioContext()
  if (!context) return false
  if (context.state === 'suspended') {
    try {
      await context.resume()
    } catch {
      /* the browser may still refuse until another gesture */
    }
  }
  reportAudioState(context)
  return context.state === 'running'
}

function playTone(context: AudioContext, frequency: number, duration: number, peak: number, delay = 0) {
  const start = context.currentTime + delay
  const oscillator = context.createOscillator()
  const gain = context.createGain()
  oscillator.type = 'sine'
  oscillator.frequency.setValueAtTime(frequency, start)
  gain.gain.setValueAtTime(0.0001, start)
  gain.gain.exponentialRampToValueAtTime(peak, start + 0.012)
  gain.gain.exponentialRampToValueAtTime(0.0001, start + duration)
  oscillator.connect(gain)
  gain.connect(context.destination)
  oscillator.start(start)
  oscillator.stop(start + duration + 0.03)
}

function playChime() {
  if (!soundEnabled.value) return
  if (!hasGesture && (!audioContext || audioContext.state !== 'running')) return
  const context = ensureAudioContext()
  if (!context) return
  const fire = () => {
    reportAudioState(context)
    playTone(context, 880, 0.32, 0.1)
    playTone(context, 1174.66, 0.36, 0.075, 0.14)
  }
  if (context.state === 'running') {
    fire()
    return
  }
  void context
    .resume()
    .then(() => {
      reportAudioState(context)
      if (context.state === 'running') fire()
    })
    .catch(() => {
      audioState.value = 'suspended'
    })
}

export function setSound(enabled: boolean) {
  soundEnabled.value = enabled
  try {
    window.localStorage.setItem(SOUND_KEY, enabled ? '1' : '0')
  } catch {
    /* ignore */
  }
  if (enabled) void unlockAudio()
}

function installGestureUnlock() {
  if (gestureInstalled || typeof window === 'undefined') return
  gestureInstalled = true
  const handler = () => {
    window.removeEventListener('pointerdown', handler, true)
    window.removeEventListener('keydown', handler, true)
    void unlockAudio()
  }
  window.addEventListener('pointerdown', handler, true)
  window.addEventListener('keydown', handler, true)
}

function wsUrl(): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/api/admin/ws`
}

function notify(event: WsEvent) {
  for (const listener of listeners) {
    try {
      listener(event)
    } catch {
      /* a page listener must never break the socket */
    }
  }
}

function applyRequestEvent(event: RequestEvent) {
  const request = event.data.request
  const index = state.pending.findIndex((item) => item.id === request.id)
  if (isActiveStatus(request.status)) {
    if (index >= 0) state.pending.splice(index, 1, request)
    else state.pending.push(request)
    state.pending = sortActiveRequests(state.pending)
  } else if (index >= 0) {
    state.pending.splice(index, 1)
  }

  state.lastEventAt = Date.now()
  state.eventSeq += 1

  if (event.data.notify) {
    if (event.type === 'request.created' || event.type === 'request.assigned') playChime()
    if (event.type === 'request.created') {
      toast(`New request · ${request.model}`, 'info', {
        detail: truncate(request.input_text || 'No input text', 110),
      })
    } else if (event.type === 'request.assigned') {
      toast(`Request assigned · ${request.model}`, 'info', {
        detail: 'You are the assigned operator.',
      })
    } else if (event.type === 'request.completed') {
      toast(`Request completed · ${request.model}`, 'success')
    }
  }
  notify(event)
}

function handleEvent(event: WsEvent) {
  switch (event.type) {
    case 'hello': {
      const data = event.data
      state.hello = data
      state.helloAt = Date.now()
      state.admin = data.admin
      state.pending = sortActiveRequests(data.pending || [])
      state.presence = data.presence || []
      state.settings = data.settings || null
      if (!soundPreferenceStored && data.settings) {
        soundEnabled.value = Boolean(data.settings.sound_default)
      }
      state.serverOffset = Number(data.server_time || Date.now()) - Date.now()
      state.connected = true
      state.connecting = false
      state.attempts = 0
      state.lastError = ''
      state.lastEventAt = Date.now()
      state.eventSeq += 1
      notify(event)
      return
    }
    case 'request.created':
    case 'request.assigned':
    case 'request.updated':
    case 'request.completed': {
      applyRequestEvent(event)
      return
    }
    case 'presence': {
      state.presence = event.data.operators || []
      state.lastEventAt = Date.now()
      state.eventSeq += 1
      notify(event)
      return
    }
    case 'ping': {
      const time = Number(event.data.time)
      if (Number.isFinite(time)) state.serverOffset = time - Date.now()
      state.lastEventAt = Date.now()
      return
    }
    default:
      return
  }
}

function openSocket() {
  if (typeof window === 'undefined') return
  if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) return
  manualClose = false
  state.connecting = true
  let next: WebSocket
  try {
    next = new WebSocket(wsUrl())
  } catch {
    state.connecting = false
    scheduleReconnect()
    return
  }
  socket = next

  next.onopen = () => {
    if (socket !== next) return
    state.connected = true
    state.connecting = false
    state.attempts = 0
    reconnectAttempts = 0
    state.lastError = ''
  }

  next.onmessage = (message: MessageEvent) => {
    if (socket !== next) return
    if (typeof message.data !== 'string') return
    let parsed: WsEvent
    try {
      parsed = JSON.parse(message.data) as WsEvent
    } catch {
      return
    }
    if (!parsed || typeof parsed !== 'object' || typeof parsed.type !== 'string') return
    handleEvent(parsed)
  }

  next.onerror = () => {
    if (socket !== next) return
    state.lastError = 'Connection error'
  }

  next.onclose = (event: CloseEvent) => {
    if (socket !== next) return
    socket = null
    state.connected = false
    state.connecting = false
    if (manualClose) return
    if (event.code === 4401) {
      state.lastError = 'Admin session expired'
      return
    }
    state.lastError = 'Connection lost'
    scheduleReconnect()
  }
}

function scheduleReconnect() {
  if (reconnectTimer !== null || manualClose) return
  reconnectAttempts += 1
  state.attempts = reconnectAttempts
  const exponent = Math.min(reconnectAttempts - 1, 5)
  const base = Math.min(15000, 600 * 2 ** exponent)
  const jitter = Math.random() * base * 0.25
  reconnectTimer = window.setTimeout(() => {
    reconnectTimer = null
    if (manualClose) return
    openSocket()
  }, Math.round(base + jitter))
}

function installNetworkListener() {
  if (onlineInstalled || typeof window === 'undefined') return
  onlineInstalled = true
  window.addEventListener('online', () => {
    if (manualClose) return
    if (reconnectTimer !== null) {
      window.clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (!state.connected) openSocket()
  })
}

export function connectAdminSocket(): void {
  if (typeof window === 'undefined') return
  installGestureUnlock()
  installNetworkListener()
  if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) return
  if (reconnectTimer !== null) {
    window.clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
  reconnectAttempts = 0
  state.attempts = 0
  openSocket()
}

export function disconnectAdminSocket(): void {
  manualClose = true
  if (reconnectTimer !== null) {
    window.clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
  if (socket) {
    const current = socket
    socket = null
    try {
      current.close(1000, 'leaving admin')
    } catch {
      /* ignore */
    }
  }
  state.connected = false
  state.connecting = false
}

export function resetAdminSocket(): void {
  disconnectAdminSocket()
  state.hello = null
  state.helloAt = 0
  state.admin = null
  state.pending = []
  state.presence = []
  state.settings = null
  state.serverOffset = 0
  state.lastError = ''
  state.attempts = 0
  state.lastEventAt = 0
  state.eventSeq = 0
  reconnectAttempts = 0
}

export function onAdminSocketEvent(listener: SocketListener): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

export function useAdminSocket() {
  return {
    state,
    soundEnabled: soundEnabled as Ref<boolean>,
    audioState: audioState as Ref<AudioState>,
    connect: connectAdminSocket,
    disconnect: disconnectAdminSocket,
    reset: resetAdminSocket,
    onEvent: onAdminSocketEvent,
    setSound,
    unlockAudio,
    now(): number {
      return Date.now() + state.serverOffset
    },
  }
}
