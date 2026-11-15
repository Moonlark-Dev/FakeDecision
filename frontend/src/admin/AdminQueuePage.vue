<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import {
  ArrowLeft,
  ArrowRight,
  Ban,
  Check,
  CheckCircle2,
  Clock3,
  Inbox,
  Loader2,
  RefreshCw,
  Send,
  Shuffle,
  TriangleAlert,
  UserRoundCheck,
  Zap,
} from 'lucide-vue-next'
import type {
  AdminUser,
  Answer,
  AnswerMap,
  DecisionRequest,
  RequestDetailResponse,
  RequestList,
  RequestSummary,
  WsEvent,
} from '@/types/api'
import { ApiError, get, post, put } from '@/lib/api'
import { toast } from '@/lib/toast'
import { formatDuration, statusLabel } from '@/lib/format'
import EmptyState from '@/components/EmptyState.vue'
import CopyButton from '@/components/CopyButton.vue'
import CountdownTimer from './components/CountdownTimer.vue'
import ConfirmDialog from './components/ConfirmDialog.vue'
import InputViewer from './components/InputViewer.vue'
import QuestionEditor from './components/QuestionEditor.vue'
import AnswerSummary from './components/AnswerSummary.vue'
import RequestListItem from './components/RequestListItem.vue'
import { useAdminSocket } from './useAdminSocket'
import { useAdminClock } from './useAdminClock'
import { useSession } from '@/lib/session'
import type { AnswerResponse, DraftState, OperatorsResponse, RandomizeResponse } from './types'
import {
  DRAFT_LABELS,
  cloneAnswerMap,
  errorMessage,
  formatAge,
  isActiveStatus,
  protocolLabel,
  sortActiveRequests,
  statusBadgeClass,
} from './utils'

const route = useRoute()
const router = useRouter()
const session = useSession()
const socket = useAdminSocket()
const now = useAdminClock(1000)

const isAdmin = computed(() => session.state.admin?.role === 'admin')

const list = ref<RequestSummary[]>([])
const loading = ref(true)
const listError = ref('')
const detail = ref<DecisionRequest | null>(null)
const detailLoading = ref(false)
const detailError = ref('')
const selectedId = ref<string | null>(null)
const answers = ref<AnswerMap>({})
const draftState = ref<DraftState>('clean')
const submitting = ref(false)
const randomizing = ref<string | 'all' | null>(null)
const operators = ref<AdminUser[]>([])
const cancelOpen = ref(false)
const cancelBusy = ref(false)
const assignBusy = ref(false)
const autoSelect = ref(true)

let off: (() => void) | null = null
let draftTimer: number | null = null
let draftInFlight = false
let detailToken = 0
let expiryTimer: number | null = null

const questions = computed(() => detail.value?.questions ?? [])
const isActive = computed(() => isActiveStatus(detail.value?.status))
const answeredCount = computed(() => questions.value.filter((question) => Boolean(answers.value[question.id])).length)
const allAnswered = computed(
  () => questions.value.length > 0 && answeredCount.value === questions.value.length,
)
const progress = computed(() =>
  questions.value.length ? answeredCount.value / questions.value.length : 0,
)
const age = computed(() => (detail.value ? formatAge(now.value - detail.value.created_at) : '—'))
const assignedName = computed(() => detail.value?.assigned_to?.name || 'Unassigned')
const isMine = computed(
  () => Boolean(detail.value?.assigned_to?.id) && detail.value?.assigned_to?.id === session.state.admin?.id,
)
const draftLabel = computed(() => {
  if (draftState.value === 'clean' && Object.keys(answers.value).length > 0) return 'Saved'
  return DRAFT_LABELS[draftState.value] || 'Draft'
})

const outcomeTitle = computed(() => {
  const request = detail.value
  if (!request) return ''
  if (request.status === 'answered') {
    return request.auto_filled ? 'Auto-filled at the deadline' : `Answered by ${request.answered_by?.name || 'an operator'}`
  }
  if (request.status === 'timed_out') return 'Timed out'
  if (request.status === 'cancelled') return 'Cancelled'
  return statusLabel(request.status)
})
const outcomeDetail = computed(() => {
  const request = detail.value
  if (!request) return ''
  if (request.status === 'answered') {
    if (request.auto_filled) {
      return 'No manual answer was committed before the auto-fill window closed. The system generated the final probabilities from the draft.'
    }
    return `Committed ${formatDuration(request.duration_ms)} after creation · ${request.total_questions} questions.`
  }
  if (request.status === 'timed_out') return 'The request expired without a committed answer.'
  if (request.status === 'cancelled') return 'An administrator cancelled this request.'
  return ''
})
const outcomeTone = computed(() => {
  const request = detail.value
  if (!request) return 'neutral'
  if (request.status === 'answered') return request.auto_filled ? 'amber' : 'green'
  if (request.status === 'timed_out') return 'red'
  if (request.status === 'cancelled') return 'neutral'
  return 'neutral'
})
const outcomeIcon = computed(() => {
  const request = detail.value
  if (!request) return CheckCircle2
  if (request.status === 'answered') return request.auto_filled ? Zap : CheckCircle2
  if (request.status === 'cancelled') return Ban
  return Clock3
})

const assignOptions = computed(() => {
  const rows = operators.value.map((operator) => ({
    id: operator.id,
    name: operator.name,
    online: Boolean(operator.online),
  }))
  const current = detail.value?.assigned_to
  if (current && !rows.some((row) => row.id === current.id)) {
    rows.push({ id: current.id, name: current.name || current.id, online: false })
  }
  return rows
})

function clearDraftTimer() {
  if (draftTimer !== null) {
    window.clearTimeout(draftTimer)
    draftTimer = null
  }
}

function applyAuthoritativeAnswers(request: DecisionRequest) {
  clearDraftTimer()
  draftState.value = 'clean'
  if (isActiveStatus(request.status)) {
    answers.value = { ...(request.draft ?? {}) }
  } else {
    answers.value = request.answers ? { ...request.answers } : {}
  }
}

async function loadList() {
  loading.value = true
  listError.value = ''
  try {
    const response = await get<RequestList>('/api/admin/requests?view=active&limit=100')
    list.value = sortActiveRequests(response.requests)
    ensureSelection()
  } catch (error) {
    listError.value = errorMessage(error, 'Could not load the active queue.')
  } finally {
    loading.value = false
  }
}

async function loadDetail(id: string) {
  const token = ++detailToken
  detailLoading.value = true
  detailError.value = ''
  try {
    const response = await get<RequestDetailResponse>(`/api/admin/requests/${encodeURIComponent(id)}`)
    if (token !== detailToken || selectedId.value !== id) return
    detail.value = response.request
    applyAuthoritativeAnswers(response.request)
  } catch (error) {
    if (token !== detailToken) return
    detailError.value = errorMessage(error, 'Could not load this request.')
  } finally {
    if (token === detailToken) detailLoading.value = false
  }
}

async function refreshDetailSoft() {
  const id = selectedId.value
  if (!id) return
  try {
    const response = await get<RequestDetailResponse>(`/api/admin/requests/${encodeURIComponent(id)}`)
    if (selectedId.value !== id) return
    detail.value = response.request
    if (!isActiveStatus(response.request.status)) applyAuthoritativeAnswers(response.request)
  } catch {
    /* keep the current view; the queue list will surface connection issues */
  }
}

async function loadOperators() {
  if (!isAdmin.value) return
  try {
    const response = await get<OperatorsResponse>('/api/admin/operators')
    operators.value = response.operators
      .filter((operator) => !operator.disabled)
      .slice()
      .sort((a, b) => a.name.localeCompare(b.name))
  } catch {
    /* reassignment simply stays unavailable */
  }
}

function ensureSelection() {
  if (selectedId.value || !autoSelect.value) return
  const first = list.value[0]
  if (first) void router.replace({ name: 'admin-queue', params: { id: first.id } })
}

function upsertList(request: DecisionRequest) {
  const index = list.value.findIndex((item) => item.id === request.id)
  if (isActiveStatus(request.status)) {
    if (index >= 0) list.value.splice(index, 1, request)
    else list.value.push(request)
    list.value = sortActiveRequests(list.value)
  } else if (index >= 0) {
    list.value.splice(index, 1)
  }
}

function applyDetailEvent(event: Extract<WsEvent, { type: 'request.created' | 'request.assigned' | 'request.updated' | 'request.completed' }>) {
  const request = event.data.request
  if (request.id !== selectedId.value) return
  if (detail.value) detail.value = { ...detail.value, ...request }
  else detail.value = request
  if (!isActiveStatus(request.status)) {
    answers.value = request.answers ? { ...request.answers } : answers.value
    draftState.value = 'clean'
    clearDraftTimer()
  }
}

function handleEvent(event: WsEvent) {
  if (event.type === 'hello') {
    list.value = sortActiveRequests(event.data.pending)
    ensureSelection()
    if (selectedId.value) void refreshDetailSoft()
    return
  }
  if (
    event.type === 'request.created' ||
    event.type === 'request.assigned' ||
    event.type === 'request.updated' ||
    event.type === 'request.completed'
  ) {
    const request = event.data.request
    upsertList(request)
    applyDetailEvent(event)
    if (event.type === 'request.created' && !selectedId.value && autoSelect.value) {
      void router.replace({ name: 'admin-queue', params: { id: request.id } })
    }
  }
}

/* --------------------------------------------------------------- draft */
function scheduleDraftSave() {
  if (!isActive.value || !selectedId.value || submitting.value) return
  draftState.value = 'dirty'
  clearDraftTimer()
  draftTimer = window.setTimeout(() => {
    draftTimer = null
    void saveDraftNow()
  }, 700)
}

async function saveDraftNow() {
  const id = selectedId.value
  if (!id || !isActive.value || draftInFlight) return
  if (draftState.value !== 'dirty' && draftState.value !== 'error') return
  const snapshot = cloneAnswerMap(answers.value)
  const fingerprint = JSON.stringify(snapshot)
  draftInFlight = true
  draftState.value = 'saving'
  try {
    await put(`/api/admin/requests/${encodeURIComponent(id)}/draft`, { answers: snapshot })
    if (selectedId.value !== id) return
    if (JSON.stringify(answers.value) === fingerprint) {
      draftState.value = 'saved'
    } else {
      draftState.value = 'dirty'
      scheduleDraftSave()
    }
  } catch (error) {
    if (selectedId.value === id) {
      draftState.value = 'error'
      toast('Draft not saved', 'error', { detail: errorMessage(error) })
    }
  } finally {
    draftInFlight = false
  }
}

function flushCurrentDraft() {
  const id = selectedId.value
  if (!id || !isActive.value) return
  if (draftState.value !== 'dirty' && draftState.value !== 'saving' && draftState.value !== 'error') return
  const snapshot = cloneAnswerMap(answers.value)
  clearDraftTimer()
  void put(`/api/admin/requests/${encodeURIComponent(id)}/draft`, { answers: snapshot }).catch(() => {
    /* best effort on navigation */
  })
}

function setAnswer(questionId: string, answer: Answer) {
  answers.value = { ...answers.value, [questionId]: answer }
  scheduleDraftSave()
}

/* ------------------------------------------------------------- actions */
async function randomize(questionId?: string) {
  const id = selectedId.value
  if (!id || !isActive.value || submitting.value || randomizing.value) return
  randomizing.value = questionId ?? 'all'
  try {
    const questionIds = questionId ? [questionId] : questions.value.map((question) => question.id)
    const response = await post<RandomizeResponse>(`/api/admin/requests/${encodeURIComponent(id)}/randomize`, {
      question_ids: questionIds,
    })
    if (questionId) {
      // Apply only the requested question so unsaved local answers for the
      // other questions are preserved (the server's draft snapshot may lag).
      const randomized = response.answers[questionId]
      if (randomized) answers.value = { ...answers.value, [questionId]: randomized }
    } else {
      answers.value = { ...answers.value, ...response.answers }
    }
    scheduleDraftSave()
  } catch (error) {
    toast('Could not randomize answers', 'error', { detail: errorMessage(error) })
  } finally {
    randomizing.value = null
  }
}

async function submitAnswer() {
  const id = selectedId.value
  if (!id || !isActive.value || submitting.value) return
  if (!allAnswered.value) {
    toast('Answer every question before submitting', 'warning', {
      detail: `${questions.value.length - answeredCount.value} question(s) still outstanding.`,
    })
    return
  }
  submitting.value = true
  clearDraftTimer()
  try {
    const response = await post<AnswerResponse>(`/api/admin/requests/${encodeURIComponent(id)}/answer`, {
      answers: answers.value,
    })
    detail.value = response.request
    answers.value = response.request.answers ? { ...response.request.answers } : answers.value
    draftState.value = 'clean'
    list.value = list.value.filter((item) => item.id !== id)
    toast('Answer submitted', 'success', {
      detail: `${response.request.total_questions} questions · ${formatDuration(response.request.duration_ms)} total`,
    })
    void loadList()
  } catch (error) {
    if (error instanceof ApiError && error.status === 409) {
      toast('Request already ended', 'warning', { detail: error.message })
      await loadDetail(id)
      void loadList()
    } else {
      toast('Submit failed', 'error', { detail: errorMessage(error) })
    }
  } finally {
    submitting.value = false
  }
}

async function reassign(event: Event) {
  const target = event.target as HTMLSelectElement
  const operatorId = target.value
  const id = selectedId.value
  if (!id || !isAdmin.value) return
  assignBusy.value = true
  try {
    const response = await put<AnswerResponse>(`/api/admin/requests/${encodeURIComponent(id)}/assign`, {
      operator_id: operatorId || null,
    })
    if (detail.value) detail.value = { ...detail.value, ...response.request }
    upsertList(response.request)
    toast(operatorId ? 'Request reassigned' : 'Request returned to the queue', 'success')
  } catch (error) {
    toast('Reassignment failed', 'error', { detail: errorMessage(error) })
    target.value = detail.value?.assigned_to?.id ?? ''
  } finally {
    assignBusy.value = false
  }
}

function askCancel() {
  cancelOpen.value = true
}

async function confirmCancel() {
  const id = selectedId.value
  if (!id) return
  cancelBusy.value = true
  try {
    const response = await post<AnswerResponse>(`/api/admin/requests/${encodeURIComponent(id)}/cancel`)
    detail.value = response.request
    answers.value = response.request.answers ? { ...response.request.answers } : {}
    draftState.value = 'clean'
    clearDraftTimer()
    list.value = list.value.filter((item) => item.id !== id)
    toast('Request cancelled', 'success')
    cancelOpen.value = false
  } catch (error) {
    toast('Cancel failed', 'error', { detail: errorMessage(error) })
  } finally {
    cancelBusy.value = false
  }
}

function onExpired() {
  if (expiryTimer !== null) return
  expiryTimer = window.setTimeout(() => {
    expiryTimer = null
    const id = selectedId.value
    if (id) void loadDetail(id)
    void loadList()
  }, 1100)
}

function selectRequest(id: string) {
  autoSelect.value = true
  if (id === selectedId.value) return
  void router.push({ name: 'admin-queue', params: { id } })
}

function backToList() {
  autoSelect.value = false
  void router.replace({ name: 'admin-queue' })
}

function nextRequest() {
  const next = list.value[0]
  if (next) void router.replace({ name: 'admin-queue', params: { id: next.id } })
  else void router.replace({ name: 'admin-queue' })
}

watch(
  () => route.params.id,
  (raw) => {
    const id = typeof raw === 'string' && raw ? raw : Array.isArray(raw) && typeof raw[0] === 'string' ? raw[0] : null
    if (id === selectedId.value) return
    if (selectedId.value) flushCurrentDraft()
    selectedId.value = id
    detail.value = null
    detailError.value = ''
    detailLoading.value = false
    answers.value = {}
    draftState.value = 'clean'
    clearDraftTimer()
    if (id) void loadDetail(id)
  },
  { immediate: true },
)

onMounted(async () => {
  socket.connect()
  off = socket.onEvent(handleEvent)
  if (isAdmin.value) void loadOperators()
  await loadList()
})

onBeforeUnmount(() => {
  if (off) off()
  if (draftTimer !== null) window.clearTimeout(draftTimer)
  if (expiryTimer !== null) window.clearTimeout(expiryTimer)
  flushCurrentDraft()
})

onBeforeRouteLeave(() => {
  flushCurrentDraft()
  return true
})
</script>

<template>
  <div class="adm-page adm-queue-page">
    <header class="adm-page-head adm-queue-head">
      <div>
        <p class="eyebrow adm-page-eyebrow">Operations</p>
        <h1 class="adm-page-title">Decision queue</h1>
        <p class="adm-page-sub">
          Answer live requests before the deadline. Drafts autosave; unanswered requests are auto-filled.
        </p>
      </div>
      <div class="adm-page-actions">
        <span class="adm-conn" :class="socket.state.connected ? 'is-live' : 'is-connecting'">
          <span class="adm-conn-dot" aria-hidden="true" />
          <span>{{ socket.state.connected ? 'Live' : 'Reconnecting' }}</span>
        </span>
        <button type="button" class="btn btn-sm" :disabled="loading" @click="loadList">
          <RefreshCw :size="14" :class="{ 'adm-spin': loading }" />
          <span>Refresh</span>
        </button>
      </div>
    </header>

    <div class="adm-queue-body" :class="{ 'is-detail': Boolean(selectedId) }">
      <section class="adm-queue-list" aria-labelledby="adm-queue-list-title">
        <header class="adm-queue-list-head">
          <div>
            <h2 id="adm-queue-list-title" class="adm-panel-title">Active</h2>
            <p class="adm-panel-sub">{{ list.length }} request{{ list.length === 1 ? '' : 's' }} · oldest first</p>
          </div>
          <span class="badge" :class="list.length ? 'badge-amber' : 'badge-green'">{{ list.length }}</span>
        </header>

        <div class="adm-queue-list-scroll">
          <div v-if="loading && !list.length" class="adm-skeleton-list" aria-hidden="true">
            <div v-for="n in 5" :key="n" class="adm-skeleton-row adm-skeleton-row-tall" />
          </div>
          <div v-else-if="listError && !list.length" class="adm-queue-list-state">
            <p class="adm-alert-copy">{{ listError }}</p>
            <button type="button" class="btn btn-sm" @click="loadList">Retry</button>
          </div>
          <div v-else-if="!list.length" class="adm-queue-list-state">
            <EmptyState
              title="Queue clear"
              description="No active requests. New work appears here over the live socket."
            />
          </div>
          <div v-else class="adm-queue-list-items">
            <div v-if="listError" class="adm-queue-list-error">
              <span>{{ listError }}</span>
              <button type="button" class="btn btn-sm btn-ghost" @click="loadList">Retry</button>
            </div>
            <RequestListItem
              v-for="request in list"
              :key="request.id"
              :request="request"
              :selected="request.id === selectedId"
              :now="now"
              @select="selectRequest"
            />
          </div>
        </div>
      </section>

      <section class="adm-queue-detail" aria-label="Decision request detail">
        <div v-if="!selectedId" class="adm-queue-placeholder">
          <EmptyState
            title="Select a request"
            :description="list.length ? `${list.length} active request${list.length === 1 ? '' : 's'} waiting in the queue.` : 'The live queue is empty.'"
          />
          <button v-if="list.length" type="button" class="btn btn-sm" @click="selectRequest(list[0].id)">
            Open oldest request
            <ArrowRight :size="13" />
          </button>
        </div>

        <div v-else-if="detailLoading && !detail" class="adm-queue-detail-loading">
          <button type="button" class="btn btn-sm adm-mobile-back" @click="backToList">
            <ArrowLeft :size="14" />
            <span>Back to queue</span>
          </button>
          <div class="adm-skeleton-row" />
          <div class="adm-skeleton-row" />
          <div class="adm-skeleton-row adm-skeleton-row-tall" />
        </div>

        <div v-else-if="detailError && !detail" class="adm-queue-detail-error">
          <button type="button" class="btn btn-sm adm-mobile-back" @click="backToList">
            <ArrowLeft :size="14" />
            <span>Back to queue</span>
          </button>
          <TriangleAlert :size="18" />
          <p>{{ detailError }}</p>
          <button type="button" class="btn btn-sm" @click="selectedId && loadDetail(selectedId)">Retry</button>
        </div>

        <template v-else-if="detail">
          <header class="adm-detail-head">
            <button type="button" class="btn btn-sm adm-mobile-back" @click="backToList">
              <ArrowLeft :size="14" />
              <span>Queue</span>
            </button>

            <div class="adm-detail-heading">
              <div class="adm-detail-title-row">
                <span class="mono adm-detail-model">{{ detail.model }}</span>
                <span class="badge">{{ protocolLabel(detail.protocol) }}</span>
                <span class="badge" :class="statusBadgeClass(detail.status)">{{ statusLabel(detail.status) }}</span>
                <span v-if="detail.auto_filled" class="badge badge-amber">auto-filled</span>
                <span v-if="isMine" class="badge badge-blue">assigned to you</span>
              </div>
              <div class="adm-detail-meta-row">
                <span class="mono adm-detail-id" :title="detail.id">{{ detail.id }}</span>
                <CopyButton :text="detail.id" label="Copy ID" />
                <span class="adm-detail-meta-dot" aria-hidden="true">·</span>
                <span>Created {{ age }} ago</span>
                <span class="adm-detail-meta-dot" aria-hidden="true">·</span>
                <span>Assigned {{ assignedName }}</span>
                <span class="adm-detail-meta-dot" aria-hidden="true">·</span>
                <span>{{ answeredCount }}/{{ questions.length }} answered</span>
              </div>
            </div>

            <div class="adm-detail-actions">
              <span v-if="isActive" class="adm-draft" :class="`is-${draftState}`" aria-live="polite">
                <Loader2 v-if="draftState === 'saving'" :size="12" class="adm-spin" />
                <Check v-else-if="draftState === 'saved'" :size="12" />
                <TriangleAlert v-else-if="draftState === 'error'" :size="12" />
                <span v-else class="adm-draft-dot" aria-hidden="true" />
                <span>{{ draftLabel }}</span>
                <button
                  v-if="draftState === 'error'"
                  type="button"
                  class="adm-draft-retry"
                  aria-label="Retry draft save"
                  @click="saveDraftNow"
                >
                  Retry
                </button>
              </span>

              <template v-if="isActive">
                <button
                  type="button"
                  class="btn btn-sm"
                  :disabled="submitting || randomizing !== null"
                  @click="randomize()"
                >
                  <Loader2 v-if="randomizing === 'all'" :size="13" class="adm-spin" />
                  <Shuffle v-else :size="13" />
                  <span>Randomize all</span>
                </button>
                <button type="button" class="btn btn-primary btn-sm" :disabled="submitting || !allAnswered" @click="submitAnswer">
                  <Loader2 v-if="submitting" :size="13" class="adm-spin" />
                  <Send v-else :size="13" />
                  <span>{{ submitting ? 'Submitting…' : 'Submit answer' }}</span>
                </button>
              </template>
            </div>
          </header>

          <div class="adm-detail-bar">
            <CountdownTimer
              v-if="detail && isActive"
              :deadline-at="detail.deadline_at"
              :auto-fill-at="detail.auto_fill_at"
              :created-at="detail.created_at"
              :timeout-seconds="detail.timeout_seconds"
              :offset="socket.state.serverOffset"
              @expired="onExpired"
            />

            <div class="adm-detail-bar-right">
              <div v-if="isAdmin && isActive" class="adm-assign-control">
                <label class="adm-assign-label" :for="`adm-assign-${detail.id}`">Assigned operator</label>
                <select
                  :id="`adm-assign-${detail.id}`"
                  class="select adm-assign-select"
                  :value="detail.assigned_to?.id ?? ''"
                  :disabled="assignBusy"
                  @change="reassign"
                >
                  <option value="">Unassigned / queue</option>
                  <option v-for="operator in assignOptions" :key="operator.id" :value="operator.id">
                    {{ operator.name }}{{ operator.online ? ' · online' : ' · offline' }}
                  </option>
                </select>
              </div>
              <button v-if="isAdmin && isActive" type="button" class="btn btn-sm btn-danger" @click="askCancel">
                <Ban :size="13" />
                <span>Cancel</span>
              </button>
              <button
                v-if="!isActive"
                type="button"
                class="btn btn-sm"
                @click="refreshDetailSoft"
              >
                <RefreshCw :size="13" />
                <span>Refresh outcome</span>
              </button>
            </div>
          </div>

          <div class="adm-detail-scroll">
            <div v-if="!isActive" class="adm-outcome" :class="`is-${outcomeTone}`">
              <span class="adm-outcome-icon"><component :is="outcomeIcon" :size="17" /></span>
              <div class="adm-outcome-copy">
                <strong>{{ outcomeTitle }}</strong>
                <p>{{ outcomeDetail }}</p>
              </div>
              <button v-if="list.length" type="button" class="btn btn-sm" @click="nextRequest">
                Next request
                <ArrowRight :size="13" />
              </button>
            </div>

            <div class="adm-detail-grid">
              <section class="adm-panel adm-input-panel" aria-labelledby="adm-request-input-title">
                <header class="adm-panel-head">
                  <div>
                    <h2 id="adm-request-input-title" class="adm-panel-title">Input</h2>
                    <p class="adm-panel-sub">{{ detail.input_kind || 'structured' }} · human-readable</p>
                  </div>
                </header>
                <div class="adm-panel-body adm-input-panel-body">
                  <InputViewer
                    :value="detail.input"
                    :input-text="detail.input_text"
                    :kind="detail.input_kind"
                    label="Request input"
                  />
                </div>
              </section>

              <section class="adm-questions" aria-labelledby="adm-request-questions-title">
                <header class="adm-questions-head">
                  <div>
                    <h2 id="adm-request-questions-title" class="adm-panel-title">Questions</h2>
                    <p class="adm-panel-sub">{{ answeredCount }} of {{ questions.length }} answered</p>
                  </div>
                  <div class="adm-questions-progress" aria-hidden="true">
                    <span :style="{ width: `${progress * 100}%` }" />
                  </div>
                </header>

                <template v-if="isActive">
                  <QuestionEditor
                    v-for="(question, index) in questions"
                    :key="`${detail.id}:${question.id}`"
                    :question="question"
                    :answer="answers[question.id]"
                    :index="index"
                    :disabled="submitting || randomizing !== null"
                    :randomizing="randomizing === question.id || randomizing === 'all'"
                    @update:answer="setAnswer(question.id, $event)"
                    @randomize="randomize(question.id)"
                  />
                  <p v-if="!allAnswered" class="adm-submit-hint">
                    <TriangleAlert :size="12" />
                    {{ questions.length - answeredCount }} question(s) must be answered before submit.
                  </p>
                </template>

                <template v-else>
                  <AnswerSummary
                    v-for="question in questions"
                    :key="`${detail.id}:${question.id}`"
                    :question="question"
                    :answer="answers[question.id] ?? null"
                  />
                  <p v-if="!questions.length" class="adm-answer-empty">No questions recorded.</p>
                </template>
              </section>
            </div>
          </div>
        </template>
      </section>
    </div>

    <ConfirmDialog
      :open="cancelOpen"
      title="Cancel this request?"
      message="The waiting HTTP client will receive a cancellation response. This cannot be undone."
      :detail="detail ? `#${detail.id} · ${detail.model}` : ''"
      confirm-label="Cancel request"
      :busy="cancelBusy"
      @close="cancelOpen = false"
      @confirm="confirmCancel"
    />
  </div>
</template>
