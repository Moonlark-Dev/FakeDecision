<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { ArrowRight, ArrowUpRight, KeyRound, RefreshCw } from 'lucide-vue-next'
import CodeBlock from '@/components/CodeBlock.vue'
import EmptyState from '@/components/EmptyState.vue'
import StatTile from '@/components/StatTile.vue'
import { get } from '@/lib/api'
import { useSession } from '@/lib/session'
import { formatCompact, formatDuration, statusLabel, statusTone, timeAgo, truncateId } from '@/lib/format'
import { reportError } from '@/public/support'
import type { Usage } from '@/types/api'

const session = useSession()
const user = computed(() => session.state.user)

const usage = ref<Usage | null>(null)
const loading = ref(true)
const error = ref('')

const greeting = computed(() => {
  const hour = new Date().getHours()
  if (hour < 5) return 'Still up'
  if (hour < 12) return 'Good morning'
  if (hour < 18) return 'Good afternoon'
  return 'Good evening'
})

const firstName = computed(() => user.value?.name?.trim().split(/\s+/)[0] || 'there')
const recent = computed(() => (usage.value?.recent ?? []).slice(0, 6))

function badgeClass(status: string): string {
  const tone = statusTone(status)
  return tone === 'neutral' ? 'badge' : `badge badge-${tone}`
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    usage.value = await get<Usage>('/api/account/usage?days=30')
  } catch (err) {
    error.value = reportError(err, 'Could not load your usage summary.')
  } finally {
    loading.value = false
  }
}

onMounted(load)

const quickstart = `curl -sS "$NOEMA_BASE_URL/v1/systemone" \\
  -H "Authorization: Bearer $NOEMA_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "jev-latest",
    "state": "The customer was charged twice.",
    "questions": {
      "refund": {
        "type": "noul",
        "instructions": "Does the customer ask for a refund?"
      }
    }
  }'`
</script>

<template>
  <div class="console-page">
    <div class="console-page-head">
      <div>
        <p class="eyebrow">Overview</p>
        <h1 class="console-h1">{{ greeting }}, {{ firstName }}.</h1>
        <p class="console-sub">Your decision traffic for the last 30 days, and the fastest path to a first call.</p>
      </div>
      <div class="console-page-actions">
        <button type="button" class="btn btn-sm" :disabled="loading" @click="load">
          <RefreshCw :size="14" :class="{ 'pub-spin': loading }" />
          Refresh
        </button>
        <RouterLink to="/console/keys" class="btn btn-primary">
          <KeyRound :size="15" />
          Create API key
        </RouterLink>
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
          label="Requests · 30d"
          :value="formatCompact(usage?.total ?? 0)"
          hint="Across every key and protocol"
          accent
        />
        <StatTile
          label="Answered"
          :value="formatCompact(usage?.answered ?? 0)"
          :hint="usage && usage.total ? `${Math.round((usage.answered / usage.total) * 100)}% of requests` : 'No requests yet'"
        />
        <StatTile
          label="Avg. response"
          :value="usage?.avg_duration_ms ? formatDuration(usage.avg_duration_ms) : '—'"
          hint="Successful requests only"
        />
        <StatTile
          label="Timed out"
          :value="formatCompact(usage?.timed_out ?? 0)"
          :hint="usage?.timed_out ? 'Consider a longer timeout' : 'None this period'"
        />
      </template>
    </div>

    <div class="console-overview-grid">
      <section class="panel console-panel">
        <header class="panel-header">
          <div>
            <h2 class="panel-title">Recent requests</h2>
            <p class="console-panel-sub">Newest first, from the last 30 days.</p>
          </div>
          <RouterLink to="/console/usage" class="pub-text-link">
            All usage
            <ArrowUpRight :size="14" />
          </RouterLink>
        </header>

        <div v-if="loading" class="console-list-loading">
          <span v-for="index in 4" :key="index" class="pub-skeleton" />
        </div>

        <div v-else-if="recent.length" class="table-wrap">
          <table class="table console-table">
            <thead>
              <tr>
                <th scope="col">Request</th>
                <th scope="col">Model</th>
                <th scope="col">Status</th>
                <th scope="col">Response</th>
                <th scope="col">When</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in recent" :key="item.id">
                <td><code class="mono tiny">{{ truncateId(item.id) }}</code></td>
                <td><span class="console-model-cell">{{ item.model }}</span></td>
                <td>
                  <span :class="badgeClass(item.status)">{{ statusLabel(item.status) }}</span>
                </td>
                <td class="mono tiny">{{ item.duration_ms ? formatDuration(item.duration_ms) : '—' }}</td>
                <td class="mono tiny muted">{{ timeAgo(item.created_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <EmptyState
          v-else
          title="No requests yet"
          description="Send your first decision request from the playground or with a cURL snippet."
        >
          <div class="console-empty-actions">
            <RouterLink to="/console/playground" class="btn btn-primary btn-sm">Open playground</RouterLink>
            <RouterLink to="/docs#quickstart" class="btn btn-sm">Quickstart</RouterLink>
          </div>
        </EmptyState>
      </section>

      <div class="console-overview-aside">
        <section class="panel console-panel">
          <header class="panel-header">
            <div>
              <h2 class="panel-title">Quickstart</h2>
              <p class="console-panel-sub">Session-authenticated, no key needed.</p>
            </div>
            <span class="badge badge-lime">cURL</span>
          </header>
          <div class="panel-body console-quickstart">
            <ol class="console-steps">
              <li>
                <span class="console-step-num mono">1</span>
                <p>Create a key in <RouterLink to="/console/keys">API keys</RouterLink>.</p>
              </li>
              <li>
                <span class="console-step-num mono">2</span>
                <p>Export <code>NOEMA_BASE_URL</code> and <code>NOEMA_API_KEY</code>.</p>
              </li>
              <li>
                <span class="console-step-num mono">3</span>
                <p>Send the request and read <code>answers</code>.</p>
              </li>
            </ol>
            <CodeBlock :code="quickstart" label="first request" max-height="300px" />
            <RouterLink to="/console/keys" class="pub-text-link console-quickstart-link">
              Create your first key
              <ArrowRight :size="14" />
            </RouterLink>
          </div>
        </section>

        <section class="panel console-panel console-resource-panel">
          <header class="panel-header">
            <h2 class="panel-title">Reference</h2>
          </header>
          <div class="console-resource-list">
            <RouterLink :to="{ path: '/docs', hash: '#system-one' }" class="console-resource">
              <span>
                <strong>System One</strong>
                <span class="mono tiny muted">POST /v1/systemone</span>
              </span>
              <ArrowUpRight :size="15" />
            </RouterLink>
            <RouterLink :to="{ path: '/docs', hash: '#gemini-decisions' }" class="console-resource">
              <span>
                <strong>Gemini Decisions</strong>
                <span class="mono tiny muted">POST /v1beta/decisions</span>
              </span>
              <ArrowUpRight :size="15" />
            </RouterLink>
            <RouterLink :to="{ path: '/docs', hash: '#questions' }" class="console-resource">
              <span>
                <strong>Question types</strong>
                <span class="mono tiny muted">noul · choice · score</span>
              </span>
              <ArrowUpRight :size="15" />
            </RouterLink>
            <RouterLink :to="{ path: '/docs', hash: '#errors' }" class="console-resource">
              <span>
                <strong>Errors</strong>
                <span class="mono tiny muted">Status codes and envelopes</span>
              </span>
              <ArrowUpRight :size="15" />
            </RouterLink>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>
