<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { Download, RefreshCw, Search, X } from 'lucide-vue-next'
import type { DecisionRequest, Model, RequestDetailResponse, RequestList, RequestSummary } from '@/types/api'
import { get } from '@/lib/api'
import { formatDate, formatDuration, statusLabel } from '@/lib/format'
import EmptyState from '@/components/EmptyState.vue'
import AdminDrawer from './components/AdminDrawer.vue'
import AnswerSummary from './components/AnswerSummary.vue'
import InputViewer from './components/InputViewer.vue'
import PaginationBar from './components/PaginationBar.vue'
import { useSession } from '@/lib/session'
import {
  errorMessage,
  isActiveStatus,
  protocolShort,
  shortId,
  statusBadgeClass,
} from './utils'

const session = useSession()
const limit = 25

const rows = ref<RequestSummary[]>([])
const total = ref(0)
const offset = ref(0)
const loading = ref(true)
const error = ref('')
const models = ref<Model[]>([])
const filters = reactive({ status: '', model: '', q: '' })
const searchText = ref('')

const drawerOpen = ref(false)
const drawerId = ref<string | null>(null)
const drawerDetail = ref<DecisionRequest | null>(null)
const drawerLoading = ref(false)
const drawerError = ref('')

let searchTimer: number | null = null

const isAdmin = computed(() => session.state.admin?.role === 'admin')
const hasFilters = computed(() => Boolean(filters.status || filters.model || filters.q))

async function load() {
  loading.value = true
  error.value = ''
  const params = new URLSearchParams({ view: 'history', limit: String(limit), offset: String(offset.value) })
  if (filters.status) params.set('status', filters.status)
  if (filters.model) params.set('model', filters.model)
  if (filters.q.trim()) params.set('q', filters.q.trim())
  try {
    const response = await get<RequestList>(`/api/admin/requests?${params.toString()}`)
    rows.value = response.requests
    total.value = response.total
  } catch (err) {
    error.value = errorMessage(err, 'Could not load request history.')
  } finally {
    loading.value = false
  }
}

async function loadModels() {
  try {
    const response = await get<{ models: Model[] }>('/api/admin/models')
    models.value = response.models
  } catch {
    models.value = []
  }
}

function applyFilters() {
  offset.value = 0
  void load()
}

function scheduleSearch() {
  if (searchTimer !== null) window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(() => {
    searchTimer = null
    filters.q = searchText.value
    applyFilters()
  }, 320)
}

function applySearch() {
  if (searchTimer !== null) {
    window.clearTimeout(searchTimer)
    searchTimer = null
  }
  filters.q = searchText.value
  applyFilters()
}

function clearFilters() {
  filters.status = ''
  filters.model = ''
  filters.q = ''
  searchText.value = ''
  applyFilters()
}

function onOffset(next: number) {
  offset.value = next
  void load()
}

async function openDrawer(id: string) {
  drawerOpen.value = true
  drawerId.value = id
  drawerDetail.value = null
  drawerError.value = ''
  drawerLoading.value = true
  try {
    const response = await get<RequestDetailResponse>(`/api/admin/requests/${encodeURIComponent(id)}`)
    if (drawerId.value !== id) return
    drawerDetail.value = response.request
  } catch (err) {
    if (drawerId.value === id) drawerError.value = errorMessage(err, 'Could not load this request.')
  } finally {
    if (drawerId.value === id) drawerLoading.value = false
  }
}

function closeDrawer() {
  drawerOpen.value = false
  drawerId.value = null
  drawerDetail.value = null
  drawerError.value = ''
}

onMounted(() => {
  void loadModels()
  void load()
})

onBeforeUnmount(() => {
  if (searchTimer !== null) window.clearTimeout(searchTimer)
})

defineExpose({ load })
</script>

<template>
  <div class="adm-page">
    <header class="adm-page-head">
      <div>
        <p class="eyebrow adm-page-eyebrow">Operations</p>
        <h1 class="adm-page-title">History</h1>
        <p class="adm-page-sub">Completed, timed-out and cancelled requests with final answers and timings.</p>
      </div>
      <div class="adm-page-actions">
        <button type="button" class="btn btn-sm" :disabled="loading" @click="load">
          <RefreshCw :size="14" :class="{ 'adm-spin': loading }" />
          <span>Refresh</span>
        </button>
        <a v-if="isAdmin" class="btn btn-sm" href="/api/admin/export/requests" download>
          <Download :size="14" />
          <span>Export JSON</span>
        </a>
      </div>
    </header>

    <section class="adm-panel">
      <header class="adm-panel-head">
        <div class="adm-filter-row">
          <div class="adm-search">
            <Search :size="14" class="adm-search-icon" aria-hidden="true" />
            <input
              v-model="searchText"
              class="input adm-search-input"
              type="search"
              placeholder="Search request id, input or model…"
              aria-label="Search request history"
              @input="scheduleSearch"
              @keydown.enter.prevent="applySearch"
            />
          </div>
          <div class="adm-filter">
            <label class="sr-only" for="adm-history-status">Status</label>
            <select id="adm-history-status" v-model="filters.status" class="select adm-filter-select" @change="applyFilters">
              <option value="">All statuses</option>
              <option value="answered">Answered</option>
              <option value="timed_out">Timed out</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </div>
          <div class="adm-filter">
            <label class="sr-only" for="adm-history-model">Model</label>
            <select id="adm-history-model" v-model="filters.model" class="select adm-filter-select" @change="applyFilters">
              <option value="">All models</option>
              <option v-for="model in models" :key="model.id" :value="model.name">{{ model.display_name }}</option>
            </select>
          </div>
          <button v-if="hasFilters" type="button" class="btn btn-sm btn-ghost" @click="clearFilters">
            <X :size="13" />
            <span>Clear</span>
          </button>
        </div>
        <div class="adm-panel-head-meta">
          <span class="badge">{{ total }} requests</span>
        </div>
      </header>

      <div v-if="error" class="adm-alert" role="alert">
        <span>{{ error }}</span>
        <button type="button" class="btn btn-sm" @click="load">Retry</button>
      </div>

      <div class="table-wrap">
        <table class="table adm-table">
          <thead>
            <tr>
              <th scope="col">Created</th>
              <th scope="col">Request</th>
              <th scope="col">Model</th>
              <th scope="col">Status</th>
              <th scope="col">Questions</th>
              <th scope="col">Operator</th>
              <th scope="col">Duration</th>
              <th scope="col">Outcome</th>
            </tr>
          </thead>
          <tbody>
            <template v-if="loading && !rows.length">
              <tr v-for="n in 6" :key="n">
                <td colspan="8"><div class="adm-skeleton-row" /></td>
              </tr>
            </template>
            <tr v-else-if="!rows.length">
              <td colspan="8">
                <EmptyState
                  title="No matching requests"
                  description="Adjust the filters or wait for completed work to appear here."
                />
              </td>
            </tr>
            <template v-else>
              <tr
                v-for="request in rows"
                :key="request.id"
                class="adm-row-clickable"
                tabindex="0"
                @click="openDrawer(request.id)"
                @keydown.enter="openDrawer(request.id)"
                @keydown.space.prevent="openDrawer(request.id)"
              >
                <td class="nowrap muted">{{ formatDate(request.created_at) }}</td>
                <td>
                  <button type="button" class="adm-id-button mono" @click.stop="openDrawer(request.id)">
                    #{{ shortId(request.id, 9) }}
                  </button>
                </td>
                <td>
                  <span class="mono adm-model-cell">{{ request.model }}</span>
                  <span class="badge adm-protocol-cell">{{ protocolShort(request.protocol) }}</span>
                </td>
                <td><span class="badge" :class="statusBadgeClass(request.status)">{{ statusLabel(request.status) }}</span></td>
                <td class="mono">{{ request.answered_count }}/{{ request.total_questions }}</td>
                <td>{{ request.answered_by?.name || request.assigned_to?.name || '—' }}</td>
                <td class="mono">{{ formatDuration(request.duration_ms) }}</td>
                <td>
                  <span v-if="request.auto_filled" class="badge badge-amber">auto-filled</span>
                  <span v-else-if="request.error" class="mono muted tiny">{{ request.error }}</span>
                  <span v-else class="muted tiny">manual</span>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>

      <footer class="adm-panel-foot adm-panel-foot-pagination">
        <PaginationBar :total="total" :limit="limit" :offset="offset" :loading="loading" @update:offset="onOffset" />
      </footer>
    </section>

    <AdminDrawer :open="drawerOpen" title="Request detail" width="640px" @close="closeDrawer">
      <template #head-extra>
        <span v-if="drawerDetail" class="badge" :class="statusBadgeClass(drawerDetail.status)">
          {{ statusLabel(drawerDetail.status) }}
        </span>
        <span v-if="drawerDetail?.auto_filled" class="badge badge-amber">auto-filled</span>
      </template>

      <div v-if="drawerLoading" class="adm-skeleton-list" aria-hidden="true">
        <div class="adm-skeleton-row" />
        <div class="adm-skeleton-row" />
        <div class="adm-skeleton-row adm-skeleton-row-tall" />
      </div>
      <div v-else-if="drawerError" class="adm-alert" role="alert">
        <span>{{ drawerError }}</span>
        <button v-if="drawerId" type="button" class="btn btn-sm" @click="openDrawer(drawerId)">Retry</button>
      </div>
      <template v-else-if="drawerDetail">
        <div class="adm-summary-grid">
          <div><span class="adm-summary-label">Request</span><span class="mono">{{ drawerDetail.id }}</span></div>
          <div><span class="adm-summary-label">Model</span><span>{{ drawerDetail.model }}</span></div>
          <div><span class="adm-summary-label">Protocol</span><span>{{ protocolShort(drawerDetail.protocol) }}</span></div>
          <div><span class="adm-summary-label">Created</span><span>{{ formatDate(drawerDetail.created_at) }}</span></div>
          <div><span class="adm-summary-label">Duration</span><span>{{ formatDuration(drawerDetail.duration_ms) }}</span></div>
          <div><span class="adm-summary-label">Operator</span><span>{{ drawerDetail.answered_by?.name || '—' }}</span></div>
          <div><span class="adm-summary-label">Questions</span><span>{{ drawerDetail.answered_count }}/{{ drawerDetail.total_questions }}</span></div>
          <div><span class="adm-summary-label">Auto-filled</span><span>{{ drawerDetail.auto_filled ? 'Yes' : 'No' }}</span></div>
          <div v-if="drawerDetail.error"><span class="adm-summary-label">Outcome</span><span class="mono">{{ drawerDetail.error }}</span></div>
          <div v-if="drawerDetail.user"><span class="adm-summary-label">Customer</span><span>{{ drawerDetail.user.name }} · {{ drawerDetail.user.email }}</span></div>
        </div>

        <section class="adm-detail-section">
          <h3 class="adm-section-title">Input</h3>
          <InputViewer :value="drawerDetail.input" :input-text="drawerDetail.input_text" :kind="drawerDetail.input_kind" />
        </section>

        <section class="adm-detail-section">
          <h3 class="adm-section-title">Final answers</h3>
          <AnswerSummary
            v-for="question in drawerDetail.questions"
            :key="question.id"
            :question="question"
            :answer="drawerDetail.answers ? drawerDetail.answers[question.id] : null"
          />
          <p v-if="!drawerDetail.questions.length" class="adm-answer-empty">No questions recorded.</p>
        </section>
      </template>
    </AdminDrawer>
  </div>
</template>
