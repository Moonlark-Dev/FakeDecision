<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { KeyRound, Loader2, Plus, RefreshCw, ShieldCheck, Trash2 } from 'lucide-vue-next'
import BaseModal from '@/components/BaseModal.vue'
import CodeBlock from '@/components/CodeBlock.vue'
import CopyButton from '@/components/CopyButton.vue'
import EmptyState from '@/components/EmptyState.vue'
import { del, get, post } from '@/lib/api'
import { formatDate, timeAgo } from '@/lib/format'
import { toast } from '@/lib/toast'
import { reportError } from '@/public/support'
import type { ApiKey } from '@/types/api'

const keys = ref<ApiKey[]>([])
const loading = ref(true)
const error = ref('')

const createOpen = ref(false)
const createName = ref('')
const creating = ref(false)
const createError = ref('')
const createdSecret = ref('')
const createdName = ref('')

const revokeTarget = ref<ApiKey | null>(null)
const revoking = ref(false)

const activeKeys = computed(() => keys.value.filter((key) => !key.revoked_at))
const revokedKeys = computed(() => keys.value.filter((key) => Boolean(key.revoked_at)))

const authSnippets = `# System One
Authorization: Bearer fd_live_…

# Gemini Decisions
x-goog-api-key: fd_live_…`

async function load() {
  loading.value = true
  error.value = ''
  try {
    const payload = await get<{ keys: ApiKey[] }>('/api/keys')
    keys.value = payload.keys ?? []
  } catch (err) {
    error.value = reportError(err, 'Could not load your API keys.')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  createName.value = ''
  createError.value = ''
  createdSecret.value = ''
  createdName.value = ''
  createOpen.value = true
}

function closeCreate() {
  if (creating.value) return
  createOpen.value = false
  createdSecret.value = ''
  createdName.value = ''
  createName.value = ''
  createError.value = ''
}

async function createKey() {
  const name = createName.value.trim()
  if (!name) {
    createError.value = 'Give the key a name so you can identify it later.'
    return
  }
  if (name.length > 80) {
    createError.value = 'Key names are limited to 80 characters.'
    return
  }
  creating.value = true
  createError.value = ''
  try {
    const payload = await post<{ key: ApiKey; secret: string }>('/api/keys', { name })
    createdSecret.value = payload.secret
    createdName.value = payload.key.name
    keys.value = [payload.key, ...keys.value]
    toast('API key created', 'success', { detail: 'Copy the secret now — it will not be shown again.' })
  } catch (err) {
    createError.value = reportError(err, 'Could not create the API key.')
  } finally {
    creating.value = false
  }
}

function askRevoke(key: ApiKey) {
  revokeTarget.value = key
}

function closeRevoke() {
  if (revoking.value) return
  revokeTarget.value = null
}

async function confirmRevoke() {
  const target = revokeTarget.value
  if (!target || revoking.value) return
  revoking.value = true
  try {
    await del(`/api/keys/${encodeURIComponent(target.id)}`)
    keys.value = keys.value.map((key) =>
      key.id === target.id ? { ...key, revoked_at: Date.now() } : key,
    )
    toast('API key revoked', 'success', { detail: 'Requests using this key now fail with 401.' })
    revokeTarget.value = null
  } catch (err) {
    reportError(err, 'Could not revoke the API key.')
  } finally {
    revoking.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="console-page">
    <div class="console-page-head">
      <div>
        <p class="eyebrow">API keys</p>
        <h1 class="console-h1">Keys</h1>
        <p class="console-sub">
          Keys authenticate provider requests. The secret is shown once, at creation, and only a hash is stored.
        </p>
      </div>
      <div class="console-page-actions">
        <button type="button" class="btn btn-sm" :disabled="loading" @click="load">
          <RefreshCw :size="14" :class="{ 'pub-spin': loading }" />
          Refresh
        </button>
        <button type="button" class="btn btn-primary" @click="openCreate">
          <Plus :size="15" />
          Create key
        </button>
      </div>
    </div>

    <div v-if="error" class="console-alert console-alert-error" role="alert">
      <span>{{ error }}</span>
      <button type="button" class="btn btn-sm" @click="load">Retry</button>
    </div>

    <div class="console-keys-grid">
      <section class="panel console-panel">
        <header class="panel-header">
          <div>
            <h2 class="panel-title">Active keys</h2>
            <p class="console-panel-sub">
              {{ activeKeys.length }} active · {{ revokedKeys.length }} revoked
            </p>
          </div>
          <span class="badge"><KeyRound :size="12" /> {{ keys.length }} total</span>
        </header>

        <div v-if="loading" class="console-list-loading">
          <span v-for="index in 3" :key="index" class="pub-skeleton" />
        </div>

        <div v-else-if="activeKeys.length" class="table-wrap">
          <table class="table console-table console-keys-table">
            <thead>
              <tr>
                <th scope="col">Name</th>
                <th scope="col">Key</th>
                <th scope="col">Created</th>
                <th scope="col">Last used</th>
                <th scope="col"><span class="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="key in activeKeys" :key="key.id">
                <td>
                  <span class="console-key-name">{{ key.name }}</span>
                </td>
                <td><code class="mono console-key-masked">{{ key.masked }}</code></td>
                <td class="mono tiny muted">{{ formatDate(key.created_at, false) }}</td>
                <td class="mono tiny muted">{{ timeAgo(key.last_used_at) }}</td>
                <td class="console-key-actions">
                  <button type="button" class="btn btn-sm btn-danger" @click="askRevoke(key)">
                    <Trash2 :size="14" />
                    Revoke
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <EmptyState
          v-else
          title="No active API keys"
          description="Create a key to authenticate requests to /v1/systemone and /v1beta/decisions."
        >
          <button type="button" class="btn btn-primary btn-sm" @click="openCreate">
            <Plus :size="14" />
            Create your first key
          </button>
        </EmptyState>
      </section>

      <aside class="console-keys-aside">
        <section class="panel console-panel">
          <header class="panel-header">
            <h2 class="panel-title">How keys are sent</h2>
          </header>
          <div class="panel-body console-keys-auth">
            <CodeBlock :code="authSnippets" label="request headers" />
            <p class="field-hint">
              Send the key in a header, never a URL. Revoking a key takes effect immediately on both protocols.
            </p>
            <RouterLink :to="{ path: '/docs', hash: '#authentication' }" class="pub-text-link">
              Authentication reference
            </RouterLink>
          </div>
        </section>

        <section class="console-keys-note">
          <ShieldCheck :size="16" />
          <div>
            <p class="console-keys-note-title">Secrets are one-time</p>
            <p class="field-hint">
              This deployment stores a hash only. If you lose a secret, revoke the key and create a new one.
            </p>
          </div>
        </section>
      </aside>
    </div>

    <section v-if="revokedKeys.length" class="panel console-panel console-revoked-panel">
      <header class="panel-header">
        <div>
          <h2 class="panel-title">Revoked keys</h2>
          <p class="console-panel-sub">Kept for audit; requests using them are rejected.</p>
        </div>
      </header>
      <div class="table-wrap">
        <table class="table console-table">
          <thead>
            <tr>
              <th scope="col">Name</th>
              <th scope="col">Key</th>
              <th scope="col">Created</th>
              <th scope="col">Revoked</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="key in revokedKeys" :key="key.id" class="console-row-muted">
              <td>{{ key.name }}</td>
              <td><code class="mono">{{ key.masked }}</code></td>
              <td class="mono tiny muted">{{ formatDate(key.created_at, false) }}</td>
              <td><span class="badge badge-red">Revoked {{ key.revoked_at ? timeAgo(key.revoked_at) : '' }}</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <BaseModal :open="createOpen" title="Create API key" @close="closeCreate">
      <template v-if="!createdSecret">
        <div class="pub-field">
          <label class="label" for="key-name">Name</label>
          <input
            id="key-name"
            v-model="createName"
            class="input"
            type="text"
            maxlength="80"
            placeholder="Production · support router"
            :disabled="creating"
            @keydown.enter.prevent="createKey"
          />
          <p class="field-hint">A label for your inventory. It is not part of the key.</p>
          <p v-if="createError" class="field-error" role="alert">{{ createError }}</p>
        </div>
        <p class="console-modal-note">
          You will see the secret once. Copy it into your secret manager before closing this dialog.
        </p>
      </template>

      <template v-else>
        <div class="console-secret-reveal">
          <p class="console-secret-title">
            <ShieldCheck :size="16" />
            Copy this secret now
          </p>
          <p class="field-hint">
            This is the only time the full key for “{{ createdName }}” will be displayed. Store it securely.
          </p>
          <div class="console-secret-field">
            <code class="console-secret mono">{{ createdSecret }}</code>
            <CopyButton :text="createdSecret" label="Copy key" :small="false" />
          </div>
          <div class="console-secret-warning">
            <span class="mono tiny">Once closed, only a masked version is shown in this table.</span>
          </div>
        </div>
      </template>

      <template #footer>
        <template v-if="!createdSecret">
          <button type="button" class="btn" :disabled="creating" @click="closeCreate">Cancel</button>
          <button type="button" class="btn btn-primary" :disabled="creating" @click="createKey">
            <Loader2 v-if="creating" :size="15" class="pub-spin" />
            {{ creating ? 'Creating…' : 'Create key' }}
          </button>
        </template>
        <button v-else type="button" class="btn btn-primary" @click="closeCreate">Done</button>
      </template>
    </BaseModal>

    <BaseModal :open="Boolean(revokeTarget)" title="Revoke API key" @close="closeRevoke">
      <p class="console-modal-text">
        Revoke <strong>{{ revokeTarget?.name }}</strong>? Any service using
        <code class="mono">{{ revokeTarget?.masked }}</code> will start receiving <code>401</code> immediately.
      </p>
      <p class="console-modal-note">This cannot be undone. Create a new key to restore access.</p>
      <template #footer>
        <button type="button" class="btn" :disabled="revoking" @click="closeRevoke">Cancel</button>
        <button type="button" class="btn btn-danger" :disabled="revoking" @click="confirmRevoke">
          <Loader2 v-if="revoking" :size="15" class="pub-spin" />
          {{ revoking ? 'Revoking…' : 'Revoke key' }}
        </button>
      </template>
    </BaseModal>
  </div>
</template>
