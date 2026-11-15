<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RefreshCw } from 'lucide-vue-next'
import EmptyState from '@/components/EmptyState.vue'
import StatTile from '@/components/StatTile.vue'
import { get } from '@/lib/api'
import {
  formatCompact,
  formatDuration,
  formatNumber,
  statusLabel,
  statusTone,
  timeAgo,
  truncateId,
} from '@/lib/format'
import { reportError } from '@/public/support'
import type { Usage } from '@/types/api'

const days = ref(30)
const ranges = [7, 30, 90]
const usage = ref<Usage | null>(null)
const loading = ref(true)
const error = ref('')

const total = computed(() => usage.value?.total ?? 0)
const answered = computed(() => usage.value?.answered ?? 0)
const timedOut = computed(() => usage.value?.timed_out ?? 0)
const answeredRate = computed(() => (total.value ? Math.round((answered.value / total.value) * 100) : 0))

const byModel = computed(() => {
  const rows = usage.value?.by_model ?? []
  return [...rows].sort((a, b) => b.n - a.n)
})

const maxModelCount = computed(() => Math.max(1, ...byModel.value.map((row) => row.n)))

function barWidth(count: number): string {
  return `${Math.max(2, Math.round((count / maxModelCount.value) * 100))}%`
}

function badgeClass(status: string): string {
  const tone = statusTone(status)
  return tone === 'neutral' ? 'badge' : `badge badge-${tone}`
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    usage.value = await get<Usage>(`/api/account/usage?days=${days.value}`)
  } catch (err) {
    error.value = reportError(err, 'Could not load usage for this period.')
  } finally {
    loading.value = false
  }
}

function setRange(range: number) {
  if (days.value === range) return
  days.value = range
}

watch(days, load)
onMounted(load)
</script>

<template>
  <div class="console-page">
    <div class="console-page-head">
      <div>
        <p class="eyebrow">Usage</p>
        <h1 class="console-h1">Usage</h1>
        <p class="console-sub">Request volume, outcomes and latency for this workspace.</p>
      </div>
      <div class="console-page-actions">
        <div class="console-range" role="group" aria-label="Usage period">
          <button
            v-for="range in ranges"
            :key="range"
            type="button"
            class="console-range-btn"
            :class="{ 'is-active': days === range }"
            :aria-pressed="days === range"
            @click="setRange(range)"
          >
            {{ range }}d
          </button>
        </div>
        <button type="button" class="btn btn-sm" :disabled="loading" @click="load">
          <RefreshCw :size="14" :class="{ 'pub-spin': loading }" />
          Refresh
        </button>
      </div>
    </div>

    <div v-if="error" class="console-alert console-alert-error" role="alert">
      <span>{{ error }}</span>
      <button type="button" class="btn btn-sm" @click="load">Retry</button>
    </div>

    <div class="console-stats">
      <template v-if="loading">
        <div v-for="index in 4" :key="index" class="console-stat-skeleton">
          <span class="pub-skeleton pub-skeleton-short" />
          <span class="pub-skeleton pub-skeleton-title" />
        </div>
      </template>
      <template v-else>
        <StatTile
          label="Requests"
          :value="formatCompact(total)"
          :hint="`Last ${days} days`"
          accent
        />
        <StatTile
          label="Answered"
          :value="formatCompact(answered)"
          :hint="total ? `${answeredRate}% of requests` : 'No requests yet'"
        />
        <StatTile
          label="Timed out"
          :value="formatCompact(timedOut)"
          :hint="timedOut ? 'Check your timeout header' : 'None this period'"
        />
        <StatTile
          label="Avg. response"
          :value="usage?.avg_duration_ms ? formatDuration(usage.avg_duration_ms) : '—'"
          hint="Successful requests only"
        />
      </template>
    </div>

    <div class="console-usage-grid">
      <section class="panel console-panel">
        <header class="panel-header">
          <div>
            <h2 class="panel-title">Requests by model</h2>
            <p class="console-panel-sub">Volume across the selected period.</p>
          </div>
        </header>

        <div v-if="loading" class="console-list-loading">
          <span v-for="index in 3" :key="index" class="pub-skeleton" />
        </div>

        <div v-else-if="byModel.length" class="panel-body console-model-bars">
          <div v-for="row in byModel" :key="row.model" class="console-model-row">
            <div class="console-model-row-head">
              <span class="console-model-row-name">{{ row.model }}</span>
              <span class="mono tiny muted">
                {{ formatNumber(row.n) }} request{{ row.n === 1 ? '' : 's' }} ·
                {{ formatNumber(row.answered) }} answered
              </span>
            </div>
            <div class="console-model-track">
              <span class="console-model-fill" :style="{ width: barWidth(row.n) }" />
            </div>
          </div>
          <div class="console-usage-summary">
            <div class="console-usage-summary-head">
              <span class="mono tiny muted">Answered rate</span>
              <span class="mono">{{ answeredRate }}%</span>
            </div>
            <div class="console-usage-summary-track">
              <span class="console-usage-summary-fill" :style="{ width: `${answeredRate}%` }" />
            </div>
          </div>
        </div>

        <EmptyState
          v-else
          title="No requests in this period"
          description="Usage appears here after your first decision request."
        >
          <RouterLink to="/console/playground" class="btn btn-primary btn-sm">Open playground</RouterLink>
        </EmptyState>
      </section>

      <section class="panel console-panel">
        <header class="panel-header">
          <div>
            <h2 class="panel-title">Recent requests</h2>
            <p class="console-panel-sub">The 30 most recent requests.</p>
          </div>
        </header>

        <div v-if="loading" class="console-list-loading">
          <span v-for="index in 6" :key="index" class="pub-skeleton" />
        </div>

        <div v-else-if="usage?.recent.length" class="table-wrap console-recent-scroll">
          <table class="table console-table">
            <thead>
              <tr>
                <th scope="col">Request</th>
                <th scope="col">Model</th>
                <th scope="col">Protocol</th>
                <th scope="col">Status</th>
                <th scope="col">Latency</th>
                <th scope="col">When</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in usage.recent" :key="item.id">
                <td><code class="mono tiny" :title="item.id">{{ truncateId(item.id) }}</code></td>
                <td><span class="console-model-cell">{{ item.model }}</span></td>
                <td><span class="badge">{{ item.protocol === 'systemone' ? 'System One' : 'Gemini' }}</span></td>
                <td>
                  <span class="console-status-cell">
                    <span :class="badgeClass(item.status)">{{ statusLabel(item.status) }}</span>
                    <span v-if="item.auto_filled" class="badge badge-amber">auto</span>
                  </span>
                </td>
                <td class="mono tiny">{{ item.duration_ms ? formatDuration(item.duration_ms) : '—' }}</td>
                <td class="mono tiny muted" :title="String(item.created_at)">{{ timeAgo(item.created_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <EmptyState
          v-else
          title="No request history"
          description="Send a request from the playground or the API to populate this table."
        >
          <RouterLink :to="{ path: '/docs', hash: '#quickstart' }" class="btn btn-sm">Quickstart</RouterLink>
        </EmptyState>
      </section>
    </div>
  </div>
</template>
