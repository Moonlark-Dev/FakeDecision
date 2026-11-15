<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ChevronDown, ChevronRight, RefreshCw, ScrollText } from 'lucide-vue-next'
import type { AuditEntry } from '@/types/api'
import { get } from '@/lib/api'
import { formatDate } from '@/lib/format'
import CodeBlock from '@/components/CodeBlock.vue'
import EmptyState from '@/components/EmptyState.vue'
import PaginationBar from './components/PaginationBar.vue'
import type { AuditResponse } from './types'
import { errorMessage, shortId } from './utils'

const limit = 50
const logs = ref<AuditEntry[]>([])
const total = ref(0)
const offset = ref(0)
const loading = ref(true)
const error = ref('')
const expanded = ref<Record<string, boolean>>({})

const expandedCount = computed(() => Object.values(expanded.value).filter(Boolean).length)

const ACTIONS: Record<string, string> = {
  'admin.login': 'Signed in',
  'admin.password_change': 'Changed own password',
  'operator.create': 'Created operator',
  'operator.update': 'Updated operator',
  'user.update': 'Updated user',
  'model.create': 'Created model',
  'model.update': 'Updated model',
  'model.delete': 'Deleted model',
  'settings.update': 'Updated settings',
  'request.answer': 'Answered request',
  'request.assign': 'Reassigned request',
  'request.cancel': 'Cancelled request',
  'request.auto_fill': 'Auto-filled request',
  'request.timeout': 'Request timed out',
}

function actionLabel(action: string): string {
  return ACTIONS[action] || action
}

function detailJson(detail: unknown): string {
  if (detail === null || detail === undefined) return 'No structured detail recorded.'
  try {
    return JSON.stringify(detail, null, 2)
  } catch {
    return String(detail)
  }
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const response = await get<AuditResponse>(`/api/admin/audit?limit=${limit}&offset=${offset.value}`)
    logs.value = response.logs
    total.value = response.total
  } catch (err) {
    error.value = errorMessage(err, 'Could not load the audit log.')
  } finally {
    loading.value = false
  }
}

function onOffset(next: number) {
  offset.value = next
  void load()
}

function toggle(id: string) {
  expanded.value = { ...expanded.value, [id]: !expanded.value[id] }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="adm-page">
    <header class="adm-page-head">
      <div>
        <p class="eyebrow adm-page-eyebrow">Administration</p>
        <h1 class="adm-page-title">Audit log</h1>
        <p class="adm-page-sub">Every operator and administrator action, with structured details.</p>
      </div>
      <div class="adm-page-actions">
        <span v-if="expandedCount" class="badge">{{ expandedCount }} expanded</span>
        <button type="button" class="btn btn-sm" :disabled="loading" @click="load">
          <RefreshCw :size="14" :class="{ 'adm-spin': loading }" />
          <span>Refresh</span>
        </button>
      </div>
    </header>

    <div v-if="error" class="adm-alert" role="alert">
      <span>{{ error }}</span>
      <button type="button" class="btn btn-sm" @click="load">Retry</button>
    </div>

    <section class="adm-panel">
      <header class="adm-panel-head">
        <div>
          <h2 class="adm-panel-title">Actions</h2>
          <p class="adm-panel-sub">{{ total }} entries · newest first</p>
        </div>
        <ScrollText :size="16" class="muted" aria-hidden="true" />
      </header>

      <div class="table-wrap">
        <table class="table adm-table adm-audit-table">
          <thead>
            <tr>
              <th scope="col"><span class="sr-only">Expand</span></th>
              <th scope="col">Time</th>
              <th scope="col">Actor</th>
              <th scope="col">Action</th>
              <th scope="col">Target</th>
            </tr>
          </thead>
          <tbody>
            <template v-if="loading && !logs.length">
              <tr v-for="n in 8" :key="n"><td colspan="5"><div class="adm-skeleton-row" /></td></tr>
            </template>
            <tr v-else-if="!logs.length">
              <td colspan="5"><EmptyState title="No audit entries" description="Actions appear here as operators work." /></td>
            </tr>
            <template v-else>
              <template v-for="log in logs" :key="log.id">
                <tr class="adm-row-clickable" @click="toggle(log.id)">
                  <td class="adm-audit-toggle-cell">
                    <button
                      type="button"
                      class="btn btn-ghost btn-icon btn-sm"
                      :aria-expanded="Boolean(expanded[log.id])"
                      :aria-label="expanded[log.id] ? 'Hide details' : 'Show details'"
                      @click.stop="toggle(log.id)"
                    >
                      <ChevronDown v-if="expanded[log.id]" :size="14" />
                      <ChevronRight v-else :size="14" />
                    </button>
                  </td>
                  <td class="nowrap muted">{{ formatDate(log.created_at) }}</td>
                  <td>
                    <span class="adm-actor">
                      <span class="adm-actor-name">{{ log.actor_name }}</span>
                      <span class="badge" :class="log.actor_kind === 'system' ? 'badge-amber' : log.actor_kind === 'admin' ? 'badge-blue' : ''">
                        {{ log.actor_kind }}
                      </span>
                    </span>
                  </td>
                  <td>
                    <span class="adm-audit-action">{{ actionLabel(log.action) }}</span>
                    <span class="mono muted tiny">{{ log.action }}</span>
                  </td>
                  <td class="mono muted">{{ log.target ? shortId(log.target, 18) : '—' }}</td>
                </tr>
                <tr v-if="expanded[log.id]" class="adm-audit-detail-row">
                  <td colspan="5">
                    <CodeBlock :code="detailJson(log.detail)" label="Audit detail" />
                  </td>
                </tr>
              </template>
            </template>
          </tbody>
        </table>
      </div>

      <footer class="adm-panel-foot adm-panel-foot-pagination">
        <PaginationBar :total="total" :limit="limit" :offset="offset" :loading="loading" @update:offset="onOffset" />
      </footer>
    </section>
  </div>
</template>
