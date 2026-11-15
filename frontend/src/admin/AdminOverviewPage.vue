<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  Activity,
  ArrowRight,
  CheckCircle2,
  Clock3,
  Inbox,
  Loader2,
  RefreshCw,
  Users,
  Wifi,
  WifiOff,
  Zap,
} from 'lucide-vue-next'
import type { AdminOverview, RequestSummary, Role } from '@/types/api'
import { get } from '@/lib/api'
import { formatDuration, formatNumber } from '@/lib/format'
import EmptyState from '@/components/EmptyState.vue'
import RequestListItem from './components/RequestListItem.vue'
import { useAdminSocket } from './useAdminSocket'
import { useAdminClock } from './useAdminClock'
import { errorMessage, formatAge, isActiveStatus, initials, protocolShort } from './utils'

interface OnlineRow {
  id: string
  name: string
  role: Role
}

const router = useRouter()
const socket = useAdminSocket()
const now = useAdminClock(1000)

const overview = ref<AdminOverview | null>(null)
const loading = ref(true)
const refreshing = ref(false)
const error = ref('')

let off: (() => void) | null = null
let refreshTimer: number | null = null

async function load(silent = false) {
  if (silent) refreshing.value = true
  else loading.value = true
  error.value = ''
  try {
    overview.value = await get<AdminOverview>('/api/admin/overview')
  } catch (err) {
    error.value = errorMessage(err, 'Could not load the overview.')
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

function scheduleRefresh() {
  if (refreshTimer !== null) window.clearTimeout(refreshTimer)
  refreshTimer = window.setTimeout(() => {
    refreshTimer = null
    void load(true)
  }, 650)
}

onMounted(async () => {
  socket.connect()
  off = socket.onEvent((event) => {
    if (event.type === 'hello' || event.type === 'presence' || event.type.startsWith('request.')) scheduleRefresh()
  })
  await load()
})

onBeforeUnmount(() => {
  if (off) off()
  if (refreshTimer !== null) window.clearTimeout(refreshTimer)
})

const snapshot = computed<RequestSummary[]>(() => {
  if (socket.state.hello) return socket.state.pending
  return (overview.value?.recent ?? []).filter((request) => isActiveStatus(request.status))
})
const queueTotal = computed(() => (socket.state.hello ? socket.state.pending.length : overview.value?.active ?? 0))
const onlineOperators = computed<OnlineRow[]>(() => {
  const list = socket.state.hello
    ? socket.state.presence.filter((operator) => operator.online)
    : (overview.value?.online_operators ?? [])
  return list.map((operator) => ({ id: operator.id, name: operator.name, role: operator.role }))
})
const operatorTotal = computed(() =>
  socket.state.hello ? socket.state.presence.length : onlineOperators.value.length,
)
const modelRows = computed(() =>
  (overview.value?.models ?? [])
    .filter((model) => model.enabled || (model.today ?? 0) > 0)
    .slice()
    .sort((a, b) => (b.today ?? 0) - (a.today ?? 0) || a.sort_order - b.sort_order),
)
const maxModelToday = computed(() => Math.max(1, ...modelRows.value.map((model) => model.today ?? 0)))
const answeredRate = computed(() => {
  const today = overview.value?.today
  if (!today || !today.total) return 0
  return today.answered / today.total
})
const oldestPendingAge = computed(() =>
  overview.value?.active ? formatAge(overview.value.oldest_pending_ms) : '—',
)
const live = computed(() => socket.state.connected && Boolean(socket.state.hello))

function openRequest(id: string) {
  void router.push({ name: 'admin-queue', params: { id } })
}

function modelPercent(today: number | undefined): string {
  const count = today ?? 0
  if (!count) return '0%'
  return `${Math.max(2, Math.min(100, (count / maxModelToday.value) * 100))}%`
}
</script>

<template>
  <div class="adm-page">
    <header class="adm-page-head">
      <div>
        <p class="eyebrow adm-page-eyebrow">Operations</p>
        <h1 class="adm-page-title">Overview</h1>
        <p class="adm-page-sub">Live queue, operator presence and model mix for today.</p>
      </div>
      <div class="adm-page-actions">
        <span class="adm-conn" :class="live ? 'is-live' : overview ? 'is-connecting' : 'is-offline'">
          <span class="adm-conn-dot" aria-hidden="true" />
          <span>{{ live ? 'Live' : overview ? 'REST snapshot' : 'Loading' }}</span>
        </span>
        <button type="button" class="btn btn-sm" :disabled="refreshing" @click="load(true)">
          <RefreshCw :size="14" :class="{ 'adm-spin': refreshing }" />
          <span>Refresh</span>
        </button>
      </div>
    </header>

    <div v-if="error" class="adm-alert" role="alert">
      <span>{{ error }}</span>
      <button type="button" class="btn btn-sm" @click="load()">Retry</button>
    </div>

    <section class="adm-metrics" aria-label="Today at a glance">
      <RouterLink :to="{ name: 'admin-queue' }" class="adm-metric adm-metric-link">
        <span class="adm-metric-label"><Activity :size="13" /> Active requests</span>
        <span class="adm-metric-value">{{ overview ? formatNumber(overview.active) : '—' }}</span>
        <span class="adm-metric-hint">
          <template v-if="overview">{{ overview.queued }} queued · {{ overview.assigned }} assigned</template>
          <template v-else>Live decision queue</template>
        </span>
        <ArrowRight :size="14" class="adm-metric-arrow" />
      </RouterLink>

      <RouterLink :to="{ name: 'admin-history' }" class="adm-metric adm-metric-link">
        <span class="adm-metric-label"><Inbox :size="13" /> Today total</span>
        <span class="adm-metric-value">{{ overview ? formatNumber(overview.today.total) : '—' }}</span>
        <span class="adm-metric-hint">
          <template v-if="overview">
            {{ formatNumber(overview.today.auto_filled) }} auto-filled · {{ formatNumber(overview.today.timed_out) }} timed out
          </template>
          <template v-else>Requests received today</template>
        </span>
        <ArrowRight :size="14" class="adm-metric-arrow" />
      </RouterLink>

      <RouterLink :to="{ name: 'admin-history' }" class="adm-metric adm-metric-link">
        <span class="adm-metric-label"><CheckCircle2 :size="13" /> Answered</span>
        <span class="adm-metric-value">{{ overview ? formatNumber(overview.today.answered) : '—' }}</span>
        <span class="adm-metric-hint">
          <template v-if="overview">{{ Math.round(answeredRate * 100) }}% of today's requests</template>
          <template v-else>Human answers today</template>
        </span>
        <ArrowRight :size="14" class="adm-metric-arrow" />
      </RouterLink>

      <RouterLink :to="{ name: 'admin-history' }" class="adm-metric adm-metric-link">
        <span class="adm-metric-label"><Clock3 :size="13" /> Avg response</span>
        <span class="adm-metric-value">{{ overview ? formatDuration(overview.average_duration_ms) : '—' }}</span>
        <span class="adm-metric-hint">Oldest pending {{ oldestPendingAge }}</span>
        <ArrowRight :size="14" class="adm-metric-arrow" />
      </RouterLink>
    </section>

    <div class="adm-overview-notes">
      <span><Zap :size="12" /> {{ overview ? formatNumber(overview.today.auto_filled) : '—' }} auto-filled today</span>
      <span><Clock3 :size="12" /> Oldest pending {{ oldestPendingAge }}</span>
      <span :class="{ 'is-offline': !live }">
        <Wifi v-if="live" :size="12" />
        <WifiOff v-else :size="12" />
        {{ live ? 'WebSocket connected' : 'Reconnecting — REST snapshot shown' }}
      </span>
    </div>

    <div class="adm-overview-grid">
      <section class="adm-panel adm-overview-queue" aria-labelledby="adm-overview-queue-title">
        <header class="adm-panel-head">
          <div>
            <h2 id="adm-overview-queue-title" class="adm-panel-title">Live queue</h2>
            <p class="adm-panel-sub">Oldest first · {{ queueTotal }} active</p>
          </div>
          <RouterLink :to="{ name: 'admin-queue' }" class="btn btn-sm">
            <span>Open queue</span>
            <ArrowRight :size="13" />
          </RouterLink>
        </header>
        <div class="adm-panel-body adm-overview-queue-body">
          <div v-if="loading && !overview" class="adm-skeleton-list" aria-hidden="true">
            <div v-for="n in 4" :key="n" class="adm-skeleton-row" />
          </div>
          <EmptyState
            v-else-if="!snapshot.length"
            title="Queue is clear"
            description="New decision requests appear here in real time. Operators are assigned automatically when online."
          />
          <div v-else class="adm-queue-snapshot">
            <RequestListItem
              v-for="request in snapshot.slice(0, 6)"
              :key="request.id"
              :request="request"
              :now="now"
              @select="openRequest"
            />
          </div>
          <footer v-if="snapshot.length > 6" class="adm-panel-foot">
            <RouterLink :to="{ name: 'admin-queue' }" class="adm-link">
              {{ snapshot.length - 6 }} more in queue
              <ArrowRight :size="12" />
            </RouterLink>
          </footer>
        </div>
      </section>

      <div class="adm-overview-side">
        <section class="adm-panel" aria-labelledby="adm-overview-operators-title">
          <header class="adm-panel-head">
            <div>
              <h2 id="adm-overview-operators-title" class="adm-panel-title">Operators online</h2>
              <p class="adm-panel-sub">{{ onlineOperators.length }} of {{ operatorTotal }} online</p>
            </div>
            <span class="badge badge-green"><span class="dot dot-live" /> {{ onlineOperators.length }}</span>
          </header>
          <div class="adm-panel-body">
            <div v-if="loading && !overview" class="adm-skeleton-list" aria-hidden="true">
              <div v-for="n in 2" :key="n" class="adm-skeleton-row" />
            </div>
            <div v-else-if="!onlineOperators.length" class="adm-overview-empty">
              <Users :size="16" />
              <p>No operators online. Queued requests wait for the next connection.</p>
            </div>
            <ul v-else class="adm-operator-list">
              <li v-for="operator in onlineOperators" :key="operator.id">
                <span class="adm-avatar">{{ initials(operator.name) }}</span>
                <span class="adm-operator-copy">
                  <span class="adm-operator-name">{{ operator.name }}</span>
                  <span class="adm-operator-role">{{ operator.role === 'admin' ? 'Administrator' : 'Operator' }}</span>
                </span>
                <span class="adm-online-dot"><span class="dot dot-live" /> online</span>
              </li>
            </ul>
          </div>
        </section>

        <section class="adm-panel" aria-labelledby="adm-overview-models-title">
          <header class="adm-panel-head">
            <div>
              <h2 id="adm-overview-models-title" class="adm-panel-title">Model distribution</h2>
              <p class="adm-panel-sub">Requests received today</p>
            </div>
          </header>
          <div class="adm-panel-body">
            <div v-if="loading && !overview" class="adm-skeleton-list" aria-hidden="true">
              <div v-for="n in 3" :key="n" class="adm-skeleton-row" />
            </div>
            <p v-else-if="!modelRows.length" class="adm-overview-empty adm-overview-empty-text">
              No model traffic recorded today.
            </p>
            <ul v-else class="adm-model-bars">
              <li v-for="model in modelRows" :key="model.id">
                <div class="adm-model-bar-head">
                  <span class="adm-model-name">{{ model.display_name }}</span>
                  <span class="mono adm-model-count">{{ formatNumber(model.today ?? 0) }}</span>
                </div>
                <div class="adm-bar" aria-hidden="true">
                  <span :style="{ width: modelPercent(model.today) }" />
                </div>
                <div class="adm-model-bar-foot">
                  <span class="mono">{{ model.name }}</span>
                  <span class="badge">{{ protocolShort(model.protocol) }}</span>
                </div>
              </li>
            </ul>
          </div>
        </section>
      </div>
    </div>

    <p v-if="refreshing" class="adm-refreshing" aria-live="polite">
      <Loader2 :size="12" class="adm-spin" /> Refreshing snapshot…
    </p>
  </div>
</template>
